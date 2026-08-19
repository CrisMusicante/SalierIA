from pywinauto import Application


class SibiliusUIFallback:
    def __init__(self):
        self.app = Application(backend='uia').connect(title_re='Sibelius.*')
        self.main = self.app.top_window()

    def export_pdf(self, output_path: str):
        try:
            self.main.menu_select('File->Export->PDF...')
            dlg = self.app['Export PDF']
            dlg['File name:'].set_text(output_path)
            dlg['Save'].click()
            dlg.wait_not('visible', timeout=15)
        except Exception as e:
            raise RuntimeError(f'UI fallback failed: {e}')

    def export_musicxml(self, output_path: str):
        try:
            self.main.menu_select('File->Export->MusicXML...')
            dlg = self.app['Export MusicXML']
            dlg['File name:'].set_text(output_path)
            dlg['Save'].click()
            dlg.wait_not('visible', timeout=15)
        except Exception as e:
            raise RuntimeError(f'UI fallback failed: {e}')

    def export_midi(self, output_path: str):
        try:
            self.main.menu_select('File->Export->MIDI...')
            dlg = self.app['Export MIDI']
            dlg['File name:'].set_text(output_path)
            dlg['Save'].click()
            dlg.wait_not('visible', timeout=15)
        except Exception as e:
            raise RuntimeError(f'UI fallback failed: {e}')
