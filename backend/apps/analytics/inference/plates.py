"""
Iranian license-plate recognition (Phase AI-2).

Two concerns live here:

  * **Normalization + validation of Iranian plates** — pure Python, fully tested.
    Iranian civilian plates read (left→right): two digits, a Persian letter, three
    digits, then a two-digit province code, e.g. ۱۲ ب ۳۴۵ ایران ۶۷. Cameras/OCR may
    emit Persian (۰-۹) or Arabic (٠-٩) digits and Latin transliterations; we fold
    them to a canonical form so watchlist matching is reliable. Generic Western
    ALPR does NOT understand this layout — hence a dedicated module.

  * **Detector backends** — `DummyPlateDetector` (deterministic synthetic plate,
    for testing the whole ALPR pipeline without weights) and `YoloPlateOcrDetector`
    (a real plate-detect + OCR model on ONNX; optional deps, graceful). The real
    model must be trained/fine-tuned on Iranian plates; a stock model is a starting
    point only.

`RawDetection.extra["plate"]` carries the canonical plate string; the runner
turns it into a `PlateRead` + watchlist-aware `Event`.
"""
import re

from .base import Detector, RawDetection

# Digit folding: Persian and Arabic-Indic → ASCII.
_DIGITS = {
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
    "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
    "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
}

# The 20-ish letters that appear on Iranian civilian plates (Persian glyphs).
IRAN_PLATE_LETTERS = set("الف ب پ ت ث ج د ز س ش ص ط ع ف ق ک گ ل م ن و ه ی".split())

# Common Latin/word transliterations OCR might emit → canonical Persian glyph.
_LETTER_ALIASES = {
    "alef": "الف", "aleph": "الف", "a": "الف",
    "b": "ب", "p": "پ", "t": "ت", "s": "س", "sin": "س", "d": "د",
    "j": "ج", "jim": "ج", "l": "ل", "lam": "ل", "m": "م", "mim": "م",
    "n": "ن", "nun": "ن", "v": "و", "vav": "و", "h": "ه", "he": "ه",
    "y": "ی", "ye": "ی", "q": "ق", "qaf": "ق", "f": "ف", "sad": "ص",
    "ta": "ط", "ein": "ع", "gaf": "گ", "kaf": "ک", "k": "ک", "g": "گ",
}


def fold_digits(text: str) -> str:
    """Replace Persian/Arabic digits with ASCII digits."""
    return "".join(_DIGITS.get(ch, ch) for ch in text)


def normalize_plate(text: str) -> str:
    """
    Fold digits, drop the word ایران and separators/whitespace, and collapse to a
    canonical compact token used for equality/watchlist matching. Letters are kept
    as Persian glyphs (aliases mapped where recognizable).
    """
    if not text:
        return ""
    t = fold_digits(str(text)).strip().lower()
    t = t.replace("ایران", " ").replace("iran", " ")
    t = t.replace("-", " ").replace("_", " ").replace(".", " ")
    tokens = [tok for tok in re.split(r"\s+", t) if tok]
    out = []
    for tok in tokens:
        if tok in _LETTER_ALIASES:
            out.append(_LETTER_ALIASES[tok])
        else:
            out.append(tok)
    return "".join(out)


def parse_iranian_plate(text: str):
    """
    Parse a plate into its parts if it matches the Iranian civilian layout
    (2 digits, 1 letter, 3 digits, 2-digit province). Returns
    {left, letter, right, province, canonical, pretty} or None.
    """
    norm = normalize_plate(text)
    # 2 digits, one Persian letter (1-3 chars for الف/گ etc.), 3 digits, 2 digits.
    m = re.match(r"^(\d{2})([^\d]{1,3})(\d{3})(\d{2})$", norm)
    if not m:
        return None
    left, letter, right, province = m.groups()
    if letter not in IRAN_PLATE_LETTERS:
        return None
    return {
        "left": left,
        "letter": letter,
        "right": right,
        "province": province,
        "canonical": f"{left}{letter}{right}{province}",
        "pretty": f"{left} {letter} {right} - {province}",
    }


def is_valid_iranian_plate(text: str) -> bool:
    return parse_iranian_plate(text) is not None


class DummyPlateDetector(Detector):
    """Emits one deterministic Iranian plate — exercises the ALPR pipeline."""

    task = "alpr"

    @property
    def name(self):
        return getattr(self.model, "name", "") or "dummy-alpr"

    def infer(self, image_bytes, width, height):
        plate = "12ب34567"
        return [RawDetection(
            label="plate", confidence=0.92, bbox=[0.3, 0.6, 0.2, 0.08],
            extra={"plate": plate},
        )]


class YoloPlateOcrDetector(Detector):
    """
    Real ALPR: plate detection + OCR on ONNX Runtime (optional deps). Loads only
    when numpy/onnxruntime and the weights are present; otherwise unavailable so
    the runner falls back. OCR head wiring is model-specific and completed when a
    trained Iranian-plate model is deployed.
    """

    task = "alpr"

    def available(self) -> bool:
        try:
            import numpy  # noqa: F401
            import onnxruntime  # noqa: F401
        except Exception:
            return False
        path = getattr(self.model, "path", "") or ""
        return bool(path)

    def infer(self, image_bytes, width, height):  # pragma: no cover - needs real weights
        # Deployment step: run the plate-detect + OCR session, normalize each read
        # via normalize_plate/parse_iranian_plate, return RawDetection(label="plate",
        # extra={"plate": canonical}). Left explicit until a real model is provided.
        return []
