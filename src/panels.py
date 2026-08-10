import gi


gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk, Pango
from gettext import gettext as _


class SidePanel(Adw.PreferencesPage):
    """Right-hand side panel: coordinate fields, extracted text, coordinates
    display and OCR language selector."""

    COORD_KEYS = (
        ("x0", _("left")),
        ("y0", _("top")),
        ("x1", _("right")),
        ("y1", _("bottom")),
        ("width", _("width")),
        ("height", _("height")),
    )

    def __init__(self, on_coord_changed, on_lock_toggled):
        super().__init__()
        self.coord_spins = {}
        self.lock_buttons = {}
        self.locks = {k: False for k, _label in self.COORD_KEYS}

        self._build_coord_group(on_coord_changed, on_lock_toggled)
        self._build_text_group()
        self._build_ocr_group()

    def _header_row(self, title):
        row = Adw.PreferencesRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.add_css_class("side-header-box")
        label = Gtk.Label(label=title, xalign=0)
        label.add_css_class("heading")
        label.set_hexpand(True)
        box.append(label)
        row.set_child(box)
        return row, box

    def _build_coord_group(self, on_coord_changed, on_lock_toggled):
        group = Adw.PreferencesGroup()
        header, header_box = self._header_row(_("Coordinate"))

        copy_menu = Gio.Menu()
        copy_menu.append(_("Copy (left, top, right, bottom)"), "win.copy-coords")
        copy_menu.append(_("Copy (x, y, width, height)"), "win.copy-coords-wh")

        btn_copy_coords = Gtk.MenuButton(icon_name="edit-copy-symbolic")
        btn_copy_coords.set_tooltip_text(_("Copy coordinates"))
        btn_copy_coords.add_css_class("flat")
        btn_copy_coords.set_valign(Gtk.Align.CENTER)
        btn_copy_coords.set_menu_model(copy_menu)
        header_box.append(btn_copy_coords)

        group.add(header)

        coord_row = Adw.PreferencesRow()
        grid = Gtk.Grid()
        grid.set_column_spacing(6)
        grid.set_row_spacing(6)
        grid.set_halign(Gtk.Align.FILL)
        grid.set_hexpand(True)
        grid.add_css_class("side-content-box")
        coord_row.set_child(grid)
        group.add(coord_row)
        self.add(group)

        for row, (key, label) in enumerate(self.COORD_KEYS):
            lbl = Gtk.Label(label=f"{label}:")
            lbl.set_halign(Gtk.Align.START)
            spin = Gtk.SpinButton()
            spin.set_range(0, 10000)
            spin.set_increments(1, 10)
            spin.set_digits(0)
            spin.set_value(0)
            spin.set_width_chars(5)
            spin.connect("value-changed", on_coord_changed)
            self.coord_spins[key] = spin

            lock_btn = Gtk.ToggleButton()
            lock_btn.set_icon_name("channel-insecure-symbolic")
            lock_btn.set_tooltip_text(_("Lock this coordinate"))
            lock_btn.add_css_class("flat")
            lock_btn.add_css_class("circular")
            lock_btn.set_valign(Gtk.Align.CENTER)
            lock_btn.connect("toggled", on_lock_toggled, key)
            self.lock_buttons[key] = lock_btn

            if key == "width":
                lbl.add_css_class("coord-sep")
                spin.add_css_class("coord-sep")
                lock_btn.add_css_class("coord-sep")

            grid.attach(lbl, 0, row, 1, 1)
            grid.attach(spin, 1, row, 1, 1)
            grid.attach(lock_btn, 2, row, 1, 1)

    def _build_text_group(self):
        group = Adw.PreferencesGroup()
        header, box = self._header_row(_("Extracted text"))

        self.lbl_text_source = Gtk.Label(label="")
        self.lbl_text_source.set_visible(False)
        self.lbl_text_source.set_valign(Gtk.Align.CENTER)
        self.lbl_text_source.add_css_class("badge")
        box.append(self.lbl_text_source)

        btn_copy_text = Gtk.Button(icon_name="edit-copy-symbolic")
        btn_copy_text.set_tooltip_text(_("Copy extracted text"))
        btn_copy_text.add_css_class("flat")
        btn_copy_text.set_valign(Gtk.Align.CENTER)
        btn_copy_text.set_action_name("win.copy-text")
        box.append(btn_copy_text)
        group.add(header)

        text_row = Adw.PreferencesRow()
        text_row.set_vexpand(True)
        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        text_box.add_css_class("side-content-box")
        text_box.set_vexpand(True)
        text_row.set_child(text_box)
        group.add(text_row)
        group.set_vexpand(True)
        self.add(group)

        self.text_scroll = Gtk.ScrolledWindow()
        self.text_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
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
        self.lbl_info.set_valign(Gtk.Align.FILL)
        self.text_scroll.set_child(self.lbl_info)
        text_box.append(self.text_scroll)

    def _build_ocr_group(self):
        group = Adw.PreferencesGroup()
        header, _header_box = self._header_row(_("OCR language"))
        group.add(header)

        ocr_row = Adw.PreferencesRow()
        ocr_row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        ocr_row_box.add_css_class("side-content-box")
        ocr_row.set_child(ocr_row_box)
        group.add(ocr_row)
        self.add(group)

        self.ocr_model = Gtk.StringList()
        self.ocr_dropdown = Gtk.DropDown.new(self.ocr_model, None)
        self.ocr_dropdown.set_selected(0)
        self.ocr_dropdown.set_hexpand(True)
        self.ocr_dropdown.set_sensitive(False)
        ocr_row_box.append(self.ocr_dropdown)
