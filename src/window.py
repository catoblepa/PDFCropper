import os
import gi


gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk
from gettext import gettext as _
from canvas import PDFCanvas
from dialogs import show_help, show_shortcuts
from ocr import OCRController
from panels import SidePanel
from version import APP_VERSION

_OCR_AUTO = "__auto__"

_OCR_LANG_NAMES = {
    "eng": "English",
    "ita": "Italiano",
    "deu": "Deutsch",
    "fra": "Français",
    "spa": "Español",
    "por": "Português",
    "nld": "Nederlands",
    "rus": "Русский",
    "pol": "Polski",
    "tur": "Türkçe",
    "jpn": "日本語",
}

# locale base code -> tesseract language code
_LOCALE_TO_OCR = {
    "en": "eng",
    "it": "ita",
    "de": "deu",
    "fr": "fra",
    "es": "spa",
    "pt": "por",
    "nl": "nld",
    "ru": "rus",
    "pl": "pol",
    "tr": "tur",
    "ja": "jpn",
}


class MainWindow(Adw.ApplicationWindow):

    def __init__(self, app):
        super().__init__(application=app, title=_("PDFCropper"))

        self.settings = Gio.Settings.new(app.props.application_id)

        width = self.settings.get_int("window-width")
        height = self.settings.get_int("window-height")
        self.set_default_size(width, height)

        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.toast_overlay.set_child(self.main_box)

        css_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "style.css")
        if os.path.exists(css_path):
            css = Gtk.CssProvider()
            css.load_from_path(css_path)
            Gtk.StyleContext.add_provider_for_display(
                self.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

        # HeaderBar
        self.header_bar = Adw.HeaderBar()
        self.main_box.append(self.header_bar)

        self.window_title = Adw.WindowTitle(title=_("PDFCropper"))
        self.header_bar.set_title_widget(self.window_title)

        self._setup_actions()

        btn_open = Gtk.Button(icon_name="document-open-symbolic")
        btn_open.set_tooltip_text(_("Open PDF"))
        btn_open.set_action_name("win.open")
        self.header_bar.pack_start(btn_open)

        self.btn_rotate_left = Gtk.Button(icon_name="object-rotate-left-symbolic")
        self.btn_rotate_left.set_tooltip_text(_("Rotate counterclockwise"))
        self.btn_rotate_left.set_action_name("win.rotate-left")
        self.btn_rotate_left.set_sensitive(False)
        self.header_bar.pack_start(self.btn_rotate_left)

        self.btn_rotate = Gtk.Button(icon_name="object-rotate-right-symbolic")
        self.btn_rotate.set_tooltip_text(_("Rotate clockwise"))
        self.btn_rotate.set_action_name("win.rotate")
        self.btn_rotate.set_sensitive(False)
        self.header_bar.pack_start(self.btn_rotate)

        self.btn_prev_page = Gtk.Button(icon_name="go-previous-symbolic")
        self.btn_prev_page.set_tooltip_text(_("Previous page"))
        self.btn_prev_page.set_action_name("win.prev-page")
        self.btn_prev_page.set_sensitive(False)

        self.lbl_page = Gtk.Label(label="")
        self.lbl_page.add_css_class("dim-label")
        self.lbl_page.set_visible(False)

        self.btn_next_page = Gtk.Button(icon_name="go-next-symbolic")
        self.btn_next_page.set_tooltip_text(_("Next page"))
        self.btn_next_page.set_action_name("win.next-page")
        self.btn_next_page.set_sensitive(False)

        self.btn_save_crop = Gtk.Button(label=_("Save cropped PDF"))
        self.btn_save_crop.set_icon_name("crop-symbolic")
        self.btn_save_crop.set_tooltip_text(_("Save cropped PDF"))
        self.btn_save_crop.set_action_name("win.save-crop")
        self.btn_save_crop.set_sensitive(False)
        self.btn_save_crop.add_css_class("suggested-action")
        self.header_bar.pack_start(self.btn_save_crop)

        # Sidebar toggle
        self.btn_toggle_sidebar = Gtk.ToggleButton()
        self.btn_toggle_sidebar.set_icon_name("sidebar-show-symbolic")
        self.btn_toggle_sidebar.set_tooltip_text(_("Toggle side panel"))
        self.btn_toggle_sidebar.add_css_class("flat")
        self.btn_toggle_sidebar.add_css_class("sidebar-toggle")
        self.btn_toggle_sidebar.connect("toggled", self.on_toggle_sidebar)

        # Sidebar toggle, page navigation, then menu (right side)
        self.settings.bind(
            "sidebar-open", self.btn_toggle_sidebar, "active", Gio.SettingsBindFlags.DEFAULT
        )

        # Sandwich menu
        self.menu_btn = Gtk.MenuButton()
        self.menu_btn.set_icon_name("open-menu-symbolic")
        self.menu_btn.set_tooltip_text(_("Menu"))
        self.menu_btn.set_menu_model(self._build_menu_model())

        # Right side, from rightmost: toggle sidebar, menu, page navigation
        self.header_bar.pack_end(self.btn_toggle_sidebar)
        self.header_bar.pack_end(self.menu_btn)
        self.header_bar.pack_end(self.btn_next_page)
        self.header_bar.pack_end(self.lbl_page)
        self.header_bar.pack_end(self.btn_prev_page)

        # Paned canvas | side panel (always visible)
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.paned.set_wide_handle(True)
        self.paned.set_resize_start_child(True)
        self.paned.set_resize_end_child(False)
        self.paned.set_vexpand(True)
        self.main_box.append(self.paned)

        # Left: Stack (Empty status page vs Canvas)
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        self.status_page = Adw.StatusPage(
            title=_("Open a PDF"),
            description=_("Drag and drop documents here"),
            icon_name="x-office-document-symbolic",
        )
        btn_status_open = Gtk.Button(label=_("Open…"))
        btn_status_open.add_css_class("suggested-action")
        btn_status_open.add_css_class("pill")
        btn_status_open.set_halign(Gtk.Align.CENTER)
        btn_status_open.set_valign(Gtk.Align.CENTER)
        btn_status_open.set_action_name("win.open")
        self.status_page.set_child(btn_status_open)
        self.stack.add_named(self.status_page, "empty")

        scroll = Gtk.ScrolledWindow()
        scroll.set_kinetic_scrolling(False)
        self.canvas = PDFCanvas()
        self.canvas.on_selection_completed = self.on_bbox_extracted
        self.canvas.on_zoom_changed = self.on_zoom_changed
        self.canvas.on_page_changed = self.on_page_changed
        scroll.set_child(self.canvas)

        self.document_scroll = scroll
        self.pan_hadj = None
        self.pan_vadj = None
        self.pan_h_start = 0.0
        self.pan_v_start = 0.0
        pan_gesture = Gtk.GestureDrag.new()
        pan_gesture.set_button(2)
        pan_gesture.set_exclusive(True)
        pan_gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        pan_gesture.connect("drag-begin", self.on_pan_begin)
        pan_gesture.connect("drag-update", self.on_pan_update)
        pan_gesture.connect("drag-end", self.on_pan_end)
        scroll.add_controller(pan_gesture)

        self.stack.add_named(scroll, "content")
        self.stack.set_visible_child_name("empty")

        # Floating zoom toolbar (Papers style) over the content area
        self.canvas_overlay = Gtk.Overlay()
        self.canvas_overlay.set_child(self.stack)

        zoom_toolbar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        zoom_toolbar.add_css_class("zoom-overlay")
        zoom_toolbar.set_halign(Gtk.Align.END)
        zoom_toolbar.set_valign(Gtk.Align.END)
        zoom_toolbar.set_margin_end(12)
        zoom_toolbar.set_margin_bottom(12)

        self.btn_fit_width = Gtk.Button(icon_name="zoom-fit-best-symbolic")
        self.btn_fit_width.add_css_class("circular")
        self.btn_fit_width.add_css_class("card")
        self.btn_fit_width.set_tooltip_text(_("Fit width"))
        self.btn_fit_width.set_action_name("win.fit-width")
        self.btn_fit_width.set_sensitive(False)
        zoom_toolbar.append(self.btn_fit_width)

        self.btn_zoom_in = Gtk.Button(icon_name="zoom-in-symbolic")
        self.btn_zoom_in.add_css_class("circular")
        self.btn_zoom_in.add_css_class("card")
        self.btn_zoom_in.set_tooltip_text(_("Zoom in"))
        self.btn_zoom_in.set_action_name("win.zoom-in")
        self.btn_zoom_in.set_sensitive(False)
        zoom_toolbar.append(self.btn_zoom_in)

        self.btn_zoom_out = Gtk.Button(icon_name="zoom-out-symbolic")
        self.btn_zoom_out.add_css_class("circular")
        self.btn_zoom_out.add_css_class("card")
        self.btn_zoom_out.set_tooltip_text(_("Zoom out"))
        self.btn_zoom_out.set_action_name("win.zoom-out")
        self.btn_zoom_out.set_sensitive(False)
        zoom_toolbar.append(self.btn_zoom_out)

        self.canvas_overlay.add_overlay(zoom_toolbar)
        self.paned.set_start_child(self.canvas_overlay)

        # Right: side panel (collapsible)
        self.side_revealer = Gtk.Revealer()
        self.side_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)
        self.side_revealer.set_reveal_child(self.btn_toggle_sidebar.get_active())
        self.side_revealer.set_transition_duration(150)
        self.paned.set_end_child(self.side_revealer)

        side_scroll = Gtk.ScrolledWindow()
        side_scroll.set_min_content_width(300)
        side_scroll.set_max_content_width(360)
        side_scroll.add_css_class("side-panel")
        self.side_revealer.set_child(side_scroll)

        self.side_panel = SidePanel(self.on_coord_changed, self.on_lock_toggled)
        side_scroll.set_child(self.side_panel)
        self.coord_spins = self.side_panel.coord_spins
        self.lock_buttons = self.side_panel.lock_buttons
        self.locks = self.side_panel.locks
        self.lbl_text_source = self.side_panel.lbl_text_source
        self.lbl_info = self.side_panel.lbl_info
        self.ocr_dropdown = self.side_panel.ocr_dropdown
        self.ocr_model = self.side_panel.ocr_model

        self._load_ocr_languages()
        self._select_ocr_language()

        # Drag & Drop Target
        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect("drop", self.on_file_dropped)
        self.add_controller(drop_target)

        self._updating_spins = False
        self._extracted_text = ""
        self._current_coords = ""
        self._fit_width_pending = None
        self._spin_to_key = {s: k for k, s in self.coord_spins.items()}
        self._crop_all_pages = self.settings.get_boolean("crop-all-pages")

        self.ocr = OCRController(
            self.canvas, self._selected_ocr_code, self._ocr_done
        )

        self.connect("map", self._on_map)
        self.connect("close-request", self._on_close_request)

    def _on_close_request(self, widget):
        self.settings.set_int("window-width", self.get_width())
        self.settings.set_int("window-height", self.get_height())
        return False

    def _setup_actions(self):
        actions = [
            ("open", self.on_open_activated),
            ("rotate", self.on_rotate_activated),
            ("rotate-left", self.on_rotate_left_activated),
            ("prev-page", self.on_prev_page_activated),
            ("next-page", self.on_next_page_activated),
            ("save-crop", self.on_save_crop_activated),
            ("fit-width", self.on_fit_width_activated),
            ("zoom-in", self.on_zoom_in_activated),
            ("zoom-out", self.on_zoom_out_activated),
            ("toggle-sidebar", self.on_toggle_sidebar_activated),
            ("copy-text", self.on_copy_text_activated),
            ("copy-coords", self.on_copy_coords_activated),
            ("copy-coords-wh", self.on_copy_coords_wh_activated),
            ("close", self.on_close_activated),
        ]
        for name, callback in actions:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

    def on_close_activated(self, action, param):
        self.close()

    def _build_menu_model(self):
        menu = Gio.Menu()
        self._add_action("shortcuts", self.on_shortcuts_activated)
        self._add_action("help", self.on_help_activated)
        self._add_action("about", self.on_about_activated)

        main_section = Gio.Menu()
        main_section.append(_("_Keyboard Shortcuts"), "win.shortcuts")
        main_section.append(_("_Help"), "win.help")
        menu.append_section(None, main_section)

        about_section = Gio.Menu()
        about_section.append(_("_About PDFCropper"), "win.about")
        menu.append_section(None, about_section)
        return menu

    def _add_action(self, name, callback):
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)

    def _load_ocr_languages(self):
        codes = PDFCanvas.get_ocr_languages()
        self.ocr_langs = [(_OCR_AUTO, _("Auto"))]
        for code in codes:
            name = _OCR_LANG_NAMES.get(code, code)
            self.ocr_langs.append((code, name))
        model = Gtk.StringList()
        for _code, label in self.ocr_langs:
            model.append(label)
        self.ocr_model = model
        self.ocr_dropdown.set_model(self.ocr_model)
        self.ocr_dropdown.set_selected(0)
        self.ocr_dropdown.set_sensitive(bool(self.ocr_langs))

    def _select_ocr_language(self):
        """Select the saved language, falling back to the system locale."""
        saved = self.settings.get_string("ocr-language")
        for i, (lang_code, _name) in enumerate(self.ocr_langs):
            if lang_code == saved:
                self.ocr_dropdown.set_selected(i)
                return
        import locale

        raw = locale.getlocale()[0]
        if not raw:
            return
        base = raw.split("_")[0].lower()
        tess_code = _LOCALE_TO_OCR.get(base)
        if not tess_code:
            return
        for i, (lang_code, _name) in enumerate(self.ocr_langs):
            if lang_code == tess_code:
                self.ocr_dropdown.set_selected(i)
                return

    def _selected_ocr_code(self):
        idx = self.ocr_dropdown.get_selected()
        if 0 <= idx < len(self.ocr_langs):
            code = self.ocr_langs[idx][0]
            self.settings.set_string("ocr-language", code)
            return code
        return _OCR_AUTO

    def on_shortcuts_activated(self, action, param):
        show_shortcuts(self)

    def on_help_activated(self, action, param):
        show_help(self)

    def on_about_activated(self, action, param):
        dialog = Adw.AboutDialog(
            application_name=_("PDFCropper"),
            application_icon="io.github.catoblepa.PDFCropper",
            version=APP_VERSION,
            developer_name=_("catoblepa"),
            license_type=Gtk.License.GPL_3_0,
            comments=_("Crop, inspect and extract text from PDF regions"),
        )
        dialog.present(self)

    def on_lock_toggled(self, btn, key):
        if btn.get_active():
            axis_name = self._AXIS_ROLE[key][0]
            for k in self._AXIS_KEYS[axis_name]:
                if k != key:
                    self.lock_buttons[k].set_active(False)
        self.locks[key] = btn.get_active()
        self.coord_spins[key].set_sensitive(not btn.get_active())
        btn.set_icon_name(
            "channel-secure-symbolic" if btn.get_active() else "channel-insecure-symbolic"
        )

    def _file_dialog_with_last_folder(self, dialog):
        last = self.settings.get_string("last-folder")
        if last and os.path.isdir(last):
            dialog.set_initial_folder(Gio.File.new_for_path(last))

    def _remember_folder(self, path):
        if path:
            folder = os.path.dirname(path)
            if folder:
                self.settings.set_string("last-folder", folder)

    def _pdf_filter(self):
        file_filter = Gtk.FileFilter()
        file_filter.set_name(_("PDF documents"))
        file_filter.add_mime_type("application/pdf")
        return file_filter

    def on_open_activated(self, action, param):
        dialog = Gtk.FileDialog()
        self._file_dialog_with_last_folder(dialog)
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(self._pdf_filter())
        dialog.set_filters(filters)
        dialog.open(self, None, self.on_file_dialog_finish)

    def on_file_dialog_finish(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            if file:
                self._remember_folder(file.get_path())
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
        try:
            self.canvas.load_pdf(path)
        except Exception:
            toast = Adw.Toast.new(_("Unable to open the file"))
            toast.set_timeout(3)
            self.toast_overlay.add_toast(toast)
            return
        self.stack.set_visible_child_name("content")
        filename = os.path.basename(path)
        self.window_title.set_title(f"{filename} - {_('PDFCropper')}")
        self.btn_fit_width.set_sensitive(True)
        self.btn_rotate.set_sensitive(True)
        self.btn_rotate_left.set_sensitive(True)
        self.btn_save_crop.set_sensitive(False)
        self.on_zoom_changed(self.canvas.scale)
        self.lbl_page.set_visible(True)
        self.on_page_changed(self.canvas.get_current_page(), self.canvas.get_page_count())

        size = self.canvas.get_page_size()
        if size:
            w, h = size
            self.coord_spins["x0"].set_range(0, w)
            self.coord_spins["x1"].set_range(0, w)
            self.coord_spins["y0"].set_range(0, h)
            self.coord_spins["y1"].set_range(0, h)
            self.coord_spins["width"].set_range(0, w)
            self.coord_spins["height"].set_range(0, h)
        self._set_spins(0, 0, 0, 0)
        self.lbl_info.set_text(
            _("Drag a box over the PDF to copy bounding box coordinates")
        )
        self._current_coords = ""
        self._extracted_text = ""
        if self._fit_width_pending is not None:
            GLib.source_remove(self._fit_width_pending)
        self._fit_width_pending = GLib.idle_add(self.canvas.fit_to_width)

    def on_zoom_changed(self, scale):
        self.btn_zoom_in.set_sensitive(self.canvas.page is not None and scale < 3.0)
        self.btn_zoom_out.set_sensitive(self.canvas.page is not None and scale > 0.5)

    def on_zoom_in_activated(self, action, param):
        if self.canvas.page is not None:
            self.canvas.zoom_about_center(1.1)

    def on_zoom_out_activated(self, action, param):
        if self.canvas.page is not None:
            self.canvas.zoom_about_center(1.0 / 1.1)

    def on_fit_width_activated(self, action, param):
        if self.canvas.page is not None:
            self.canvas.fit_to_width()

    def on_rotate_activated(self, action, param):
        if self.canvas.page is not None:
            self.canvas.rotate(90)
            self._reapply_bbox()

    def on_rotate_left_activated(self, action, param):
        if self.canvas.page is not None:
            self.canvas.rotate(-90)
            self._reapply_bbox()

    def _reapply_bbox(self):
        if self.canvas.bbox is not None:
            x0, top, x1, bottom = self.canvas.bbox
            self._apply_bbox(x0, top, x1, bottom)

    def on_prev_page_activated(self, action, param):
        self.canvas.go_to_page(self.canvas.get_current_page() - 1)

    def on_next_page_activated(self, action, param):
        self.canvas.go_to_page(self.canvas.get_current_page() + 1)

    def on_toggle_sidebar_activated(self, action, param):
        self.btn_toggle_sidebar.set_active(
            not self.btn_toggle_sidebar.get_active()
        )

    def on_page_changed(self, idx, count):
        self.lbl_page.set_text(f"{idx + 1} / {count}")
        self.btn_prev_page.set_sensitive(idx > 0)
        self.btn_next_page.set_sensitive(idx < count - 1)
        if self.canvas.bbox is not None:
            self.lbl_info.set_text(_("Drag a box over the PDF to copy bounding box coordinates"))
            self._extracted_text = ""
            self._set_text_source(None)

    def on_toggle_sidebar(self, btn):
        if not hasattr(self, "side_revealer"):
            return
        visible = btn.get_active()
        self.side_revealer.set_reveal_child(visible)
        if visible:
            if self.get_width() > 0:
                self.paned.set_position(self.get_width() - 320)
        else:
            if self.get_width() > 0:
                self.paned.set_position(self.get_width())

    def _apply_panel_position(self):
        if self.get_width() > 0 and self.btn_toggle_sidebar.get_active():
            self.paned.set_position(self.get_width() - 320)
        return False

    def _on_map(self, widget):
        GLib.idle_add(self._apply_panel_position)

    def on_save_crop_activated(self, action, param):
        if self.canvas.bbox is None:
            return
        if self.canvas.get_page_count() > 1:
            dialog = Adw.AlertDialog()
            dialog.set_heading(_("Crop PDF"))
            dialog.set_body(
                _("Do you want to crop the current page or all pages?")
            )
            dialog.add_response("current", _("Current page"))
            dialog.add_response("all", _("All pages"))
            dialog.set_response_appearance("all", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_default_response("all")
            dialog.set_close_response("current")
            dialog.choose(self, None, self._on_crop_scope_chosen)
        else:
            self._open_save_crop_dialog()

    def _on_crop_scope_chosen(self, dialog, result):
        try:
            scope = dialog.choose_finish(result)
        except Exception:
            return
        if scope == "all":
            self._crop_all_pages = True
        elif scope == "current":
            self._crop_all_pages = False
        else:
            return
        self.settings.set_boolean("crop-all-pages", self._crop_all_pages)
        self._open_save_crop_dialog()

    def _open_save_crop_dialog(self):
        if self.canvas.bbox is None:
            return
        dialog = Gtk.FileDialog()
        dialog.set_title(_("Save cropped PDF"))
        dialog.set_initial_name(self._suggested_crop_name())
        self._file_dialog_with_last_folder(dialog)
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(self._pdf_filter())
        dialog.set_filters(filters)
        dialog.save(self, None, self.on_save_crop_finish)

    def _suggested_crop_name(self):
        path = getattr(self.canvas, "_file_path", "") or ""
        name = os.path.basename(path)
        if not name or "." not in name:
            return "cropped.pdf"
        stem, ext = name.rsplit(".", 1)
        return f"{stem}.cropped.{ext}"

    def on_save_crop_finish(self, dialog, result):
        try:
            file = dialog.save_finish(result)
            if not file:
                return
            path = file.get_path()
            if not path:
                return
            self._remember_folder(path)
            x0, top, x1, bottom = self.canvas.bbox
            all_pages = getattr(self, "_crop_all_pages", True)
            if self.canvas.save_cropped_pdf(
                path, x0, top, x1, bottom, all_pages=all_pages
            ):
                toast = Adw.Toast.new(_("Cropped PDF saved"))
                toast.set_timeout(2)
                self.toast_overlay.add_toast(toast)
            else:
                toast = Adw.Toast.new(_("Unable to save cropped PDF"))
                toast.set_timeout(3)
                self.toast_overlay.add_toast(toast)
        except Exception:
            toast = Adw.Toast.new(_("Unable to save cropped PDF"))
            toast.set_timeout(3)
            self.toast_overlay.add_toast(toast)

    def on_pan_begin(self, gesture, x, y):
        self.pan_hadj = self.document_scroll.get_hadjustment()
        self.pan_vadj = self.document_scroll.get_vadjustment()
        self.pan_h_start = self.pan_hadj.get_value()
        self.pan_v_start = self.pan_vadj.get_value()
        self.document_scroll.set_cursor_from_name("grabbing")

    def on_pan_update(self, gesture, dx, dy):
        if self.pan_hadj is not None:
            self.pan_hadj.set_value(self.pan_h_start - dx)
        if self.pan_vadj is not None:
            self.pan_vadj.set_value(self.pan_v_start - dy)

    def on_pan_end(self, gesture, x, y):
        self.document_scroll.set_cursor_from_name("default")

    @staticmethod
    def _solve_axis(values, changed, locks):
        """Solve a (start, end, size) axis keeping the locked field fixed.

        values: dict with keys 'start', 'end', 'size'
        changed: one of 'start'/'end'/'size' (the field the user edited)
        locks: dict of the same keys -> bool
        Returns an updated values dict.
        """
        v = dict(values)
        if changed == "size":
            if locks.get("end"):
                v["start"] = v["end"] - v["size"]
            else:
                v["end"] = v["start"] + v["size"]
        elif changed == "start":
            if locks.get("size"):
                v["end"] = v["start"] + v["size"]
            else:
                v["size"] = max(0.0, v["end"] - v["start"])
        elif changed == "end":
            if locks.get("size"):
                v["start"] = v["end"] - v["size"]
            else:
                v["size"] = max(0.0, v["end"] - v["start"])
        return v

    def _set_spins(self, x0, top, x1, bottom):
        self._updating_spins = True
        try:
            self.coord_spins["x0"].set_value(x0)
            self.coord_spins["y0"].set_value(top)
            self.coord_spins["x1"].set_value(x1)
            self.coord_spins["y1"].set_value(bottom)
            self.coord_spins["width"].set_value(max(0.0, x1 - x0))
            self.coord_spins["height"].set_value(max(0.0, bottom - top))
        finally:
            self._updating_spins = False

    # Coordinate keys -> (axis, role)
    _AXIS_ROLE = {
        "x0": ("x", "start"),
        "x1": ("x", "end"),
        "width": ("x", "size"),
        "y0": ("y", "start"),
        "y1": ("y", "end"),
        "height": ("y", "size"),
    }
    _AXIS_KEYS = {"x": ("x0", "x1", "width"), "y": ("y0", "y1", "height")}

    def on_coord_changed(self, spin):
        if self._updating_spins:
            return

        key = self._spin_to_key.get(spin)
        if key is None:
            return

        axis_name, changed = self._AXIS_ROLE[key]
        start_key, end_key, size_key = self._AXIS_KEYS[axis_name]

        axis = {
            "start": self.coord_spins[start_key].get_value(),
            "end": self.coord_spins[end_key].get_value(),
            "size": self.coord_spins[size_key].get_value(),
        }
        locks = {
            "start": self.locks[start_key],
            "end": self.locks[end_key],
            "size": self.locks[size_key],
        }

        axis = self._solve_axis(axis, changed, locks)

        x0 = self.coord_spins["x0"].get_value()
        x1 = self.coord_spins["x1"].get_value()
        top = self.coord_spins["y0"].get_value()
        bottom = self.coord_spins["y1"].get_value()

        if axis_name == "x":
            x0, x1 = min(axis["start"], axis["end"]), max(
                axis["start"], axis["end"]
            )
        else:
            top, bottom = min(axis["start"], axis["end"]), max(
                axis["start"], axis["end"]
            )

        self._set_spins(x0, top, x1, bottom)
        self._apply_bbox(x0, top, x1, bottom)

    def format_coordinates(self, x0, top, x1, bottom):
        return f"({x0:.0f}, {top:.0f}, {x1:.0f}, {bottom:.0f})"

    def format_coordinates_wh(self, x0, top, x1, bottom):
        return f"{x0:.0f}, {top:.0f}, {x1 - x0:.0f}, {bottom - top:.0f}"

    def _set_text_source(self, source):
        """Show a badge only when the text came from OCR (tesseract)."""
        if source == "ocr":
            self.lbl_text_source.set_text(_("OCR"))
            self.lbl_text_source.set_visible(True)
            self.lbl_text_source.add_css_class("ocr-badge")
        else:
            self.lbl_text_source.set_visible(False)
            self.lbl_text_source.remove_css_class("ocr-badge")

    def _apply_bbox(self, x0, top, x1, bottom, text=None, source=None):
        if text is None:
            text = self.canvas.extract_text(x0, top, x1, bottom)
            source = "native" if (text or "").strip() else None
        self.canvas.set_bbox(x0, top, x1, bottom)
        self.update_preview(x0, top, x1, bottom, text, source)
        self.btn_save_crop.set_sensitive(True)
        if not (text or "").strip() and self.ocr_dropdown.get_sensitive():
            self._run_ocr(x0, top, x1, bottom)

    def _run_ocr(self, x0, top, x1, bottom):
        self.ocr.run(x0, top, x1, bottom)

    def _ocr_done(self, page_idx, ocr_text):
        if self.canvas.get_current_page() != page_idx:
            return
        if ocr_text:
            self._extracted_text = ocr_text
            self.lbl_info.set_text(ocr_text)
            self._set_text_source("ocr")

    def update_preview(self, x0, top, x1, bottom, text, source=None):
        formatted_str = self.format_coordinates(x0, top, x1, bottom)
        self._current_coords = formatted_str
        self._current_bbox = (x0, top, x1, bottom)
        self._extracted_text = text or ""
        clean_text = (text or "").strip()
        if clean_text:
            preview = clean_text
        else:
            preview = _("(no text)")
        self.lbl_info.set_text(preview)
        self._set_text_source(source)

    def on_copy_text_activated(self, action, param):
        if self._extracted_text.strip():
            clipboard = self.get_clipboard()
            clipboard.set(self._extracted_text)
            toast = Adw.Toast.new(_("Text copied to clipboard"))
            toast.set_timeout(2)
            self.toast_overlay.add_toast(toast)

    def on_copy_coords_activated(self, action, param):
        if self._current_coords:
            clipboard = self.get_clipboard()
            clipboard.set(self._current_coords)
            toast = Adw.Toast.new(_("Coordinates copied to clipboard"))
            toast.set_timeout(2)
            self.toast_overlay.add_toast(toast)

    def on_copy_coords_wh_activated(self, action, param):
        if getattr(self, "_current_bbox", None):
            x0, top, x1, bottom = self._current_bbox
            clipboard = self.get_clipboard()
            clipboard.set(self.format_coordinates_wh(x0, top, x1, bottom))
            toast = Adw.Toast.new(_("Coordinates copied to clipboard"))
            toast.set_timeout(2)
            self.toast_overlay.add_toast(toast)

    def on_bbox_extracted(self, x0, top, x1, bottom, text):
        self._set_spins(x0, top, x1, bottom)
        source = "native" if (text or "").strip() else None
        self._apply_bbox(x0, top, x1, bottom, text, source)
