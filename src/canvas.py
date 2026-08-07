import gi


gi.require_version("Gtk", "4.0")
gi.require_version("Poppler", "0.18")
from gi.repository import Gdk, Gtk, Poppler, GLib
import cairo


class PDFCanvas(Gtk.DrawingArea):

    def __init__(self):
        super().__init__()
        self.doc = None
        self.page = None
        self.scale = 1.0
        self._layout_cache = None
        self._render_cache = None

        self.start_x = self.start_y = self.curr_x = self.curr_y = 0
        self.is_drawing = False
        self.bbox = None

        self.on_selection_completed = None
        self.on_zoom_changed = None

        self.set_draw_func(self.on_draw)

        click_gesture = Gtk.GestureClick.new()
        click_gesture.connect("pressed", self.on_press)
        click_gesture.connect("released", self.on_release)
        self.add_controller(click_gesture)

        motion_controller = Gtk.EventControllerMotion.new()
        motion_controller.connect("motion", self.on_motion)
        self.add_controller(motion_controller)

        scroll_controller = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.BOTH_AXES
        )
        scroll_controller.connect("scroll", self.on_scroll)
        self.add_controller(scroll_controller)

    def load_pdf(self, file_path):
        uri = (
            f"file://{file_path}"
            if not file_path.startswith("file://")
            else file_path
        )
        self.doc = Poppler.Document.new_from_file(uri, None)
        self.bbox = None
        self.scale = 1.0
        self._layout_cache = None
        self._render_cache = None
        self.update_page()

    def set_scale(self, scale_factor):
        new_scale = max(0.5, min(scale_factor, 3.0))
        if abs(new_scale - self.scale) < 0.001:
            return
        self.scale = new_scale
        self._render_cache = None
        self.update_canvas_size()
        self.queue_draw()
        if self.on_zoom_changed:
            self.on_zoom_changed(self.scale)

    def set_scale_unclamped(self, scale_factor):
        new_scale = max(0.1, scale_factor)
        if abs(new_scale - self.scale) < 0.001:
            return
        self.scale = new_scale
        self._render_cache = None
        self.update_canvas_size()
        self.queue_draw()
        if self.on_zoom_changed:
            self.on_zoom_changed(self.scale)

    def _get_scrolled_window(self):
        widget = self.get_parent()
        while widget is not None:
            if isinstance(widget, Gtk.ScrolledWindow):
                return widget
            widget = widget.get_parent()
        return None

    def fit_to_width(self):
        if not self.page:
            return
        parent = self._get_scrolled_window()
        if parent is None:
            return
        hadj = parent.get_hadjustment()
        available = hadj.get_page_size() if hadj else parent.get_width()
        if available <= 0:
            return
        page_width, _ = self.page.get_size()
        self.set_scale_unclamped(available / page_width)
        if hadj:
            hadj.set_value(0)

    def zoom_about_center(self, factor):
        old = self.scale
        new = max(0.5, min(old * factor, 3.0))
        if abs(new - old) < 0.001:
            return

        parent = self._get_scrolled_window()
        hadj = parent.get_hadjustment() if parent else None
        vadj = parent.get_vadjustment() if parent else None
        h_center = (
            hadj.get_value() + hadj.get_page_size() / 2.0 if hadj else 0.0
        )
        v_center = (
            vadj.get_value() + vadj.get_page_size() / 2.0 if vadj else 0.0
        )

        self.set_scale(new)
        ratio = new / old

        def restore_scroll():
            if hadj is not None:
                maximum = max(0.0, hadj.get_upper() - hadj.get_page_size())
                hadj.set_value(
                    min(
                        maximum,
                        max(0.0, h_center * ratio - hadj.get_page_size() / 2.0),
                    )
                )
            if vadj is not None:
                maximum = max(0.0, vadj.get_upper() - vadj.get_page_size())
                vadj.set_value(
                    min(
                        maximum,
                        max(0.0, v_center * ratio - vadj.get_page_size() / 2.0),
                    )
                )
            return False

        GLib.idle_add(restore_scroll)

    def on_scroll(self, controller, dx, dy):
        state = controller.get_current_event_state()
        if state & Gdk.ModifierType.CONTROL_MASK:
            if dy:
                self.zoom_about_center(1.1 if dy < 0 else 1.0 / 1.1)
            return True
        return False

    def update_page(self):
        if not self.doc:
            return
        self.page = self.doc.get_page(0)
        self._layout_cache = None
        self._render_cache = None
        self.update_canvas_size()
        self.queue_draw()

    def update_canvas_size(self):
        if self.page:
            width, height = self.page.get_size()
            self.set_content_width(int(width * self.scale))
            self.set_content_height(int(height * self.scale))

    def get_page_size(self):
        return self.page.get_size() if self.page else None

    def extract_text(self, x0, top, x1, bottom):
        if not self.page:
            return ""
        ok, rects, text = self._get_layout()
        if not ok or not rects or len(rects) != len(text):
            rect = Poppler.Rectangle()
            rect.x1, rect.y1, rect.x2, rect.y2 = x0, top, x1, bottom
            return self.page.get_text_for_area(rect) or ""
        return self._reconstruct_text(text, rects, x0, top, x1, bottom)

    def _get_layout(self):
        if self._layout_cache is None:
            try:
                ok, rects = self.page.get_text_layout()
                text = self.page.get_text()
            except Exception:
                ok, rects, text = False, None, ""
            self._layout_cache = (ok, rects, text)
        return self._layout_cache

    @staticmethod
    def _reconstruct_text(text, rects, x0, top, x1, bottom, tol=1.0):
        groups = {}
        for char, rect in zip(text, rects):
            if char == "\n":
                continue
            center_x = (rect.x1 + rect.x2) / 2
            center_y = (rect.y1 + rect.y2) / 2
            if (
                x0 - tol <= center_x <= x1 + tol
                and top - tol <= center_y <= bottom + tol
            ):
                groups.setdefault(round(center_y), []).append((char, rect))

        lines = []
        for line in sorted(groups.values(), key=lambda chars: chars[0][1].y1):
            chars = sorted(line, key=lambda item: item[1].x1)
            output = ""
            previous = None
            for char, rect in chars:
                if previous is not None and rect.x1 - previous.x2 > 2.0:
                    output += " "
                output += char
                previous = rect
            lines.append(output)
        return "\n".join(lines).rstrip()

    def set_bbox(self, x0, top, x1, bottom):
        size = self.get_page_size()
        if size:
            page_width, page_height = size
            x0 = max(0.0, min(x0, page_width))
            x1 = max(0.0, min(x1, page_width))
            top = max(0.0, min(top, page_height))
            bottom = max(0.0, min(bottom, page_height))
        self.bbox = (min(x0, x1), min(top, bottom), max(x0, x1), max(top, bottom))
        self.queue_draw()

    def _get_render_cache(self):
        if self._render_cache is None and self.page is not None:
            width, height = self.page.get_size()
            iw = max(1, int(width * self.scale))
            ih = max(1, int(height * self.scale))
            surface = cairo.ImageSurface(cairo.Format.ARGB32, iw, ih)
            context = cairo.Context(surface)
            context.scale(self.scale, self.scale)
            self.page.render(context)
            self._render_cache = surface
        return self._render_cache

    def on_draw(self, area, cr, width, height):
        if not self.page:
            return

        surface = self._get_render_cache()
        if surface is not None:
            cr.set_source_surface(surface, 0, 0)
            cr.paint()

        bbox = self.bbox
        if self.is_drawing:
            bbox = (
                min(self.start_x, self.curr_x) / self.scale,
                min(self.start_y, self.curr_y) / self.scale,
                max(self.start_x, self.curr_x) / self.scale,
                max(self.start_y, self.curr_y) / self.scale,
            )
        if bbox:
            x0, top, x1, bottom = bbox
            cr.set_source_rgba(0.9, 0.2, 0.2, 0.25)
            cr.rectangle(
                x0 * self.scale,
                top * self.scale,
                (x1 - x0) * self.scale,
                (bottom - top) * self.scale,
            )
            cr.fill_preserve()
            cr.set_source_rgb(0.9, 0.1, 0.1)
            cr.set_line_width(1.5)
            cr.stroke()

    def on_press(self, gesture, n_press, x, y):
        if gesture.get_current_button() != 1:
            return
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
        if x1 - x0 < 3 or bottom - top < 3:
            return

        self.bbox = (x0, top, x1, bottom)
        text = self.extract_text(x0, top, x1, bottom)
        if self.on_selection_completed:
            self.on_selection_completed(x0, top, x1, bottom, text)
