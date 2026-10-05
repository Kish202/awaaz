"""WER / CER on a Common Voice test split, with a per-utterance error dump.

Works for the stock Whisper model too, which gives the zero-shot baseline that a
fine-tuned model has to beat. Both references and hypotheses go through the same
`normalize_for_asr` so orthographic variants are not counted as errors.
"""

from __future__ import annotations

import csv
from pathlib import Path

from .config import LanguageConfig
from .data.common_voice import find_locale_dir, load_splits
from .text.normalize import normalize_for_asr
from .transcribe import WhisperTranscriber


def evaluate_split(
    model_path: str,
    cfg: LanguageConfig,
    cv_root: Path,
    split: str = "test",
    limit: int | None = None,
    out_tsv: Path | None = None,
    batch_size: int = 8,
) -> dict[str, float]:
    import jiwer

    locale_dir = find_locale_dir(cv_root, cfg.common_voice_locale)
    splits = load_splits(locale_dir, (split,))
    if split not in splits:
        raise FileNotFoundError(f"No {split}.tsv under {locale_dir}")
    rows = splits[split].rows
    if limit:
        rows = rows[:limit]

    transcriber = WhisperTranscriber(model_path, cfg)
    paths = [locale_dir / "clips" / r["path"] for r in rows]
    hyps_raw = [t for _, t in transcriber.transcribe_files(paths, batch_size=batch_size)]

    refs = [normalize_for_asr(r["sentence"], cfg.text) for r in rows]
    hyps = [normalize_for_asr(h, cfg.text) for h in hyps_raw]
    keep = [i for i, r in enumerate(refs) if r]
    refs_k = [refs[i] for i in keep]
    hyps_k = [hyps[i] for i in keep]

    wer = 100 * jiwer.wer(refs_k, hyps_k)
    cer = 100 * jiwer.cer(refs_k, hyps_k)

    if out_tsv:
        out_tsv.parent.mkdir(parents=True, exist_ok=True)
        with out_tsv.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter="\t", quoting=csv.QUOTE_NONE, escapechar="\\")
            w.writerow(["path", "ref", "hyp", "utt_wer"])
            for r, ref, hyp in zip(rows, refs, hyps):
                utt = 100 * jiwer.wer(ref, hyp) if ref else float("nan")
                w.writerow([r["path"], ref, hyp, f"{utt:.1f}"])

    return {"wer": wer, "cer": cer, "n": len(refs_k)}
