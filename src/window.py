import gi


gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango
from gettext import gettext as _
from canvas import PDFCanvas


class MainWindow(Adw.ApplicationWindow):

    def __init__(self, app):
        super().__init__(application=app, title="Bounds")
        self.set_default_size(1000, 700)

        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.toast_overlay.set_child(self.main_box)

        css = Gtk.CssProvider()
        css.load_from_string(
            """
            .zoom-overlay {
                background-color: transparent;
                border-radius: 9999px;
                padding: 4px;
            }
            .zoom-overlay button.circular {
                background-color: rgba(60, 60, 60, 0.85);
                color: white;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.4);
            }
            .zoom-overlay button.circular:hover {
                background-color: rgba(80, 80, 80, 0.9);
            }
            .zoom-overlay button.circular:active {
                background-color: rgba(40, 40, 40, 0.9);
            }
            .zoom-overlay button.circular:disabled {
                background-color: rgba(60, 60, 60, 0.35);
                color: alpha(white, 0.5);
            }
            """
        )
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # HeaderBar
        self.header_bar = Adw.HeaderBar()
        self.main_box.append(self.header_bar)

        self.window_title = Adw.WindowTitle(title="Bounds")
        self.header_bar.set_title_widget(self.window_title)

        btn_open = Gtk.Button(icon_name="document-open-symbolic")
        btn_open.set_tooltip_text(_("Open PDF"))
        btn_open.connect("clicked", self.on_open_clicked)
        self.header_bar.pack_start(btn_open)

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

        # Right: side panel
        side_scroll = Gtk.ScrolledWindow()
        side_scroll.set_min_content_width(280)
        side_scroll.set_max_content_width(360)
        self.paned.set_end_child(side_scroll)

        self.side_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.side_box.set_margin_start(12)
        self.side_box.set_margin_end(12)
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
        self.add_controller(shortcuts)

        self._updating_spins = False
        self._extracted_text = ""
        self._current_coords = ""
        self._spin_to_key = {s: k for k, s in self.coord_spins.items()}

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
        about_section.append(_("_About Bounds"), "win.about")
        menu.append_section(None, about_section)
        return menu

    def _add_action(self, name, callback):
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)

    def on_shortcuts_activated(self, action, param):
        dialog = Adw.ShortcutsDialog()

        general = Adw.ShortcutsSection(title=_("General"))
        for title, trigger in (
            (_("Open PDF"), "<primary>o"),
            (_("Close window"), "<primary>w"),
        ):
            general.add(Adw.ShortcutsItem(title=title, accelerator=trigger))
        dialog.add(general)

        zoom = Adw.ShortcutsSection(title=_("Zoom"))
        for title, trigger in (
            (_("Zoom in"), "<primary>plus"),
            (_("Zoom out"), "<primary>minus"),
            (_("Fit width"), "<primary>0"),
        ):
            zoom.add(Adw.ShortcutsItem(title=title, accelerator=trigger))
        pan_item = Adw.ShortcutsItem(title=_("Pan"))
        pan_item.props.subtitle = _("Middle click + drag")
        zoom.add(pan_item)
        dialog.add(zoom)

        dialog.present()

    def on_help_activated(self, action, param):
        launcher = Gtk.UriLauncher.new(
            "https://github.com/catoblepa/bounds"
        )
        launcher.launch(self, None, None, None)

    def on_about_activated(self, action, param):
        dialog = Adw.AboutDialog(
            application_name=_("Bounds"),
            application_icon="io.github.catoblepa.Bounds",
            version="0.1.0",
            developer_name=_("catoblepa"),
            license_type=Gtk.License.GPL_3_0,
            comments=_(
                "Pick PDF bounding box coordinates visually for code extraction"
            ),
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
        self.window_title.set_title(f"{filename} - Bounds")
        self.btn_fit_width.set_sensitive(True)
        self.on_zoom_changed(self.canvas.scale)
        if self.get_width() > 0:
            self.paned.set_position(self.get_width() - 320)

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
        GLib.idle_add(self.canvas.fit_to_width)

    def on_zoom_changed(self, scale):
        self.btn_zoom_in.set_sensitive(self.canvas.page is not None and scale < 3.0)
        self.btn_zoom_out.set_sensitive(self.canvas.page is not None and scale > 0.5)

    def on_zoom_in_clicked(self, btn):
        self.canvas.zoom_about_center(1.1)

    def on_zoom_out_clicked(self, btn):
        self.canvas.zoom_about_center(1.0 / 1.1)

    def on_fit_width_clicked(self, btn):
        self.canvas.fit_to_width()

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
        if self.canvas.page is not None:
            self.canvas.zoom_about_center(1.1)
        return True

    def _on_zoom_out_shortcut(self, *args):
        if self.canvas.page is not None:
            self.canvas.zoom_about_center(1.0 / 1.1)
        return True

    def _on_fit_width_shortcut(self, *args):
        if self.canvas.page is not None:
            self.canvas.fit_to_width()
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
