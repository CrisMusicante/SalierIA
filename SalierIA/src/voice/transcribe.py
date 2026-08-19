import numpy as np
import whisper

MUSICAL_PROMPT = (
    'do re mi fa sol la si sostenido bemol negra blanca redonda corchea '
    'semicorchea compás tiempo piano forte fortissimo pianissimo crescendo '
    'decrescendo staccato tenuto acorde ligadura fermata tempo allegro andante'
)


class Transcriber:
    def __init__(self, model_size: str = 'small'):
        self.model = whisper.load_model(model_size)

    def transcribe(self, audio_bytes: bytes) -> str:
        # Convert raw int16 PCM bytes to float32 normalized to [-1, 1]
        audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        result = self.model.transcribe(
            audio,
            language='es',
            initial_prompt=MUSICAL_PROMPT,
            temperature=0.0,
        )
        return result['text'].strip()
