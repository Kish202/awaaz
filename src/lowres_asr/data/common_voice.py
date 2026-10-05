"""Read a locally extracted Mozilla Common Voice release.

Common Voice releases are downloaded manually from the Mozilla Data Collective
(an account is required) and extracted to e.g.

    data/raw/cv-corpus-26.0-2026-06-12/gju/
        clips/*.mp3
        train.tsv  dev.tsv  test.tsv  validated.tsv  invalidated.tsv  other.tsv
        validated_sentences.tsv

This module reads those TSVs with the standard library (no heavy imports) and,
when asked, builds Hugging Face `Dataset` objects with decoded 16 kHz audio.
"""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ..config import LanguageConfig
from ..text.normalize import normalize_for_asr

if TYPE_CHECKING:  # pragma: no cover
    from datasets import DatasetDict

SPLITS = ("train", "dev", "test")


@dataclass
class CommonVoiceSplit:
    name: str
    rows: list[dict[str, str]]

    @property
    def clip_paths(self) -> list[str]:
        return [r["path"] for r in self.rows]

    @property
    def sentences(self) -> list[str]:
        return [r["sentence"] for r in self.rows]


def find_locale_dir(root: Path, locale: str) -> Path:
    """Accept either the locale directory itself or the release root containing it."""
    root = Path(root)
    if (root / "clips").is_dir():
        return root
    cand = root / locale
    if (cand / "clips").is_dir():
        return cand
    # One level deeper: data/raw/cv-corpus-*/<locale>
    for p in sorted(root.glob(f"*/{locale}")):
        if (p / "clips").is_dir():
            return p
    raise FileNotFoundError(
        f"Could not find a Common Voice '{locale}' directory with a clips/ folder under {root}"
    )


def read_cv_tsv(path: Path) -> list[dict[str, str]]:
    with Path(path).open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        return [dict(r) for r in reader]


def load_splits(locale_dir: Path, splits: tuple[str, ...] = SPLITS) -> dict[str, CommonVoiceSplit]:
    out = {}
    for name in splits:
        tsv = locale_dir / f"{name}.tsv"
        if tsv.exists():
            out[name] = CommonVoiceSplit(name, read_cv_tsv(tsv))
    return out


def cv_stats(locale_dir: Path, cfg: LanguageConfig) -> str:
    """Human-readable summary: clips, speakers, unique sentences, demographic skew."""
    splits = load_splits(locale_dir, SPLITS + ("validated",))
    lines = [f"Common Voice {cfg.name} ({cfg.code}) at {locale_dir}", ""]
    for name, split in splits.items():
        speakers = {r.get("client_id", "") for r in split.rows}
        uniq = {normalize_for_asr(s, cfg.text) for s in split.sentences}
        genders = Counter(r.get("gender", "") or "unknown" for r in split.rows)
        ages = Counter(r.get("age", "") or "unknown" for r in split.rows)
        lines.append(f"[{name}] clips={len(split.rows)} speakers={len(speakers)} unique_sentences={len(uniq)}")
        lines.append(f"  gender: {dict(genders.most_common())}")
        lines.append(f"  age:    {dict(ages.most_common())}")
    if "train" in splits and "test" in splits:
        train_s = {normalize_for_asr(s, cfg.text) for s in splits["train"].sentences}
        test_s = {normalize_for_asr(s, cfg.text) for s in splits["test"].sentences}
        overlap = len(train_s & test_s)
        lines.append("")
        lines.append(f"train/test sentence overlap: {overlap} (should be 0; CV guarantees this)")
        train_spk = {r.get("client_id") for r in splits["train"].rows}
        test_spk = {r.get("client_id") for r in splits["test"].rows}
        lines.append(f"train/test speaker overlap:  {len(train_spk & test_spk)}")
    return "\n".join(lines)


def load_common_voice(locale_dir: Path, cfg: LanguageConfig) -> DatasetDict:
    """Build a `DatasetDict` with columns: audio (16 kHz), sentence, text, client_id.

    `text` is the ASR-normalised target. Requires the `[train]` extra.
    """
    from datasets import Audio, Dataset, DatasetDict

    locale_dir = Path(locale_dir)
    splits = load_splits(locale_dir)
    if not splits:
        raise FileNotFoundError(f"No train/dev/test TSVs under {locale_dir}")

    dd = {}
    for name, split in splits.items():
        records = {
            "audio": [str(locale_dir / "clips" / p) for p in split.clip_paths],
            "sentence": split.sentences,
            "text": [normalize_for_asr(s, cfg.text) for s in split.sentences],
            "client_id": [r.get("client_id", "") for r in split.rows],
        }
        ds = Dataset.from_dict(records)
        ds = ds.cast_column("audio", Audio(sampling_rate=cfg.train.sampling_rate))
        dd[name] = ds
    return DatasetDict(dd)
