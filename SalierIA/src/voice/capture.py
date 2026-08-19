import threading
import time

import keyboard
import numpy as np
import sounddevice as sd

# Hold F9 to record, release to send. Change PTT_KEY to any key name keyboard supports.
PTT_KEY = 'F9'


class VoiceCapture:
    SAMPLE_RATE = 16000
    FRAME_LENGTH = 512
    MAX_RECORD_SECONDS = 10

    def __init__(self, on_command_ready):
        self.on_command_ready = on_command_ready
        self._recording = False
        self._frames = []
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._recording

    def start(self):
        keyboard.on_press_key(PTT_KEY, self._on_key_press, suppress=False)
        keyboard.on_release_key(PTT_KEY, self._on_key_release, suppress=False)
        with sd.InputStream(
            samplerate=self.SAMPLE_RATE,
            channels=1,
            dtype='int16',
            blocksize=self.FRAME_LENGTH,
            callback=self._audio_callback,
        ):
            self._stop_event.wait()

    def stop(self):
        self._stop_event.set()

    def _on_key_press(self, event):
        with self._lock:
            if not self._recording:
                self._recording = True
                self._frames = []

    def _on_key_release(self, event):
        with self._lock:
            if self._recording:
                self._flush()

    def _audio_callback(self, indata, frames, time_info, status):
        with self._lock:
            if self._recording:
                self._frames.extend(indata[:, 0].tolist())
                max_frames = self.SAMPLE_RATE * self.MAX_RECORD_SECONDS
                if len(self._frames) >= max_frames:
                    self._flush()

    def _flush(self):
        # Called with self._lock held
        frames = self._frames[:]
        self._frames = []
        self._recording = False
        audio_bytes = np.array(frames, dtype=np.int16).tobytes()
        threading.Thread(target=self.on_command_ready, args=(audio_bytes,), daemon=True).start()
