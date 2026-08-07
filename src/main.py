import sys
import gi


gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw
from window import MainWindow


class BoundsApp(Adw.Application):

    def __init__(self):
        super().__init__(application_id="io.github.catoblepa.Bounds")

    def do_activate(self):
        win = MainWindow(self)
        win.present()


def main():
    app = BoundsApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
