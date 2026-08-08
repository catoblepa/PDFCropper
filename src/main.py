import gettext
import os
import sys
import gi


gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, Gtk

_LOCALE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "locale"
)
gettext.bindtextdomain("pdfcropper", _LOCALE_DIR)
gettext.textdomain("pdfcropper")

_APP_ICONS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "icons")

from window import MainWindow


class PDFCropperApp(Adw.Application):

    def __init__(self):
        super().__init__(
            application_id="io.github.catoblepa.PDFCropper",
            flags=Gio.ApplicationFlags.HANDLES_OPEN,
        )
        self.win = None
        self._icons_registered = None

    def do_activate(self):
        if self._icons_registered is None:
            self._register_icons()
        if self.win is None:
            self.win = MainWindow(self)
        self.win.present()

    def _register_icons(self):
        self._icons_registered = True
        display = Gdk.Display.get_default()
        if display is None:
            return
        theme = Gtk.IconTheme.get_for_display(display)
        if os.path.isdir(_APP_ICONS):
            theme.add_search_path(_APP_ICONS)

    def do_open(self, files, n_files, hint):
        self.do_activate()
        for f in files:
            path = f.get_path()
            if path:
                self.win.load_pdf_file(path)
                break


def main():
    app = PDFCropperApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
