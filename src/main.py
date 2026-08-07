import gettext
import os
import sys
import gi


gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio

_LOCALE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "locale"
)
gettext.bindtextdomain("bounds", _LOCALE_DIR)
gettext.textdomain("bounds")

from window import MainWindow


class BoundsApp(Adw.Application):

    def __init__(self):
        super().__init__(
            application_id="io.github.catoblepa.PDFBounds",
            flags=Gio.ApplicationFlags.HANDLES_OPEN,
        )
        self.win = None

    def do_activate(self):
        if self.win is None:
            self.win = MainWindow(self)
        self.win.present()

    def do_open(self, files, n_files, hint):
        self.do_activate()
        for f in files:
            path = f.get_path()
            if path:
                self.win.load_pdf_file(path)
                break


def main():
    app = BoundsApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
