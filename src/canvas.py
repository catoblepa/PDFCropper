import gi


gi.require_version("Gtk", "4.0")
gi.require_version("Poppler", "0.18")
from gi.repository import Gdk, Gtk, Poppler


class PDFCanvas(Gtk.DrawingArea):

    def __init__(self):
        super().__init__()
        self.doc = None
        self.page = None
        self.current_page_idx = 0
        self.scale = 1.0

        self.start_x = self.start_y = self.curr_x = self.curr_y = 0
        self.is_drawing = False

        self.set_draw_func(self.on_draw)

        click_gesture = Gtk.GestureClick.new()
        click_gesture.connect("pressed", self.on_press)
        click_gesture.connect("released", self.on_release)
        self.add_controller(click_gesture)

        motion_controller = Gtk.EventControllerMotion.new()
        motion_controller.connect("motion", self.on_motion)
        self.add_controller(motion_controller)

        self.on_selection_completed = None

    def load_pdf(self, file_path):
        uri = (
            f"file://{file_path}"
            if not file_path.startswith("file://")
            else file_path
        )
        self.doc = Poppler.Document.new_from_file(uri, None)
        self.current_page_idx = 0
        self.update_page()

    def set_page(self, page_idx):
        if self.doc and 0 <= page_idx < self.doc.get_n_pages():
            self.current_page_idx = page_idx
            self.update_page()

    def set_scale(self, scale_factor):
        self.scale = max(0.5, min(scale_factor, 3.0))
        self.update_canvas_size()
        self.queue_draw()

    def update_page(self):
        if not self.doc:
            return
        self.page = self.doc.get_page(self.current_page_idx)
        self.update_canvas_size()
        self.queue_draw()

    def update_canvas_size(self):
        if self.page:
            w, h = self.page.get_size()
            self.set_content_width(int(w * self.scale))
            self.set_content_height(int(h * self.scale))

    def on_draw(self, area, cr, width, height):
        if not self.page:
            return

        cr.scale(self.scale, self.scale)
        self.page.render(cr)

        if self.is_drawing or (self.start_x != self.curr_x):
            cr.scale(1.0 / self.scale, 1.0 / self.scale)

            x = min(self.start_x, self.curr_x)
            y = min(self.start_y, self.curr_y)
            w = abs(self.curr_x - self.start_x)
            h = abs(self.curr_y - self.start_y)

            cr.set_source_rgba(0.9, 0.2, 0.2, 0.25)
            cr.rectangle(x, y, w, h)
            cr.fill_preserve()

            cr.set_source_rgb(0.9, 0.1, 0.1)
            cr.set_line_width(1.5)
            cr.stroke()

    def on_press(self, gesture, n_press, x, y):
        self.start_x = self.curr_x = x
        self.start_y = self.curr_y = y
        self.is_drawing = True

    def on_motion(self, controller, x, y):
        if self.is_drawing:
            self.curr_x = x
            self.curr_y = y
            self.queue_draw()

    def on_release(self, gesture, n_press, x, y):
        if not self.is_drawing:
            return

        self.is_drawing = False
        self.curr_x = x
        self.curr_y = y
        self.queue_draw()

        x0 = min(self.start_x, self.curr_x) / self.scale
        top = min(self.start_y, self.curr_y) / self.scale
        x1 = max(self.start_x, self.curr_x) / self.scale
        bottom = max(self.start_y, self.curr_y) / self.scale

        if (x1 - x0) < 3 or (bottom - top) < 3:
            return

        extracted_text = ""
        if self.page:
            rect = Poppler.Rectangle()
            rect.x1, rect.y1, rect.x2, rect.y2 = x0, top, x1, bottom
            extracted_text = self.page.get_text_for_area(rect) or ""

        if self.on_selection_completed:
            self.on_selection_completed(x0, top, x1, bottom, extracted_text)
