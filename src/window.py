import gi


gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk
from canvas import PDFCanvas


class MainWindow(Adw.ApplicationWindow):

    def __init__(self, app):
        super().__init__(application=app, title="Bounds")
        self.set_default_size(950, 750)

        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.toast_overlay.set_child(self.main_box)

        # HeaderBar
        self.header_bar = Adw.HeaderBar()
        self.main_box.append(self.header_bar)

        btn_open = Gtk.Button(icon_name="document-open-symbolic")
        btn_open.set_tooltip_text("Open PDF")
        btn_open.connect("clicked", self.on_open_clicked)
        self.header_bar.pack_start(btn_open)

        self.format_model = Gtk.StringList.new(
            ["pdfplumber", "PyMuPDF (fitz)", "JSON", "CSV"]
        )
        self.format_dropdown = Gtk.DropDown.new(self.format_model, None)
        self.format_dropdown.set_selected(0)
        self.header_bar.pack_end(self.format_dropdown)

        # Stack (Empty vs Content)
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_vexpand(True)
        self.main_box.append(self.stack)

        self.status_page = Adw.StatusPage(
            title="No PDF Loaded",
            description="Open a PDF document or drag it here to pick coordinates",
            icon_name="document-open-symbolic",
        )
        btn_status_open = Gtk.Button(label="Open PDF")
        btn_status_open.add_css_class("suggested-action")
        btn_status_open.connect("clicked", self.on_open_clicked)
        self.status_page.set_child(btn_status_open)
        self.stack.add_named(self.status_page, "empty")

        scroll = Gtk.ScrolledWindow()
        self.canvas = PDFCanvas()
        self.canvas.on_selection_completed = self.on_bbox_extracted
        scroll.set_child(self.canvas)
        self.stack.add_named(scroll, "content")

        self.stack.set_visible_child_name("empty")

        # Drag & Drop Target
        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect("drop", self.on_file_dropped)
        self.add_controller(drop_target)

        # Bottom Info Bar
        self.bottom_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.bottom_bar.set_margin_start(12)
        self.bottom_bar.set_margin_end(12)
        self.bottom_bar.set_margin_top(8)
        self.bottom_bar.set_margin_bottom(8)

        self.lbl_info = Gtk.Label(
            label="Drag a box over the PDF to copy bounding box coordinates"
        )
        self.bottom_bar.append(self.lbl_info)
        self.main_box.append(self.bottom_bar)

    def on_open_clicked(self, btn):
        dialog = Gtk.FileDialog()
        dialog.open(self, None, self.on_file_dialog_finish)

    def on_file_dialog_finish(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            if file:
                self.load_pdf_file(file.get_path())
        except Exception:
            pass

    def on_file_dropped(self, target, value, x, y):
        if isinstance(value, Gdk.FileList):
            files = value.get_files()
            if files:
                self.load_pdf_file(files[0].get_path())
                return True
        return False

    def load_pdf_file(self, path):
        self.canvas.load_pdf(path)
        self.stack.set_visible_child_name("content")
        filename = path.split("/")[-1]
        self.set_subtitle(filename)

    def format_coordinates(self, x0, top, x1, bottom):
        idx = self.format_dropdown.get_selected()
        if idx == 0:
            return f"bbox = ({x0:.1f}, {top:.1f}, {x1:.1f}, {bottom:.1f})"
        elif idx == 1:
            return f"fitz.Rect({x0:.1f}, {top:.1f}, {x1:.1f}, {bottom:.1f})"
        elif idx == 2:
            return f'{{"x0": {x0:.1f}, "top": {top:.1f}, "x1": {x1:.1f}, "bottom": {bottom:.1f}}}'
        elif idx == 3:
            return f"{x0:.1f},{top:.1f},{x1:.1f},{bottom:.1f}"
        return f"({x0:.1f}, {top:.1f}, {x1:.1f}, {bottom:.1f})"

    def on_bbox_extracted(self, x0, top, x1, bottom, text):
        formatted_str = self.format_coordinates(x0, top, x1, bottom)

        clipboard = self.get_clipboard()
        clipboard.set(formatted_str)

        clean_text = text.strip().replace("\n", " ")
        preview = (
            f"<b>{formatted_str}</b> | <i>'{clean_text}'</i>"
            if clean_text
            else f"<b>{formatted_str}</b>"
        )
        self.lbl_info.set_markup(preview)

        toast = Adw.Toast.new(f"Copied: {formatted_str}")
        toast.set_timeout(2)
        self.toast_overlay.add_toast(toast)
