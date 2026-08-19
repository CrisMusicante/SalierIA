import os
import threading
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

LISTENING = 'LISTENING'
PROCESSING = 'PROCESSING'
ERROR = 'ERROR'
PAUSED = 'PAUSED'

_STATE_COLORS = {
    LISTENING:  (0, 200, 0, 255),
    PROCESSING: (255, 180, 0, 255),
    ERROR:      (220, 30, 30, 255),
    PAUSED:     (130, 130, 130, 255),
}

_STATE_TOOLTIPS = {
    LISTENING:  'Salieri — Escuchando',
    PROCESSING: 'Salieri — Procesando',
    ERROR:      'Salieri — Error',
    PAUSED:     'Salieri — Pausado',
}

_LOG_PATH = Path.home() / 'AppData' / 'Local' / 'SiberiusVoiceAgent' / 'salieri.log'


def _make_icon(state: str) -> Image.Image:
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = _STATE_COLORS.get(state, _STATE_COLORS[LISTENING])
    draw.ellipse([4, 4, 60, 60], fill=color)
    return img


class SalierITray:
    def __init__(self, on_start, on_stop, on_quit):
        self._on_start = on_start
        self._on_stop = on_stop
        self._on_quit = on_quit
        self._icon = None
        self._current_state = PAUSED

    def set_state(self, state: str):
        self._current_state = state
        if self._icon is not None:
            self._icon.icon = _make_icon(state)
            self._icon.title = _STATE_TOOLTIPS.get(state, 'Salieri')

    def run(self):
        menu = pystray.Menu(
            pystray.MenuItem('Iniciar', lambda icon, item: self._on_start()),
            pystray.MenuItem('Detener', lambda icon, item: self._on_stop()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Mostrar log', lambda icon, item: self._open_log()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Salir', lambda icon, item: self._quit(icon)),
        )
        self._icon = pystray.Icon(
            'salieri',
            _make_icon(self._current_state),
            _STATE_TOOLTIPS[self._current_state],
            menu,
        )
        threading.Thread(target=self._icon.run, daemon=True).start()

    def stop(self):
        if self._icon is not None:
            self._icon.stop()

    def _open_log(self):
        if _LOG_PATH.exists():
            os.startfile(str(_LOG_PATH))

    def _quit(self, icon):
        self._on_quit()
        icon.stop()
