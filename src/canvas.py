import gi


gi.require_version("Gtk", "4.0")
gi.require_version("Poppler", "0.18")
from gi.repository import Gdk, Gtk, Poppler, GLib


class PDFCanvas(Gtk.DrawingArea):

    def __init__(self):
        super().__init__()
        self.doc = None
        self.page = None
        self.scale = 1.0
        self._layout_cache = None

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
        self.update_page()

    def set_scale(self, scale_factor):
        new_scale = max(0.5, min(scale_factor, 3.0))
        if abs(new_scale - self.scale) < 0.001:
            return
        self.scale = new_scale
        self.update_canvas_size()
        self.queue_draw()
        if self.on_zoom_changed:
            self.on_zoom_changed(self.scale)

    def zoom_about_center(self, factor):
        old = self.scale
        new = max(0.5, min(old * factor, 3.0))
        if abs(new - old) < 0.001:
            return

        parent = self.get_parent()
        hadj = None
        vadj = None
        if isinstance(parent, Gtk.ScrolledWindow):
            hadj = parent.get_hadjustment()
            vadj = parent.get_vadjustment()

        hc = (hadj.get_value() + hadj.get_page_size() / 2.0) if hadj else 0.0
        vc = (vadj.get_value() + vadj.get_page_size() / 2.0) if vadj else 0.0

        self.set_scale(new)
        ratio = new / old

        def restore_scroll():
            if hadj is not None:
                upper = max(0.0, hadj.get_upper() - hadj.get_page_size())
                hadj.set_value(
                    min(upper, max(0.0, hc * ratio - hadj.get_page_size() / 2.0))
                )
            if vadj is not None:
                upper = max(0.0, vadj.get_upper() - vadj.get_page_size())
                vadj.set_value(
                    min(upper, max(0.0, vc * ratio - vadj.get_page_size() / 2.0))
                )
            return False

        GLib.idle_add(restore_scroll)

    def on_scroll(self, controller, dx, dy):
        state = controller.get_current_event_state()
        if state & Gdk.ModifierType.CONTROL_MASK:
            if dy != 0:
                factor = 1.1 if dy < 0 else 1.0 / 1.1
                self.zoom_about_center(factor)
            return True
        return False

    def update_page(self):
        if not self.doc:
            return
        self.page = self.doc.get_page(0)
        self.update_canvas_size()
        self.queue_draw()

    def update_canvas_size(self):
        if self.page:
            w, h = self.page.get_size()
            self.set_content_width(int(w * self.scale))
            self.set_content_height(int(h * self.scale))

    def get_page_size(self):
        if self.page:
            return self.page.get_size()
        return None

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
        for ch, r in zip(text, rects):
            if ch == "\n":
                continue
            cx = (r.x1 + r.x2) / 2
            cy = (r.y1 + r.y2) / 2
            if x0 - tol <= cx <= x1 + tol and top - tol <= cy <= bottom + tol:
                groups.setdefault(round(cy), []).append((ch, r))
        if not groups:
            return ""
        out = []
        for cy in sorted(groups):
            chars = sorted(groups[cy], key=lambda cr: cr[1].x1)
            s = ""
            prev = None
            for ch, r in chars:
                if prev is not None and r.x1 - prev.x2 > 2.0:
                    s += " "
                s += ch
                prev = r
            out.append(s)
        return "\n".join(out).rstrip()

    def set_bbox(self, x0, top, x1, bottom):
        size = self.get_page_size()
        if size:
            w, h = size
            x0 = max(0.0, min(x0, w))
            x1 = max(0.0, min(x1, w))
            top = max(0.0, min(top, h))
            bottom = max(0.0, min(bottom, h))
        x0, x1 = min(x0, x1), max(x0, x1)
        top, bottom = min(top, bottom), max(top, bottom)
        self.bbox = (x0, top, x1, bottom)
        self.queue_draw()

    def on_draw(self, area, cr, width, height):
        if not self.page:
            return

        cr.scale(self.scale, self.scale)
        self.page.render(cr)

        if self.is_drawing:
            bbox = (
                min(self.start_x, self.curr_x) / self.scale,
                min(self.start_y, self.curr_y) / self.scale,
                max(self.start_x, self.curr_x) / self.scale,
                max(self.start_y, self.curr_y) / self.scale,
            )
        else:
            bbox = self.bbox

        if bbox:
            cr.scale(1.0 / self.scale, 1.0 / self.scale)

            x0, top, x1, bottom = bbox
            x = x0 * self.scale
            y = top * self.scale
            w = (x1 - x0) * self.scale
            h = (bottom - top) * self.scale

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

        self.bbox = (x0, top, x1, bottom)
        extracted_text = self.extract_text(x0, top, x1, bottom)

        if self.on_selection_completed:
            self.on_selection_completed(x0, top, x1, bottom, extracted_text)
