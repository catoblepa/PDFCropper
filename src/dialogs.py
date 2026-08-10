import gi


gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk
from gettext import gettext as _


def show_shortcuts(parent):
    dialog = Adw.ShortcutsDialog()
    dialog.set_follows_content_size(False)
    dialog.present(parent)
    GLib.idle_add(lambda: (dialog.set_content_height(500), False)[1])

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
    title = Gtk.Label(label=_("How to use PDFCropper"))
    title.set_halign(Gtk.Align.START)
    title.add_css_class("title-2")
    box.append(title)

    box.append(_help_section(
        _("Crop a PDF"),
        _(
            "Draw a box over the region you want to keep, then press "
            "<b>Save cropped PDF</b>. The result is a vector (lossless) "
            "copy of the selected area.\n\n"
            "On a single-page document the cropped file is saved "
            "immediately. On a multi-page document you choose between the "
            "current page and all pages; the same region is applied to "
            "every page, clamped to each page's bounds. The on-screen "
            "rotation is applied to the output."
        ),
        code=False,
    ))

    box.append(_help_section(
        _("Text recognition"),
        _(
            "After selecting a region, PDFCropper extracts its selectable "
            "text using Poppler, which follows the reading order of the "
            "document (horizontal, vertical or rotated text). The result "
            "appears in the Extracted text section."
        ),
        code=False,
    ))

    box.append(_help_section(
        _("OCR"),
        _(
            "When the selected region has no selectable text (scanned "
            "pages), tesseract OCR runs automatically. Pick a language in "
            "the OCR section of the side panel — the installed languages "
            "are listed there. 'Auto' matches the system locale. A badge "
            "marks results that come from OCR."
        ),
        code=False,
    ))

    box.append(_help_section(
        _("Selecting and editing the box"),
        _(
            "Draw a new box with the left mouse button. Drag an existing "
            "box to move it, or use its 8 handles to resize it. The lock "
            "buttons in the Coordinate section pin individual values so "
            "that editing a coordinate keeps the locked one fixed. "
            "Width and height are derived from the four edges."
        ),
        code=False,
    ))

    box.append(_help_section(
        _("Navigation and rotation"),
        _(
            "Flip through pages with the header buttons or Page Up / Page "
            "Down. Rotate clockwise or counterclockwise (Ctrl+Right / "
            "Ctrl+Left); the current page keeps its rotation. The selected "
            "box and its text are re-evaluated after each rotation."
        ),
        code=False,
    ))

    box.append(_help_section(
        _("Copying the coordinates"),
        _(
            "The copy button in the Coordinate section offers two formats, "
            "both in PDF points (1 point = 1/72 inch) from the top-left "
            "corner of the page:\n\n"
            "<span font_family='monospace'>(left, top, right, bottom)</span>\n"
            "<span font_family='monospace'>x, y, width, height</span>"
        ),
        code=False,
    ))

    # Example coordinates box
    example = Gtk.Label(
        label=_(
            "Example: a box from (72, 144) to (360, 288) gives\n"
            "<span font_family='monospace'>(72, 144, 360, 288)</span>\n"
            "<span font_family='monospace'>72, 144, 288, 144</span>"
        )
    )
    example.set_halign(Gtk.Align.START)
    example.add_css_class("dim-label")
    example.set_margin_bottom(4)
    example.set_use_markup(True)
    box.append(example)

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
        _("Note"),
        _(
            "width = x1 - x0 and height = bottom - top. "
            "The <span font_family='monospace'>(left, top, right, bottom)</span> "
            "format matches pdfplumber, PyMuPDF and Camelot; "
            "<span font_family='monospace'>x, y, width, height</span> "
            "matches pdftotext. Tabula expects "
            "<span font_family='monospace'>(top, left, bottom, right)</span>."
        ),
        code=False,
    ))

    dialog.present()
