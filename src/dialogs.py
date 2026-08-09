import gi


gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk
from gettext import gettext as _


def show_shortcuts(parent):
    dialog = Adw.ShortcutsDialog()

    general = Adw.ShortcutsSection(title=_("General"))
    for title, trigger in (
        (_("Open PDF"), "<primary>o"),
        (_("Close window"), "<primary>w"),
        (_("Quit"), "<primary>q"),
        (_("Help"), "F1"),
        (_("Toggle side panel"), "F9"),
    ):
        general.add(Adw.ShortcutsItem(title=title, accelerator=trigger))
    dialog.add(general)

    nav = Adw.ShortcutsSection(title=_("Navigation"))
    for title, trigger in (
        (_("Previous page"), "Page_Up"),
        (_("Next page"), "Page_Down"),
    ):
        nav.add(Adw.ShortcutsItem(title=title, accelerator=trigger))
    dialog.add(nav)

    zoom = Adw.ShortcutsSection(title=_("Zoom"))
    for title, trigger in (
        (_("Zoom in"), "<primary>plus"),
        (_("Zoom out"), "<primary>minus"),
        (_("Fit width"), "<primary>0"),
        (_("Rotate clockwise"), "<primary>Right"),
        (_("Rotate counterclockwise"), "<primary>Left"),
        (_("Keyboard shortcuts"), "<primary>question"),
    ):
        zoom.add(Adw.ShortcutsItem(title=title, accelerator=trigger))
    pan_item = Adw.ShortcutsItem(title=_("Pan"))
    pan_item.props.subtitle = _("Middle click + drag")
    zoom.add(pan_item)
    dialog.add(zoom)

    dialog.present()


def _help_section(title, content, code=True):
    frame = Gtk.Frame()
    frame.add_css_class("card")
    frame.set_halign(Gtk.Align.FILL)

    vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    vbox.set_margin_start(14)
    vbox.set_margin_end(14)
    vbox.set_margin_top(12)
    vbox.set_margin_bottom(12)
    frame.set_child(vbox)

    header = Gtk.Label(label=title)
    header.set_halign(Gtk.Align.START)
    header.add_css_class("heading")
    vbox.append(header)

    if code:
        label = Gtk.Label(label=content)
        label.set_halign(Gtk.Align.START)
        label.set_selectable(True)
        label.add_css_class("monospace")
        label.set_wrap(False)
        label.set_justify(Gtk.Justification.LEFT)
        vbox.append(label)
    else:
        label = Gtk.Label(label=content)
        label.set_wrap(True)
        label.set_xalign(0)
        vbox.append(label)

    return frame


def show_help(parent):
    dialog = Adw.Dialog(title=_("Help"))
    dialog.set_content_width(640)
    dialog.set_content_height(600)

    toolbar = Adw.ToolbarView()
    dialog.set_child(toolbar)

    header_bar = Adw.HeaderBar(show_title=False)
    toolbar.add_top_bar(header_bar)

    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    toolbar.set_content(scroll)

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    box.set_margin_start(24)
    box.set_margin_end(24)
    box.set_margin_top(20)
    box.set_margin_bottom(20)
    scroll.set_child(box)

    # Title inside the content
    title = Gtk.Label(label=_("How to use the extracted coordinates"))
    title.set_halign(Gtk.Align.START)
    title.add_css_class("title-2")
    box.append(title)

    intro = Gtk.Label(
        label=_(
            "Draw a box over the text you are interested in. PDFCropper "
            "copies four numbers to the clipboard:\n\n"
            "<span font_family='monospace'>(x0, top, x1, bottom)</span>\n\n"
            "They define the bounding box of the selected area in PDF "
            "points (1 point = 1/72 inch), measured from the top-left "
            "corner of the page. "
            "<b>x0</b> is the left edge, <b>top</b> the upper edge, "
            "<b>x1</b> the right edge and <b>bottom</b> the lower edge "
            "of the box."
        )
    )
    intro.set_wrap(True)
    intro.set_xalign(0)
    intro.set_margin_bottom(4)
    intro.set_use_markup(True)
    box.append(intro)

    # Example coordinates box
    example = Gtk.Label(
        label=_(
            "Example: a box from (72, 144) to (360, 288) gives\n"
            "<span font_family='monospace'>(72, 144, 360, 288)</span>"
        )
    )
    example.set_halign(Gtk.Align.START)
    example.add_css_class("dim-label")
    example.set_margin_bottom(4)
    example.set_use_markup(True)
    box.append(example)

    box.append(_help_section(
        _("Use in the command line"),
        _(
            "pdftotext from poppler-utils can crop a region directly. "
            "It needs the top-left corner plus the width and height:"
        ),
        code=False,
    ))
    box.append(_help_section(
        _("pdftotext (command line)"),
        "pdftotext -x {x0} -y {top} -W {width} -H {height} input.pdf -",
    ))
    box.append(_help_section(
        _("pdfplumber (Python)"),
        "import pdfplumber\n\n"
        "with pdfplumber.open('input.pdf') as pdf:\n"
        "    page = pdf.pages[0]\n"
        "    text = page.crop(({x0}, {top}, {x1}, {bottom})).extract_text()\n"
        "    print(text)",
    ))
    box.append(_help_section(
        _("PyMuPDF / fitz (Python)"),
        "import fitz\n\n"
        "doc = fitz.open('input.pdf')\n"
        "page = doc[0]\n"
        "text = page.get_textbox(fitz.Rect({x0}, {top}, {x1}, {bottom}))\n"
        "print(text)",
    ))
    box.append(_help_section(
        _("Camelot (Python, tables)"),
        "import camelot\n\n"
        "tables = camelot.read_pdf(\n"
        "    'input.pdf',\n"
        "    table_areas=['{x0},{top},{x1},{bottom}'],\n"
        ")\n"
        "print(tables[0].df)",
    ))
    box.append(_help_section(
        _("Tabula (Python, tables)"),
        "import tabula\n\n"
        "df = tabula.read_pdf(\n"
        "    'input.pdf',\n"
        "    area=({top}, {x0}, {bottom}, {x1}),\n"
        "    pages='1',\n"
        ")[0]\n"
        "print(df)",
    ))
    box.append(_help_section(
        _("OCR"),
        _(
            "When the region contains no selectable text (for example a "
            "scanned page), PDFCropper runs tesseract automatically. Pick the "
            "language in the side panel; a badge appears when the result "
            "comes from OCR."
        ),
        code=False,
    ))
    box.append(_help_section(
        _("Crop"),
        _(
            "Draw a box, then use Save cropped PDF. On a multi-page document "
            "you can choose to crop only the current page or all pages; the "
            "current rotation is applied to the result."
        ),
        code=False,
    ))
    box.append(_help_section(
        _("Note"),
        _(
            "width = x1 - x0 and height = bottom - top. "
            "Tabula expects (top, left, bottom, right) order; "
            "the other tools use (left, top, right, bottom), "
            "same as what PDFCropper copies."
        ),
        code=False,
    ))

    dialog.present()
