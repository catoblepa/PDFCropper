import os
import gi


gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango
from gettext import gettext as _
from canvas import PDFCanvas
from dialogs import show_help, show_shortcuts

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
        self.set_default_size(1000, 700)

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

        btn_open = Gtk.Button(icon_name="document-open-symbolic")
        btn_open.set_tooltip_text(_("Open PDF"))
        btn_open.connect("clicked", self.on_open_clicked)
        self.header_bar.pack_start(btn_open)

        self.btn_rotate = Gtk.Button(icon_name="object-rotate-right-symbolic")
        self.btn_rotate.set_tooltip_text(_("Rotate clockwise"))
        self.btn_rotate.connect("clicked", self.on_rotate_clicked)
        self.btn_rotate.set_sensitive(False)
        self.header_bar.pack_start(self.btn_rotate)

        self.btn_save_crop = Gtk.Button(label=_("Save cropped PDF"))
        self.btn_save_crop.set_icon_name("crop-symbolic")
        self.btn_save_crop.set_tooltip_text(_("Save cropped PDF"))
        self.btn_save_crop.connect("clicked", self.on_save_crop_clicked)
        self.btn_save_crop.set_sensitive(False)
        self.btn_save_crop.add_css_class("suggested-action")
        self.header_bar.pack_start(self.btn_save_crop)

        # Sidebar toggle (right side, next to the panel)
        self.btn_toggle_sidebar = Gtk.ToggleButton()
        self.btn_toggle_sidebar.set_icon_name("sidebar-show-symbolic")
        self.btn_toggle_sidebar.set_tooltip_text(_("Toggle side panel"))
        self.btn_toggle_sidebar.add_css_class("flat")
        self.btn_toggle_sidebar.add_css_class("sidebar-toggle")
        self.btn_toggle_sidebar.connect("toggled", self.on_toggle_sidebar)
        self.header_bar.pack_end(self.btn_toggle_sidebar)

        self.settings = Gio.Settings.new("io.github.catoblepa.PDFCropper")
        sidebar_open = self.settings.get_boolean("sidebar-open")
        self.btn_toggle_sidebar.set_active(sidebar_open)

        # Sandwich menu
        self.menu_btn = Gtk.MenuButton()
        self.menu_btn.set_icon_name("open-menu-symbolic")
        self.menu_btn.set_tooltip_text(_("Menu"))
        self.menu_btn.set_menu_model(self._build_menu_model())
        self.header_bar.pack_end(self.menu_btn)

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
        btn_status_open.connect("clicked", self.on_open_clicked)
        self.status_page.set_child(btn_status_open)
        self.stack.add_named(self.status_page, "empty")

        scroll = Gtk.ScrolledWindow()
        scroll.set_kinetic_scrolling(False)
        self.canvas = PDFCanvas()
        self.canvas.on_selection_completed = self.on_bbox_extracted
        self.canvas.on_zoom_changed = self.on_zoom_changed
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
        self.btn_fit_width.connect("clicked", self.on_fit_width_clicked)
        self.btn_fit_width.set_sensitive(False)
        zoom_toolbar.append(self.btn_fit_width)

        self.btn_zoom_in = Gtk.Button(icon_name="zoom-in-symbolic")
        self.btn_zoom_in.add_css_class("circular")
        self.btn_zoom_in.add_css_class("card")
        self.btn_zoom_in.set_tooltip_text(_("Zoom in"))
        self.btn_zoom_in.connect("clicked", self.on_zoom_in_clicked)
        self.btn_zoom_in.set_sensitive(False)
        zoom_toolbar.append(self.btn_zoom_in)

        self.btn_zoom_out = Gtk.Button(icon_name="zoom-out-symbolic")
        self.btn_zoom_out.add_css_class("circular")
        self.btn_zoom_out.add_css_class("card")
        self.btn_zoom_out.set_tooltip_text(_("Zoom out"))
        self.btn_zoom_out.connect("clicked", self.on_zoom_out_clicked)
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
        side_scroll.set_min_content_width(320)
        side_scroll.set_max_content_width(360)
        side_scroll.add_css_class("side-panel")
        self.side_revealer.set_child(side_scroll)

        self.side_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.side_box.set_margin_start(7)
        self.side_box.set_margin_end(7)
        self.side_box.set_margin_top(12)
        self.side_box.set_margin_bottom(12)
        self.side_box.set_hexpand(False)
        side_scroll.set_child(self.side_box)

        # Coordinates card
        coord_card = Gtk.Frame()
        coord_card.add_css_class("card")
        coord_card.set_hexpand(True)

        coord_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        coord_box.set_margin_start(14)
        coord_box.set_margin_end(14)
        coord_box.set_margin_top(12)
        coord_box.set_margin_bottom(12)
        coord_card.set_child(coord_box)
        self.side_box.append(coord_card)

        coord_header = Gtk.Label(label=_("Coordinate fields"))
        coord_header.set_halign(Gtk.Align.START)
        coord_header.add_css_class("heading")
        coord_box.append(coord_header)

        coord_grid = Gtk.Grid()
        coord_grid.set_column_spacing(6)
        coord_grid.set_row_spacing(6)
        coord_grid.set_halign(Gtk.Align.FILL)
        coord_grid.set_hexpand(True)
        coord_box.append(coord_grid)

        self.coord_spins = {}
        self.lock_buttons = {}
        self.locks = {k: False for k in self._KEYS}
        for row, (key, label) in enumerate(
            [
                ("x0", _("left")),
                ("top", _("top")),
                ("x1", _("right")),
                ("bottom", _("bottom")),
                ("width", _("width")),
                ("height", _("height")),
            ]
        ):
            lbl = Gtk.Label(label=f"{label}:")
            lbl.set_halign(Gtk.Align.START)
            spin = Gtk.SpinButton()
            spin.set_range(0, 10000)
            spin.set_increments(1, 10)
            spin.set_digits(0)
            spin.set_value(0)
            spin.set_width_chars(5)
            spin.connect("value-changed", self.on_coord_changed)
            self.coord_spins[key] = spin

            lock_btn = Gtk.ToggleButton()
            lock_btn.set_icon_name("channel-insecure-symbolic")
            lock_btn.set_tooltip_text(_("Lock this coordinate"))
            lock_btn.add_css_class("flat")
            lock_btn.add_css_class("circular")
            lock_btn.set_valign(Gtk.Align.CENTER)
            lock_btn.connect("toggled", self.on_lock_toggled, key)
            self.lock_buttons[key] = lock_btn

            if key == "width":
                lbl.set_margin_top(15)
                spin.set_margin_top(15)
                lock_btn.set_margin_top(15)

            coord_grid.attach(lbl, 0, row, 1, 1)
            coord_grid.attach(spin, 1, row, 1, 1)
            coord_grid.attach(lock_btn, 2, row, 1, 1)

        # Extracted text card
        text_card = Gtk.Frame()
        text_card.add_css_class("card")
        text_card.set_hexpand(True)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        text_box.set_margin_start(14)
        text_box.set_margin_end(14)
        text_box.set_margin_top(6)
        text_box.set_margin_bottom(12)
        text_card.set_child(text_box)

        text_header_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        text_header_row.set_hexpand(True)

        text_header = Gtk.Label(label=_("Extracted text"))
        text_header.set_halign(Gtk.Align.START)
        text_header.set_hexpand(True)
        text_header.add_css_class("heading")
        text_header_row.append(text_header)

        btn_copy_text = Gtk.Button(icon_name="edit-copy-symbolic")
        btn_copy_text.set_tooltip_text(_("Copy extracted text"))
        btn_copy_text.add_css_class("flat")
        btn_copy_text.set_halign(Gtk.Align.END)
        btn_copy_text.set_valign(Gtk.Align.CENTER)
        btn_copy_text.connect("clicked", self.on_copy_text_clicked)
        text_header_row.append(btn_copy_text)

        text_box.append(text_header_row)

        self.text_scroll = Gtk.ScrolledWindow()
        self.text_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.text_scroll.set_max_content_height(400)
        self.text_scroll.set_vexpand(True)
        self.text_scroll.set_hexpand(True)

        self.lbl_info = Gtk.Label(
            label=_("Drag a box over the PDF to copy bounding box coordinates")
        )
        self.lbl_info.set_wrap(True)
        self.lbl_info.set_wrap_mode(Pango.WrapMode.CHAR)
        self.lbl_info.set_xalign(0)
        self.lbl_info.set_selectable(True)
        self.lbl_info.set_halign(Gtk.Align.FILL)
        self.lbl_info.set_valign(Gtk.Align.START)
        self.text_scroll.set_child(self.lbl_info)
        text_box.append(self.text_scroll)

        self.side_box.append(text_card)

        # Coordinates display card
        coord_display_card = Gtk.Frame()
        coord_display_card.add_css_class("card")
        coord_display_card.set_hexpand(True)

        coord_display_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        coord_display_box.set_margin_start(14)
        coord_display_box.set_margin_end(14)
        coord_display_box.set_margin_top(6)
        coord_display_box.set_margin_bottom(12)
        coord_display_card.set_child(coord_display_box)

        coord_display_header_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=6
        )
        coord_display_header_row.set_hexpand(True)

        coord_display_header = Gtk.Label(label=_("Coordinates"))
        coord_display_header.set_halign(Gtk.Align.START)
        coord_display_header.set_hexpand(True)
        coord_display_header.add_css_class("heading")
        coord_display_header_row.append(coord_display_header)

        btn_copy_coords = Gtk.Button(icon_name="edit-copy-symbolic")
        btn_copy_coords.set_tooltip_text(_("Copy coordinates"))
        btn_copy_coords.add_css_class("flat")
        btn_copy_coords.set_halign(Gtk.Align.END)
        btn_copy_coords.set_valign(Gtk.Align.CENTER)
        btn_copy_coords.connect("clicked", self.on_copy_coords_clicked)
        coord_display_header_row.append(btn_copy_coords)

        coord_display_box.append(coord_display_header_row)

        self.lbl_coords = Gtk.Label(label="")
        self.lbl_coords.set_xalign(0)
        self.lbl_coords.set_selectable(True)
        self.lbl_coords.set_halign(Gtk.Align.FILL)
        coord_display_box.append(self.lbl_coords)

        self.side_box.append(coord_display_card)

        # OCR card
        ocr_card = Gtk.Frame()
        ocr_card.add_css_class("card")
        ocr_card.set_hexpand(True)

        ocr_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        ocr_box.set_margin_start(14)
        ocr_box.set_margin_end(14)
        ocr_box.set_margin_top(12)
        ocr_box.set_margin_bottom(12)
        ocr_card.set_child(ocr_box)

        ocr_header = Gtk.Label(label=_("OCR"))
        ocr_header.set_halign(Gtk.Align.START)
        ocr_header.add_css_class("heading")
        ocr_box.append(ocr_header)

        ocr_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        ocr_lbl = Gtk.Label(label=_("Language:"))
        ocr_lbl.set_halign(Gtk.Align.START)
        ocr_row.append(ocr_lbl)

        self.ocr_langs = self._load_ocr_languages()
        self.ocr_model = Gtk.StringList()
        for _code, label in self.ocr_langs:
            self.ocr_model.append(label)
        self.ocr_dropdown = Gtk.DropDown.new(self.ocr_model, None)
        self.ocr_dropdown.set_selected(0)
        self.ocr_dropdown.set_hexpand(True)
        self.ocr_dropdown.set_sensitive(bool(self.ocr_langs))
        self._select_ocr_language()
        ocr_row.append(self.ocr_dropdown)
        ocr_box.append(ocr_row)

        self.side_box.append(ocr_card)

        # Drag & Drop Target
        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect("drop", self.on_file_dropped)
        self.add_controller(drop_target)

        # Keyboard shortcuts (HIG: Ctrl+O, Ctrl++, Ctrl+-, Ctrl+0)
        shortcuts = Gtk.ShortcutController()
        shortcuts.set_scope(Gtk.ShortcutScope.GLOBAL)
        shortcuts.add_shortcut(
            Gtk.Shortcut.new(
                Gtk.ShortcutTrigger.parse_string("<Ctrl>o"),
                Gtk.CallbackAction.new(self._on_open_shortcut),
            )
        )
        shortcuts.add_shortcut(
            Gtk.Shortcut.new(
                Gtk.ShortcutTrigger.parse_string("<Ctrl>w"),
                Gtk.CallbackAction.new(self._on_close_shortcut),
            )
        )
        shortcuts.add_shortcut(
            Gtk.Shortcut.new(
                Gtk.ShortcutTrigger.parse_string("<Ctrl>q"),
                Gtk.CallbackAction.new(self._on_close_shortcut),
            )
        )
        shortcuts.add_shortcut(
            Gtk.Shortcut.new(
                Gtk.ShortcutTrigger.parse_string("F1"),
                Gtk.CallbackAction.new(self._on_help_shortcut),
            )
        )
        shortcuts.add_shortcut(
            Gtk.Shortcut.new(
                Gtk.ShortcutTrigger.parse_string("<Ctrl>question"),
                Gtk.CallbackAction.new(self._on_shortcuts_shortcut),
            )
        )
        shortcuts.add_shortcut(
            Gtk.Shortcut.new(
                Gtk.ShortcutTrigger.parse_string("<Ctrl>plus"),
                Gtk.CallbackAction.new(self._on_zoom_in_shortcut),
            )
        )
        shortcuts.add_shortcut(
            Gtk.Shortcut.new(
                Gtk.ShortcutTrigger.parse_string("<Ctrl>minus"),
                Gtk.CallbackAction.new(self._on_zoom_out_shortcut),
            )
        )
        shortcuts.add_shortcut(
            Gtk.Shortcut.new(
                Gtk.ShortcutTrigger.parse_string("<Ctrl>0"),
                Gtk.CallbackAction.new(self._on_fit_width_shortcut),
            )
        )
        shortcuts.add_shortcut(
            Gtk.Shortcut.new(
                Gtk.ShortcutTrigger.parse_string("F9"),
                Gtk.CallbackAction.new(self._on_toggle_sidebar_shortcut),
            )
        )
        self.add_controller(shortcuts)

        self._updating_spins = False
        self._extracted_text = ""
        self._current_coords = ""
        self._fit_width_pending = None
        self._spin_to_key = {s: k for k, s in self.coord_spins.items()}

        self.connect("map", self._on_map)

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
        langs = [(_OCR_AUTO, _("Auto"))]
        for code in codes:
            name = _OCR_LANG_NAMES.get(code, code)
            langs.append((code, name))
        return langs

    def _select_ocr_language(self):
        """Select the language matching the system locale, if installed."""
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
            return self.ocr_langs[idx][0]
        return _OCR_AUTO

    def _ocr_text(self, x0, top, x1, bottom):
        if not PDFCanvas.tesseract_available():
            return ""
        lang = self._selected_ocr_code()
        if lang == _OCR_AUTO:
            for code in PDFCanvas.get_ocr_languages():
                text = self.canvas.ocr_region(x0, top, x1, bottom, code)
                if text:
                    return text
            return ""
        return self.canvas.ocr_region(x0, top, x1, bottom, lang)

    def on_shortcuts_activated(self, action, param):
        show_shortcuts(self)

    def on_help_activated(self, action, param):
        show_help(self)

    def on_about_activated(self, action, param):
        dialog = Adw.AboutDialog(
            application_name=_("PDFCropper"),
            application_icon="io.github.catoblepa.PDFCropper",
            version="0.1.0",
            developer_name=_("catoblepa"),
            license_type=Gtk.License.GPL_3_0,
            comments=_("PDF bounding box extractor"),
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

    def on_open_clicked(self, btn):
        dialog = Gtk.FileDialog()
        dialog.open(self, None, self.on_file_dialog_finish)

    def _on_open_shortcut(self, *args):
        self.on_open_clicked(None)
        return True

    def _on_close_shortcut(self, *args):
        self.close()
        return True

    def _on_help_shortcut(self, *args):
        self.on_help_activated(None, None)
        return True

    def _on_shortcuts_shortcut(self, *args):
        self.on_shortcuts_activated(None, None)
        return True

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
        try:
            self.canvas.load_pdf(path)
        except Exception:
            toast = Adw.Toast.new(_("Unable to open the file"))
            toast.set_timeout(3)
            self.toast_overlay.add_toast(toast)
            return
        self.stack.set_visible_child_name("content")
        filename = path.split("/")[-1]
        self.window_title.set_title(f"{filename} - {_('PDFCropper')}")
        self.btn_fit_width.set_sensitive(True)
        self.btn_rotate.set_sensitive(True)
        self.btn_save_crop.set_sensitive(False)
        self.on_zoom_changed(self.canvas.scale)

        size = self.canvas.get_page_size()
        if size:
            w, h = size
            self.coord_spins["x0"].set_range(0, w)
            self.coord_spins["x1"].set_range(0, w)
            self.coord_spins["top"].set_range(0, h)
            self.coord_spins["bottom"].set_range(0, h)
            self.coord_spins["width"].set_range(0, w)
            self.coord_spins["height"].set_range(0, h)
        self._set_spins(0, 0, 0, 0)
        self.lbl_info.set_text(
            _("Drag a box over the PDF to copy bounding box coordinates")
        )
        self.lbl_coords.set_text("")
        self._current_coords = ""
        self._extracted_text = ""
        if self._fit_width_pending is not None:
            GLib.source_remove(self._fit_width_pending)
        self._fit_width_pending = GLib.idle_add(self.canvas.fit_to_width)

    def on_zoom_changed(self, scale):
        self.btn_zoom_in.set_sensitive(self.canvas.page is not None and scale < 3.0)
        self.btn_zoom_out.set_sensitive(self.canvas.page is not None and scale > 0.5)

    def on_zoom_in_clicked(self, btn):
        if self.canvas.page is not None:
            self.canvas.zoom_about_center(1.1)

    def on_zoom_out_clicked(self, btn):
        if self.canvas.page is not None:
            self.canvas.zoom_about_center(1.0 / 1.1)

    def on_fit_width_clicked(self, btn):
        if self.canvas.page is not None:
            self.canvas.fit_to_width()

    def on_rotate_clicked(self, btn):
        if self.canvas.page is not None:
            self.canvas.rotate(90)

    def on_toggle_sidebar(self, btn):
        if hasattr(self, "settings"):
            self.settings.set_boolean("sidebar-open", btn.get_active())
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

    def on_save_crop_clicked(self, btn):
        if self.canvas.bbox is None:
            return
        dialog = Gtk.FileDialog()
        dialog.set_title(_("Save cropped PDF"))
        dialog.set_initial_name(self._suggested_crop_name())
        file_filter = Gtk.FileFilter()
        file_filter.set_name(_("PDF documents"))
        file_filter.add_mime_type("application/pdf")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(file_filter)
        dialog.set_filters(filters)
        dialog.save(self, None, self.on_save_crop_finish)

    def _suggested_crop_name(self):
        path = getattr(self.canvas, "_file_path", "") or ""
        if path.startswith("file://"):
            path = path[len("file://"):]
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
            x0, top, x1, bottom = self.canvas.bbox
            if self.canvas.save_cropped_pdf(path, x0, top, x1, bottom):
                toast = Adw.Toast.new(_("Cropped PDF saved"))
                toast.set_timeout(2)
                self.toast_overlay.add_toast(toast)
            else:
                toast = Adw.Toast.new(_("Unable to save cropped PDF"))
                toast.set_timeout(3)
                self.toast_overlay.add_toast(toast)
        except Exception:
            pass

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

    def _on_zoom_in_shortcut(self, *args):
        self.on_zoom_in_clicked(None)
        return True

    def _on_zoom_out_shortcut(self, *args):
        self.on_zoom_out_clicked(None)
        return True

    def _on_fit_width_shortcut(self, *args):
        self.on_fit_width_clicked(None)
        return True

    def _on_toggle_sidebar_shortcut(self, *args):
        self.btn_toggle_sidebar.set_active(
            not self.btn_toggle_sidebar.get_active()
        )
        return True

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
            self.coord_spins["top"].set_value(top)
            self.coord_spins["x1"].set_value(x1)
            self.coord_spins["bottom"].set_value(bottom)
            self.coord_spins["width"].set_value(max(0.0, x1 - x0))
            self.coord_spins["height"].set_value(max(0.0, bottom - top))
        finally:
            self._updating_spins = False

    # Coordinate keys -> (axis, role)
    _AXIS_ROLE = {
        "x0": ("x", "start"),
        "x1": ("x", "end"),
        "width": ("x", "size"),
        "top": ("y", "start"),
        "bottom": ("y", "end"),
        "height": ("y", "size"),
    }
    _KEYS = ("x0", "top", "x1", "bottom", "width", "height")
    _AXIS_KEYS = {"x": ("x0", "x1", "width"), "y": ("top", "bottom", "height")}

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
        top = self.coord_spins["top"].get_value()
        bottom = self.coord_spins["bottom"].get_value()

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

    def _apply_bbox(self, x0, top, x1, bottom, text=None):
        if text is None:
            text = self.canvas.extract_text(x0, top, x1, bottom)
        self.canvas.set_bbox(x0, top, x1, bottom)
        self.update_preview(x0, top, x1, bottom, text)
        self.btn_save_crop.set_sensitive(True)
        if not (text or "").strip() and self.ocr_dropdown.get_sensitive():
            self._run_ocr(x0, top, x1, bottom)

    def _run_ocr(self, x0, top, x1, bottom):
        if getattr(self, "_ocr_busy", False):
            return
        self._ocr_busy = True

        def work():
            ocr_text = self._ocr_text(x0, top, x1, bottom)
            GLib.idle_add(self._ocr_done, x0, top, x1, bottom, ocr_text)

        import threading

        threading.Thread(target=work, daemon=True).start()

    def _ocr_done(self, x0, top, x1, bottom, ocr_text):
        self._ocr_busy = False
        if ocr_text:
            self._extracted_text = ocr_text
            self.lbl_info.set_text(ocr_text)

    def update_preview(self, x0, top, x1, bottom, text):
        formatted_str = self.format_coordinates(x0, top, x1, bottom)
        self._current_coords = formatted_str
        self.lbl_coords.set_text(formatted_str)
        self._extracted_text = text or ""
        clean_text = (text or "").strip()
        if clean_text:
            preview = clean_text
        else:
            preview = _("(no text)")
        self.lbl_info.set_text(preview)

    def on_copy_text_clicked(self, btn):
        if self._extracted_text.strip():
            clipboard = self.get_clipboard()
            clipboard.set(self._extracted_text)
            toast = Adw.Toast.new(_("Text copied to clipboard"))
            toast.set_timeout(2)
            self.toast_overlay.add_toast(toast)

    def on_copy_coords_clicked(self, btn):
        if self._current_coords:
            clipboard = self.get_clipboard()
            clipboard.set(self._current_coords)
            toast = Adw.Toast.new(_("Coordinates copied to clipboard"))
            toast.set_timeout(2)
            self.toast_overlay.add_toast(toast)

    def on_bbox_extracted(self, x0, top, x1, bottom, text):
        self._set_spins(x0, top, x1, bottom)
        self._apply_bbox(x0, top, x1, bottom, text)
