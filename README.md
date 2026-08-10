# PDFCropper

A lightweight developer utility to select, inspect, extract and crop regions of a PDF. Draw a box over any area, read the text and its bounding box coordinates, run OCR on scanned content, rotate the page, and save a cropped copy of the document.

Built with GTK 4, libadwaita, poppler-glib and tesseract.

## Features

- Open a PDF by dialog, drag & drop, or command line
- Navigate multi-page documents (Page Up / Page Down)
- Draw a box over any region; move it or resize it with 8 handles
- Extract the selectable text inside the box, using Poppler's own reading
  order (handles horizontal, vertical and rotated text)
- Automatic OCR (tesseract) when a region has no selectable text, with a
  per-language selector and an "Auto" mode that follows the system locale
- Two copy formats for the bounding box: `(left, top, right, bottom)` and
  `x, y, width, height`
- Lock individual coordinates so that editing one value keeps the locked
  edge fixed
- Zoom in/out, fit to width, and middle-click pan
- Rotate the page clockwise or counterclockwise; the selection and its text
  are re-evaluated after rotation
- Save a vector (lossless) cropped copy of the current page or all pages,
  rotated exactly as shown on screen
- Collapsible side panel (F9); window size, last folder, OCR language and
  crop scope are remembered
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

### Cropping

The main purpose of PDFCropper is to crop a region of a PDF.

1. Open a PDF.
2. Draw a box over the area you want to keep (drag to move it, use the
   8 handles to resize it).
3. Press **Save cropped PDF**.

On a single-page document the cropped file is saved immediately. On a
multi-page document you choose between cropping the current page or all
pages: the same region is applied to every page, clamped to each page's
bounds, and the on-screen rotation is applied to the output. The result is
a vector (lossless) PDF.

### Text recognition

After selecting a region, PDFCropper extracts its selectable text using
Poppler, following the reading order of the document (horizontal, vertical
or rotated text). The result appears in the **Extracted text** section.

### OCR

When the selected region has no selectable text (scanned pages), tesseract
OCR runs automatically. The **OCR** section of the side panel lists the
installed languages; pick one, or leave **Auto** to follow the system
locale. A badge marks results that come from OCR.

### Coordinates

The copy button in the **Coordinate** section offers two clipboard formats,
both in PDF points (1/72 inch) from the top-left corner of the page:

- `(left, top, right, bottom)` — matches pdfplumber, PyMuPDF and Camelot
- `x, y, width, height` — matches pdftotext

In the examples below, `{x0}`, `{top}`, `{x1}`, `{bottom}` are the four
edges and `{width} = {x1} - {x0}`, `{height} = {bottom} - {top}`.

#### pdftotext (command line, poppler-utils)

```sh
pdftotext -x {x0} -y {top} -W {width} -H {height} input.pdf -
```

#### pdfplumber (Python)

```python
import pdfplumber

with pdfplumber.open('input.pdf') as pdf:
    page = pdf.pages[0]
    text = page.crop(({x0}, {top}, {x1}, {bottom})).extract_text()
    print(text)
```

#### PyMuPDF / fitz (Python)

```python
import fitz

doc = fitz.open('input.pdf')
page = doc[0]
text = page.get_textbox(fitz.Rect({x0}, {top}, {x1}, {bottom}))
print(text)
```

#### Camelot (Python, tables)

```python
import camelot

tables = camelot.read_pdf(
    'input.pdf',
    table_areas=['{x0},{top},{x1},{bottom}'],
)
print(tables[0].df)
```

#### Tabula (Python, tables)

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

`width = x1 - x0` and `height = bottom - top`. Tabula uses `(top, left, bottom, right)` order; the `(left, top, right, bottom)` format matches pdfplumber, PyMuPDF and Camelot, and `x, y, width, height` matches pdftotext.

## License

GPL-3.0-or-later
