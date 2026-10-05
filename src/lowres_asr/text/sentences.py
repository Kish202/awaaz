"""Turn running text into Common Voice-ready sentences.

The Common Voice bottleneck for Gojri and Pahari is the sentence corpus (a few
thousand sentences each), not volunteers. This module takes raw text (typed-up
books, OCR output, transcripts) and produces a clean, deduplicated list of short
sentences that pass the Common Voice sentence rules: short, no digits, no foreign
script, no URLs or abbreviations. Every rejection carries a reason so the source
text can be fixed rather than silently discarded.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

import regex

from ..config import SentenceConfig, TextConfig
from .normalize import normalize, normalize_for_asr

_LATIN = regex.compile(r"\p{Script=Latin}")
_DIGIT = regex.compile(r"\p{Nd}")
_URL = regex.compile(r"(https?://|www\.|@[\w.]+|[\w.-]+\.(com|org|net|pk|in|edu))", regex.I)
# Anything outside Arabic script, common punctuation/symbols, inherited marks
# (harakat, ZWNJ) and whitespace.
_FOREIGN = regex.compile(r"[^\p{Script=Arabic}\p{Script=Common}\p{Script=Inherited}\s]")
# An isolated letter followed by a dot looks like an abbreviation ("ڈ۔" for ڈاکٹر).
_ABBREV = regex.compile(r"(^|\s)\p{L}[\.\u06d4](\s|$)")
# Three or more of the same character in a row is almost always an OCR/typing artefact.
_REPEAT = regex.compile(r"(.)\1{2,}")


@dataclass
class Rejection:
    sentence: str
    reason: str
    source: str = ""


@dataclass
class ExtractResult:
    accepted: list[tuple[str, str]] = field(default_factory=list)  # (sentence, source)
    rejected: list[Rejection] = field(default_factory=list)
    duplicates: int = 0

    def summary(self) -> str:
        reasons: dict[str, int] = {}
        for r in self.rejected:
            reasons[r.reason] = reasons.get(r.reason, 0) + 1
        lines = [
            f"accepted:   {len(self.accepted)}",
            f"rejected:   {len(self.rejected)}",
            f"duplicates: {self.duplicates}",
        ]
        for reason, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
            lines.append(f"  {reason:<14} {n}")
        return "\n".join(lines)


def split_sentences(text: str, terminators: Iterable[str]) -> Iterator[str]:
    """Split on the configured terminators, keeping the terminator on the sentence.

    Newlines are treated as soft boundaries only when the preceding line already
    ends in a terminator; otherwise lines are joined, since typed-up books wrap mid
    sentence.
    """
    terms = "".join(regex.escape(t) for t in terminators)
    # Join wrapped lines, then split after any run of terminators.
    joined = regex.sub(r"\s*\n\s*", " ", text)
    pattern = regex.compile(rf"[^{terms}]+[{terms}]+|[^{terms}]+$")
    for m in pattern.finditer(joined):
        s = m.group(0).strip()
        if s:
            yield s


class SentenceFilter:
    def __init__(self, cfg: SentenceConfig, text_cfg: TextConfig | None = None):
        self.cfg = cfg
        self.text_cfg = text_cfg or TextConfig()

    def check(self, sentence: str) -> str | None:
        """Return a rejection reason, or None if the sentence is acceptable."""
        cfg = self.cfg
        words = normalize_for_asr(sentence, self.text_cfg).split()
        if not words:
            return "empty"
        if len(words) < cfg.min_words:
            return "too_short"
        if len(words) > cfg.max_words:
            return "too_long"
        if cfg.reject_urls and _URL.search(sentence):
            return "url"
        if cfg.reject_digits and _DIGIT.search(sentence):
            return "digits"
        if cfg.reject_latin and _LATIN.search(sentence):
            return "latin"
        if _FOREIGN.search(sentence):
            return "foreign_char"
        if _ABBREV.search(sentence):
            return "abbreviation"
        if _REPEAT.search("".join(words)):
            return "repeat_chars"
        return None


def extract_sentences(
    sources: Iterable[tuple[str, str]],
    cfg: SentenceConfig,
    text_cfg: TextConfig | None = None,
    keep_punctuation: bool = True,
) -> ExtractResult:
    """Split, normalise, filter and deduplicate text from many sources.

    `sources` yields (source_name, raw_text). Dedup is by the ASR-normalised form so
    that sentences differing only in diacritics or punctuation count as one.
    """
    text_cfg = text_cfg or TextConfig()
    # Keep diacritics in the published sentence (readers want them) even if the ASR
    # normaliser strips them; only strip what is unambiguous noise.
    corpus_text_cfg = TextConfig(
        preserve_chars=text_cfg.preserve_chars,
        strip_diacritics=False,
        strip_zwnj=text_cfg.strip_zwnj,
        digits=text_cfg.digits,
    )
    filt = SentenceFilter(cfg, text_cfg)
    result = ExtractResult()
    seen: set[str] = set()

    for source, raw in sources:
        for sent in split_sentences(raw, cfg.terminators):
            clean = normalize(sent, corpus_text_cfg)
            if not keep_punctuation:
                clean = normalize_for_asr(clean, corpus_text_cfg)
            reason = filt.check(clean)
            if reason:
                result.rejected.append(Rejection(clean, reason, source))
                continue
            key = normalize_for_asr(clean, text_cfg)
            if key in seen:
                result.duplicates += 1
                continue
            seen.add(key)
            result.accepted.append((clean, source))
    return result
