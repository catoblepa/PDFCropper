# PDFCropper

A lightweight developer utility to select, inspect, extract and crop regions of a PDF. Draw a box over any area, read the text and its bounding box coordinates, run OCR on scanned content, rotate the page, and save a cropped copy of the document.

Built with GTK 4, libadwaita, poppler-glib and tesseract.

## Features

- Open a PDF by dialog, drag & drop, or command line
- Draw a box over any region to get its bounding box coordinates in PDF points
- Extract the text contained in the selected region
- Run OCR (tesseract) on scanned or image-only content, with multiple languages
- Resize, move, or lock individual coordinates from the side panel
- Zoom in/out, fit to width, and middle-click pan
- Rotate the page clockwise for easier reading and OCR
- Save a vector cropped copy of the selected region, rotated exactly as shown
- Side panel can be hidden (F9), the last state is remembered
- English and Italian interface

## Build

### Dependencies

- Python 3
- GTK 4 (>= 4.14)
- libadwaita (>= 1.5)
- poppler-glib (>= 0.18)
- tesseract (>= 5) with language data
- pypdf
- Meson (>= 0.59) and Ninja

### Flatpak

```sh
flatpak-builder --user --install build-dir io.github.catoblepa.PDFCropper.json
```

## Usage

When you draw a box, PDFCropper copies four numbers: `(x0, top, x1, bottom)`. They are the bounding box of the selected area in PDF points (1/72 inch), measured from the top-left corner of the page. Use them with the tools below.

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
