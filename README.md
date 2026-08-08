# PDF Bounds

A lightweight developer utility to open a PDF, drag a visual box over any text region, and extract the text from that region along with its bounding box coordinates.

Built with GTK 4, libadwaita and poppler-glib.

## Features

- Open a PDF by dialog, drag & drop, or command line
- Drag a box over any text region to get its bounding box coordinates in PDF points
- Extract the text contained in the selected region
- Resize, move, or lock individual coordinates from the side panel
- Zoom in/out, fit to width, and middle-click pan

## Build

### Dependencies

- Python 3
- GTK 4 (>= 4.14)
- libadwaita (>= 1.5)
- poppler-glib (>= 0.18)
- Meson (>= 0.59) and Ninja

### Meson

```sh
meson setup build && meson compile -C build
meson install -C build
```

### Flatpak

```sh
flatpak-builder --user --install build-dir io.github.catoblepa.PDFBounds.json
```

## Usage

When you drag a box, PDF Bounds copies four numbers: `(x0, top, x1, bottom)`. They are the bounding box of the selected area in PDF points (1/72 inch), measured from the top-left corner of the page. Use them with the tools below.

### pdftotext (command line, poppler-utils)

```sh
pdftotext -x {x0} -y {top} -W {width} -H {height} input.pdf -
```

### pdfplumber (Python)

```python
import pdfplumber

with pdfplumber.open('input.pdf') as pdf:
    page = pdf.pages[0]
    text = page.crop(({x0}, {top}, {x1}, {bottom})).extract_text()
    print(text)
```

### PyMuPDF / fitz (Python)

```python
import fitz

doc = fitz.open('input.pdf')
page = doc[0]
text = page.get_textbox(fitz.Rect({x0}, {top}, {x1}, {bottom}))
print(text)
```

### Camelot (Python, tables)

```python
import camelot

tables = camelot.read_pdf(
    'input.pdf',
    table_areas=['{x0},{top},{x1},{bottom}'],
)
print(tables[0].df)
```

### Tabula (Python, tables)

```python
import tabula

df = tabula.read_pdf(
    'input.pdf',
    area=({top}, {x0}, {bottom}, {x1}),
    pages='1',
)[0]
print(df)
```

### Note

`width = x1 - x0` and `height = bottom - top`. Tabula uses `(top, left, bottom, right)` order, the other tools use `(left, top, right, bottom)`.

## License

GPL-3.0-or-later
