import math
import os
import shutil
import subprocess
import tempfile
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
        self._file_path = None
        self.current_page_idx = 0
        self.scale = 1.0
        self.rotation = 0
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
        self.on_page_changed = None

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
        self._file_path = uri
        self.doc = Poppler.Document.new_from_file(uri, None)
        self.current_page_idx = 0
        self.bbox = None
        self.scale = 1.0
        self.rotation = 0
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
        pw, ph = self.page.get_size()
        view_w = ph if self.rotation in (90, 270) else pw
        self.set_scale(available / view_w, clamp=False)
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
        self.page = self.doc.get_page(self.current_page_idx)
        self._layout_cache = None
        self._render_cache = None
        self.update_canvas_size()
        self.queue_draw()

    def get_page_count(self):
        if self.doc:
            return self.doc.get_n_pages()
        return 1

    def get_current_page(self):
        return self.current_page_idx

    def go_to_page(self, idx):
        if not self.doc:
            return
        count = self.get_page_count()
        idx = max(0, min(idx, count - 1))
        if idx == self.current_page_idx:
            return
        self.current_page_idx = idx
        self._layout_cache = None
        self._render_cache = None
        self.page = self.doc.get_page(idx)
        self.update_canvas_size()
        self.queue_draw()
        if self.on_page_changed:
            self.on_page_changed(idx, count)

    def update_canvas_size(self):
        if self.page:
            width, height = self.page.get_size()
            if self.rotation in (90, 270):
                width, height = height, width
            self.set_content_width(int(width * self.scale))
            self.set_content_height(int(height * self.scale))

    def rotate(self, degrees):
        self.rotation = (self.rotation + degrees) % 360
        self._render_cache = None
        self.update_canvas_size()
        self.queue_draw()
        if self.on_zoom_changed:
            self.on_zoom_changed(self.scale)

    def widget_to_page(self, wx, wy):
        """Convert widget coordinates to page (PDF) coordinates."""
        width, height = self.page.get_size()
        x = wx / self.scale
        y = wy / self.scale
        if self.rotation == 90:
            return y, height - x
        if self.rotation == 180:
            return width - x, height - y
        if self.rotation == 270:
            return width - y, x
        return x, y

    def page_to_widget(self, px, py):
        """Convert page (PDF) coordinates to widget coordinates."""
        width, height = self.page.get_size()
        if self.rotation == 90:
            return (height - py) * self.scale, px * self.scale
        if self.rotation == 180:
            return (width - px) * self.scale, (height - py) * self.scale
        if self.rotation == 270:
            return py * self.scale, (width - px) * self.scale
        return px * self.scale, py * self.scale

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

    @staticmethod
    def get_ocr_languages():
        """List installed tesseract languages from tessdata dir."""
        tessdata_dir = os.environ.get(
            "TESSDATA_PREFIX", "/app/share/tessdata"
        )
        if not os.path.isdir(tessdata_dir):
            return []
        langs = []
        for name in sorted(os.listdir(tessdata_dir)):
            if name.endswith(".traineddata"):
                langs.append(name[: -len(".traineddata")])
        return langs

    @staticmethod
    def tesseract_available():
        return shutil.which("tesseract") is not None

    def ocr_region(self, x0, top, x1, bottom, lang, page=None, scale=None):
        """Run tesseract OCR on the selected region (rotation aware).

        page/scale are captured by the caller so this can run in a thread
        even if the canvas page changes in the meantime.
        """
        page = page if page is not None else self.page
        scale = scale if scale is not None else self.scale
        if not page:
            return ""
        if x1 - x0 <= 0 or bottom - top <= 0:
            return ""

        scale = max(scale, 2.0)
        pw, ph = page.get_size()
        vw, vh = pw, ph
        if self.rotation in (90, 270):
            vw, vh = ph, pw
        iw = max(1, int(vw * scale))
        ih = max(1, int(vh * scale))

        # render the whole page with rotation applied
        page_surface = cairo.ImageSurface(cairo.Format.ARGB32, iw, ih)
        context = cairo.Context(page_surface)
        context.set_source_rgb(1, 1, 1)
        context.paint()
        context.scale(scale, scale)
        if self.rotation == 90:
            context.translate(ph, 0)
            context.rotate(math.pi / 2)
        elif self.rotation == 180:
            context.translate(pw, ph)
            context.rotate(math.pi)
        elif self.rotation == 270:
            context.translate(0, pw)
            context.rotate(-math.pi / 2)
        page.render(context)

        # bbox corners in view coordinates, using captured page/scale
        def to_view(px, py):
            W, H = page.get_size()
            if self.rotation == 90:
                return (H - py) * scale, px * scale
            if self.rotation == 180:
                return (W - px) * scale, (H - py) * scale
            if self.rotation == 270:
                return py * scale, (W - px) * scale
            return px * scale, py * scale

        wx0, wy0 = to_view(x0, top)
        wx1, wy1 = to_view(x1, bottom)
        rx = min(wx0, wx1)
        ry = min(wy0, wy1)
        rw = abs(wx1 - wx0)
        rh = abs(wy1 - wy0)
        if rw < 1 or rh < 1:
            return ""

        crop = cairo.ImageSurface(cairo.Format.ARGB32, int(rw), int(rh))
        crop_ctx = cairo.Context(crop)
        crop_ctx.set_source_surface(page_surface, -rx, -ry)
        crop_ctx.paint()

        png_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                png_path = tmp.name
            crop.write_to_png(png_path)
            lang_opt = "-l", lang if lang else "eng"
            result = subprocess.run(
                ["tesseract", png_path, "-", *lang_opt, "--psm", "6"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.stdout.strip()
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            return ""
        finally:
            if png_path and os.path.exists(png_path):
                try:
                    os.unlink(png_path)
                except OSError:
                    pass

    def save_cropped_pdf(self, output_path, x0, top, x1, bottom, all_pages=True):
        """Save a cropped copy using pypdf (vector crop).

        The region is the one selected on the current page. If all_pages is
        True it is applied to every page, clamped to each page's bounds;
        otherwise only the current page is cropped. The current rotation is
        applied as shown on screen.
        """
        if not self.doc or self.bbox is None or not self._file_path:
            return False
        try:
            from pypdf import PdfReader, PdfWriter
        except ImportError:
            return False

        if not self.page:
            return False

        src_path = self._file_path
        if src_path.startswith("file://"):
            src_path = src_path[len("file://"):]

        reader = PdfReader(src_path)
        writer = PdfWriter()

        # region in view coordinates (as seen on screen), in points
        wx0, wy0 = self.page_to_widget(x0, top)
        wx1, wy1 = self.page_to_widget(x1, bottom)
        s = self.scale
        v_left, v_right = sorted([wx0 / s, wx1 / s])
        v_top, v_bottom = sorted([wy0 / s, wy1 / s])

        pages = range(len(reader.pages))
        if not all_pages:
            pages = [self.current_page_idx]

        for idx in pages:
            page = reader.pages[idx]

            # rotate the page content as shown on screen
            if self.rotation:
                page.rotate(self.rotation)
                page.transfer_rotation_to_content()

            # real page size after rotation (pypdf mediabox, bottom-left origin)
            mb = page.mediabox
            mw = float(mb.upper_right[0])
            mh = float(mb.upper_right[1])

            # clamp the visual region to this page's bounds
            left = max(0.0, min(v_left, mw))
            right = max(0.0, min(v_right, mw))
            lower = max(0.0, mh - min(v_bottom, mh))
            upper = max(0.0, mh - min(v_top, mh))

            page.cropbox.lower_left = (left, lower)
            page.cropbox.upper_right = (right, upper)
            writer.add_page(page)

        with open(output_path, "wb") as f:
            writer.write(f)
        return True

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
            pw, ph = self.page.get_size()
            width, height = pw, ph
            if self.rotation in (90, 270):
                width, height = ph, pw
            iw = max(1, int(width * self.scale))
            ih = max(1, int(height * self.scale))
            surface = cairo.ImageSurface(cairo.Format.ARGB32, iw, ih)
            context = cairo.Context(surface)
            context.scale(self.scale, self.scale)
            if self.rotation == 90:
                context.translate(ph, 0)
                context.rotate(math.pi / 2)
            elif self.rotation == 180:
                context.translate(pw, ph)
                context.rotate(math.pi)
            elif self.rotation == 270:
                context.translate(0, pw)
                context.rotate(-math.pi / 2)
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
            x0, top = self.widget_to_page(self.start_x, self.start_y)
            x1, bottom = self.widget_to_page(self.curr_x, self.curr_y)
            bbox = (min(x0, x1), min(top, bottom), max(x0, x1), max(top, bottom))
        if bbox:
            x0, top, x1, bottom = bbox
            wx0, wy0 = self.page_to_widget(x0, top)
            wx1, wy1 = self.page_to_widget(x1, bottom)
            rx0, ry0 = min(wx0, wx1), min(wy0, wy1)
            rx1, ry1 = max(wx0, wx1), max(wy0, wy1)
            cr.set_source_rgba(0.9, 0.2, 0.2, 0.25)
            cr.rectangle(rx0, ry0, rx1 - rx0, ry1 - ry0)
            cr.fill_preserve()
            cr.set_source_rgb(0.9, 0.1, 0.1)
            cr.set_line_width(1.5)
            cr.stroke()

            handle = 6
            cr.set_source_rgb(0.9, 0.1, 0.1)
            for hx, hy in (
                self.page_to_widget(x0, top),
                self.page_to_widget(x1, top),
                self.page_to_widget(x0, bottom),
                self.page_to_widget(x1, bottom),
                self.page_to_widget((x0 + x1) / 2, top),
                self.page_to_widget((x0 + x1) / 2, bottom),
                self.page_to_widget(x0, (top + bottom) / 2),
                self.page_to_widget(x1, (top + bottom) / 2),
            ):
                cr.rectangle(hx - handle / 2, hy - handle / 2, handle, handle)
                cr.fill()

    def _handle_at(self, x, y, tol=8):
        """Return the page-space handle name (nw/ne/sw/se/n/s/w/e) hit by (x, y).

        The bbox is stored in page coordinates; handles are named in page
        coordinates too, so the drag direction matches the page orientation.
        """
        if self.bbox is None:
            return None
        x0, top, x1, bottom = self.bbox
        handles = {
            "nw": (x0, top),
            "ne": (x1, top),
            "sw": (x0, bottom),
            "se": (x1, bottom),
            "n": ((x0 + x1) / 2, top),
            "s": ((x0 + x1) / 2, bottom),
            "w": (x0, (top + bottom) / 2),
            "e": (x1, (top + bottom) / 2),
        }
        for name, (hx, hy) in handles.items():
            wx, wy = self.page_to_widget(hx, hy)
            if abs(x - wx) <= tol and abs(y - wy) <= tol:
                return name
        return None

    def _resize_to(self, x, y, min_size=5.0):
        orig_x0, orig_top, orig_x1, orig_bottom = self.resize_bbox
        dx = x - self.move_start_x
        dy = y - self.move_start_y

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
        px, py = self.widget_to_page(x, y)
        handle = self._handle_at(x, y)
        if handle is not None:
            self.is_resizing = True
            self.resize_handle = handle
            self.resize_bbox = self.bbox
            self.move_start_x = px
            self.move_start_y = py
            self.set_cursor_from_name("default")
            return
        if self.bbox is not None and self._point_in_bbox(x, y):
            self.is_moving = True
            self.move_start_x = px
            self.move_start_y = py
            self.move_bbox = self.bbox
            self.set_cursor_from_name("move")
            return
        self.start_x = self.curr_x = x
        self.start_y = self.curr_y = y
        self.is_drawing = True

    def _point_in_bbox(self, x, y):
        x0, top, x1, bottom = self.bbox
        wx0, wy0 = self.page_to_widget(x0, top)
        wx1, wy1 = self.page_to_widget(x1, bottom)
        return (
            min(wx0, wx1) <= x <= max(wx0, wx1)
            and min(wy0, wy1) <= y <= max(wy0, wy1)
        )

    def _move_bbox_to(self, x, y):
        dx = x - self.move_start_x
        dy = y - self.move_start_y
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
            px, py = self.widget_to_page(x, y)
            self._resize_to(px, py)
        elif self.is_moving:
            px, py = self.widget_to_page(x, y)
            self._move_bbox_to(px, py)
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
            px, py = self.widget_to_page(x, y)
            self._resize_to(px, py)
            self._commit_bbox()
            return
        if self.is_moving:
            self.is_moving = False
            self.curr_x = x
            self.curr_y = y
            px, py = self.widget_to_page(x, y)
            self._move_bbox_to(px, py)
            self._commit_bbox()
            return
        if not self.is_drawing:
            return
        self.is_drawing = False
        self.curr_x = x
        self.curr_y = y
        self.queue_draw()

        x0, top = self.widget_to_page(self.start_x, self.start_y)
        x1, bottom = self.widget_to_page(self.curr_x, self.curr_y)
        x0, x1 = min(x0, x1), max(x0, x1)
        top, bottom = min(top, bottom), max(top, bottom)
        if x1 - x0 < 3 or bottom - top < 3:
            return

        self.bbox = (x0, top, x1, bottom)
        self._commit_bbox()
