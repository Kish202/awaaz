"""Unicode normalisation for Perso-Arabic (Urdu-orthography) text.

Gojri and Pahari-Pothwari are both written with Urdu conventions, and text scraped
from PDFs, Word files and the web mixes Arabic-form and Urdu-form code points for
the same letter (e.g. ي vs ی, ك vs ک, ه vs ہ). Left alone, that silently doubles
the vocabulary an ASR model has to learn and makes WER meaningless. Everything
here is deterministic and config-driven so the same rules apply to the sentence
corpus, the training targets and the evaluation references.
"""

from __future__ import annotations

import unicodedata
from collections import Counter
from collections.abc import Iterable

import regex

from ..config import TextConfig

# Arabic-form code point -> Urdu-form code point. Applied after NFKC so that
# presentation forms (U+FB50-FDFF, U+FE70-FEFF) have already been decomposed.
URDU_LETTER_MAP: dict[str, str] = {
    "\u064a": "\u06cc",  # ARABIC YEH ي -> FARSI YEH ی
    "\u0649": "\u06cc",  # ALEF MAKSURA ى -> FARSI YEH ی
    "\u0643": "\u06a9",  # ARABIC KAF ك -> KEHEH ک
    "\u0647": "\u06c1",  # ARABIC HEH ه -> HEH GOAL ہ
    "\u0629": "\u06c3",  # TEH MARBUTA ة -> TEH MARBUTA GOAL ۃ
    "\u0623": "\u0627",  # ALEF WITH HAMZA ABOVE أ -> ALEF ا
    "\u0625": "\u0627",  # ALEF WITH HAMZA BELOW إ -> ALEF ا
    "\u06c0": "\u06c1\u0621",  # HEH WITH YEH ABOVE ۀ -> ہ + ء
}

TATWEEL = "\u0640"
ZWNJ = "\u200c"
ZWJ = "\u200d"
# Characters that carry no information and must always go.
ALWAYS_DROP = {
    "\ufeff",  # BOM
    "\u200b",  # zero-width space
    "\u200e",  # LRM
    "\u200f",  # RLM
    "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",  # bidi embedding controls
    "\u2066", "\u2067", "\u2068", "\u2069",  # bidi isolates
    "\u00ad",  # soft hyphen
}

ARABIC_INDIC_DIGITS = "\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669"
EXTENDED_ARABIC_INDIC_DIGITS = "\u06f0\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7\u06f8\u06f9"
ASCII_DIGITS = "0123456789"

_TO_ASCII_DIGITS = str.maketrans(
    ARABIC_INDIC_DIGITS + EXTENDED_ARABIC_INDIC_DIGITS, ASCII_DIGITS * 2
)
_TO_URDU_DIGITS = str.maketrans(
    ASCII_DIGITS + ARABIC_INDIC_DIGITS, EXTENDED_ARABIC_INDIC_DIGITS * 2
)

# Combining marks inside the Arabic blocks: harakat, shadda, sukun, superscript alef,
# Quranic annotation signs. We detect them by Unicode category rather than listing
# ranges so new code points are handled automatically.
_ARABIC_BLOCKS = regex.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")
_WS = regex.compile(r"\s+")
_PUNCT = regex.compile(r"\p{P}+|[\u06d4\u061f\u060c\u061b\u066a\u066b\u066c]")


def _is_arabic_combining(ch: str) -> bool:
    return unicodedata.category(ch) == "Mn" and bool(_ARABIC_BLOCKS.match(ch))


def normalize(text: str, cfg: TextConfig | None = None) -> str:
    """Canonicalise orthography while keeping punctuation. Use this for sentence corpora.

    Steps, in order:
      1. NFKC (folds presentation forms and ligatures like ﷲ back to letters)
      2. drop invisible/bidi control characters and tatweel
      3. map Arabic-form letters to Urdu-form letters (unless in `preserve_chars`)
      4. optionally strip diacritics and ZWNJ
      5. normalise digits
      6. collapse whitespace
    """
    cfg = cfg or TextConfig()
    preserve = set(cfg.preserve_chars)

    text = unicodedata.normalize("NFKC", text)

    out: list[str] = []
    for ch in text:
        if ch in ALWAYS_DROP or ch == TATWEEL or ch == ZWJ:
            continue
        if ch in preserve:
            out.append(ch)
            continue
        if ch == ZWNJ:
            if not cfg.strip_zwnj:
                out.append(ch)
            continue
        if cfg.strip_diacritics and _is_arabic_combining(ch):
            continue
        out.append(URDU_LETTER_MAP.get(ch, ch))
    text = "".join(out)

    if cfg.digits == "ascii":
        text = text.translate(_TO_ASCII_DIGITS)
    elif cfg.digits == "urdu":
        text = text.translate(_TO_URDU_DIGITS)

    return _WS.sub(" ", text).strip()


def normalize_for_asr(text: str, cfg: TextConfig | None = None) -> str:
    """`normalize` plus punctuation removal. Use for training targets and WER/CER refs."""
    text = normalize(text, cfg)
    text = _PUNCT.sub(" ", text)
    return _WS.sub(" ", text).strip()


def char_inventory(texts: Iterable[str]) -> list[tuple[str, str, str, int]]:
    """Count every non-space character across `texts`.

    Returns rows of (char, U+XXXX, unicode name, count), most frequent first. Run this
    on a Common Voice sentence corpus to see which code points a language actually
    uses, spot stray Arabic-form letters, and find the language-specific letters that
    belong in `preserve_chars`.
    """
    counts: Counter[str] = Counter()
    for t in texts:
        for ch in t:
            if not ch.isspace():
                counts[ch] += 1
    rows = []
    for ch, n in counts.most_common():
        name = unicodedata.name(ch, "<unnamed>")
        rows.append((ch, f"U+{ord(ch):04X}", name, n))
    return rows
