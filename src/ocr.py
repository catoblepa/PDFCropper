import threading

import gi


gi.require_version("Poppler", "0.18")
from gi.repository import GLib, Poppler


_OCR_AUTO = "__auto__"

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


class OCRController:
    """Runs tesseract OCR in a background thread on a private Poppler
    document, then reports the result on the main thread."""

    def __init__(self, canvas, get_lang, on_done):
        self.canvas = canvas
        self._get_lang = get_lang
        self._on_done = on_done
        self._busy = False

    def run(self, x0, top, x1, bottom):
        if self._busy:
            return
        file_path = getattr(self.canvas, "_file_path", None)
        if not file_path:
            return
        page_idx = self.canvas.get_current_page()
        rotation = self.canvas.rotation
        self._busy = True

        def work():
            ocr_text = self._ocr_text(
                x0, top, x1, bottom, file_path, page_idx, rotation
            )
            GLib.idle_add(self._done, page_idx, ocr_text)

        threading.Thread(target=work, daemon=True).start()

    def _ocr_text(self, x0, top, x1, bottom, file_path, page_idx, rotation):
        from canvas import PDFCanvas

        if not PDFCanvas.tesseract_available():
            return ""
        try:
            doc = Poppler.Document.new_from_file(
                GLib.filename_to_uri(file_path, None), None
            )
        except Exception:
            return ""
        scale = self.canvas.scale
        lang = self._get_lang()
        if lang == _OCR_AUTO:
            for code in PDFCanvas.get_ocr_languages():
                text = self.canvas.ocr_region(
                    x0, top, x1, bottom, code,
                    doc=doc, page_idx=page_idx, rotation=rotation, scale=scale,
                )
                if text:
                    return text
            return ""
        return self.canvas.ocr_region(
            x0, top, x1, bottom, lang,
            doc=doc, page_idx=page_idx, rotation=rotation, scale=scale,
        )

    def _done(self, page_idx, ocr_text):
        self._busy = False
        self._on_done(page_idx, ocr_text)
