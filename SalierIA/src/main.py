import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

LOG_DIR = Path.home() / 'AppData' / 'Local' / 'SiberiusVoiceAgent'
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'salieri.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger('salieri.main')

import pyttsx3  # noqa: E402 — must come after basicConfig

from src.agent.claude_agent import SiberiusAgent  # noqa: E402
from src.agent.parser import parse  # noqa: E402
from src.bridge.ipc import IPCError, IPCManager  # noqa: E402
from src.ui.tray import ERROR, LISTENING, PAUSED, PROCESSING, SalierITray  # noqa: E402
from src.voice.capture import VoiceCapture  # noqa: E402
from src.voice.transcribe import Transcriber  # noqa: E402


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise EnvironmentError(f'Required environment variable {name} is not set')
    return value


class SiberiusOrchestrator:
    def __init__(self):
        _require_env('ANTHROPIC_API_KEY')
        bridge_dir = _require_env('SVA_BRIDGE_DIR')

        self.tts = pyttsx3.init()
        self.tts.setProperty('rate', int(os.getenv('SVA_TTS_RATE', '175')))

        logger.info('Loading Whisper model...')
        self.transcriber = Transcriber(model_size=os.getenv('SVA_WHISPER_MODEL', 'small'))

        self.agent = SiberiusAgent(
            tools_path='docs/tools.json',
            prompt_path='src/agent/system_prompt.txt',
        )
        self.ipc = IPCManager(bridge_dir)
        self.capture = VoiceCapture(on_command_ready=self._on_command_ready)
        self.tray = SalierITray(
            on_start=self.start_listening,
            on_stop=self.stop_listening,
            on_quit=self.shutdown,
        )
        self._running = False

    def _on_command_ready(self, audio_bytes: bytes):
        self.tray.set_state(PROCESSING)
        try:
            transcript = self.transcriber.transcribe(audio_bytes)
            logger.info('Transcribed: %s', transcript)

            intent = parse(transcript, self.agent.score_state.to_dict())
            result = self.agent.process(transcript, intent)

            for tool_call in result.tool_calls:
                if tool_call.name == 'export_score':
                    resp = self.ipc.send_and_wait(tool_call.name, tool_call.input)
                    if resp.get('status') == 'use_fallback':
                        logger.info('Export requires UI fallback — not implemented in v1')
                else:
                    self.ipc.send_and_wait(tool_call.name, tool_call.input)
                    logger.info('Tool executed: %s', tool_call.name)

            if result.confirmation:
                self._speak(result.confirmation)

        except TimeoutError:
            logger.error('Sibelius did not respond in time')
            self._speak('Sibelius no respondió. Verifica que esté abierto.')
            self.tray.set_state(ERROR)
        except IPCError as e:
            logger.error('IPC error: %s', e)
            self._speak('Error en Sibelius. Revisa el log.')
            self.tray.set_state(ERROR)
        except Exception as e:
            logger.exception('Unexpected error: %s', e)
            self._speak('Ocurrió un error. Intenta de nuevo.')
            self.tray.set_state(ERROR)
        else:
            self.tray.set_state(LISTENING)

    def _speak(self, text: str):
        self.tts.say(text)
        self.tts.runAndWait()

    def start_listening(self):
        self._running = True
        self.tray.set_state(LISTENING)
        logger.info('Salieri iniciado. Mantén F9 para grabar un comando.')

    def stop_listening(self):
        self._running = False
        self.tray.set_state(PAUSED)

    def shutdown(self):
        self._running = False
        self.ipc.clear()
        logger.info('Salieri apagado.')
        sys.exit(0)

    def run(self):
        self.tray.run()
        self.start_listening()
        self.capture.start()  # blocks forever


if __name__ == '__main__':
    orchestrator = SiberiusOrchestrator()
    orchestrator.run()
