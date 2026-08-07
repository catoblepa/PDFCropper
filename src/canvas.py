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
        self.is_moving = False
        self.move_start_x = 0
        self.move_start_y = 0
        self.move_bbox = None
        self.is_resizing = False
        self.resize_handle = None
        self.resize_bbox = None
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

    def set_scale(self, scale_factor, clamp=True):
        if clamp:
            new_scale = max(0.5, min(scale_factor, 3.0))
        else:
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
        self.set_scale(available / page_width, clamp=False)
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
            px0, pt, px1, pb = (
                x0 * self.scale,
                top * self.scale,
                x1 * self.scale,
                bottom * self.scale,
            )
            cr.set_source_rgba(0.9, 0.2, 0.2, 0.25)
            cr.rectangle(px0, pt, px1 - px0, pb - pt)
            cr.fill_preserve()
            cr.set_source_rgb(0.9, 0.1, 0.1)
            cr.set_line_width(1.5)
            cr.stroke()

            handle = 6
            cr.set_source_rgb(0.9, 0.1, 0.1)
            for hx, hy in (
                (px0, pt),
                (px1, pt),
                (px0, pb),
                (px1, pb),
                ((px0 + px1) / 2, pt),
                ((px0 + px1) / 2, pb),
                (px0, (pt + pb) / 2),
                (px1, (pt + pb) / 2),
            ):
                cr.rectangle(hx - handle / 2, hy - handle / 2, handle, handle)
                cr.fill()

    def _handle_at(self, x, y, tol=8):
        if self.bbox is None:
            return None
        x0, top, x1, bottom = self.bbox
        px0, pt, px1, pb = (
            x0 * self.scale,
            top * self.scale,
            x1 * self.scale,
            bottom * self.scale,
        )
        near_left = abs(x - px0) <= tol
        near_right = abs(x - px1) <= tol
        near_top = abs(y - pt) <= tol
        near_bottom = abs(y - pb) <= tol
        if near_top and near_left:
            return "nw"
        if near_top and near_right:
            return "ne"
        if near_bottom and near_left:
            return "sw"
        if near_bottom and near_right:
            return "se"
        if near_top:
            return "n"
        if near_bottom:
            return "s"
        if near_left:
            return "w"
        if near_right:
            return "e"
        return None

    def _resize_to(self, x, y, min_size=5.0):
        orig_x0, orig_top, orig_x1, orig_bottom = self.resize_bbox
        dx = (x - self.move_start_x) / self.scale
        dy = (y - self.move_start_y) / self.scale

        size = self.get_page_size()
        if size:
            page_width, page_height = size
        else:
            page_width, page_height = 1e9, 1e9

        x0, top, x1, bottom = orig_x0, orig_top, orig_x1, orig_bottom
        handle = self.resize_handle

        if "w" in handle:
            x0 = max(0.0, min(orig_x0 + dx, orig_x1 - min_size))
        if "e" in handle:
            x1 = min(page_width, max(orig_x1 + dx, orig_x0 + min_size))
        if "n" in handle:
            top = max(0.0, min(orig_top + dy, orig_bottom - min_size))
        if "s" in handle:
            bottom = min(page_height, max(orig_bottom + dy, orig_top + min_size))

        self.bbox = (x0, top, x1, bottom)
        self.queue_draw()

    def on_press(self, gesture, n_press, x, y):
        if gesture.get_current_button() != 1:
            return
        handle = self._handle_at(x, y)
        if handle is not None:
            self.is_resizing = True
            self.resize_handle = handle
            self.resize_bbox = self.bbox
            self.move_start_x = x
            self.move_start_y = y
            self.set_cursor_from_name("default")
            return
        if self.bbox is not None and self._point_in_bbox(x, y):
            self.is_moving = True
            self.move_start_x = x
            self.move_start_y = y
            self.move_bbox = self.bbox
            self.set_cursor_from_name("move")
            return
        self.start_x = self.curr_x = x
        self.start_y = self.curr_y = y
        self.is_drawing = True

    def _point_in_bbox(self, x, y):
        x0, top, x1, bottom = self.bbox
        return (
            x0 * self.scale <= x <= x1 * self.scale
            and top * self.scale <= y <= bottom * self.scale
        )

    def _move_bbox_to(self, x, y):
        dx = (x - self.move_start_x) / self.scale
        dy = (y - self.move_start_y) / self.scale
        orig_x0, orig_top, orig_x1, orig_bottom = self.move_bbox
        width = orig_x1 - orig_x0
        height = orig_bottom - orig_top

        size = self.get_page_size()
        if size:
            page_width, page_height = size
            x0 = max(0.0, min(orig_x0 + dx, page_width - width))
            top = max(0.0, min(orig_top + dy, page_height - height))
        else:
            x0 = orig_x0 + dx
            top = orig_top + dy
        self.bbox = (x0, top, x0 + width, top + height)
        self.queue_draw()

    def on_motion(self, controller, x, y):
        if self.is_resizing:
            self._resize_to(x, y)
        elif self.is_moving:
            self._move_bbox_to(x, y)
        elif self.is_drawing:
            self.curr_x = x
            self.curr_y = y
            self.queue_draw()

    def _commit_bbox(self):
        self.set_cursor_from_name("default")
        x0, top, x1, bottom = self.bbox
        text = self.extract_text(x0, top, x1, bottom)
        if self.on_selection_completed:
            self.on_selection_completed(x0, top, x1, bottom, text)

    def on_release(self, gesture, n_press, x, y):
        if self.is_resizing:
            self.is_resizing = False
            self._resize_to(x, y)
            self._commit_bbox()
            return
        if self.is_moving:
            self.is_moving = False
            self.curr_x = x
            self.curr_y = y
            self._move_bbox_to(x, y)
            self._commit_bbox()
            return
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
        self._commit_bbox()
