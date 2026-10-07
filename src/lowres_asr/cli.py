"""`lowres-asr` command line.

    lowres-asr charset   <lang> FILE...            # which code points does this text use?
    lowres-asr normalize <lang> FILE               # print normalised text
    lowres-asr sentences <lang> --out DIR FILE...  # build a Common Voice sentence corpus
    lowres-asr cv-stats  <lang> --cv-root DIR      # summarise a Common Voice release
    lowres-asr train     <lang> --cv-root DIR --out DIR
    lowres-asr evaluate  <lang> --cv-root DIR --model PATH
    lowres-asr transcribe <lang> --model PATH FILE...
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections.abc import Iterator
from pathlib import Path

from .config import load_config


def _read_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as e:  # pragma: no cover
            raise SystemExit("PDF input needs `pip install -e '.[pdf]'`") from e
        return "\n".join((page.extract_text() or "") for page in PdfReader(str(path)).pages)
    return path.read_text(encoding="utf-8", errors="replace")


def _iter_sources(paths: list[Path]) -> Iterator[tuple[str, str]]:
    for p in paths:
        if p.is_dir():
            for child in sorted(p.rglob("*")):
                if child.suffix.lower() in {".txt", ".md", ".pdf"}:
                    yield child.name, _read_text(child)
        else:
            yield p.name, _read_text(p)


def cmd_charset(args: argparse.Namespace) -> None:
    from .text.normalize import char_inventory

    texts = [t for _, t in _iter_sources(args.files)]
    for ch, cp, name, n in char_inventory(texts):
        print(f"{n:>8}  {cp}  {ch}  {name}")


def cmd_normalize(args: argparse.Namespace) -> None:
    from .text.normalize import normalize, normalize_for_asr

    cfg = load_config(args.lang)
    fn = normalize_for_asr if args.asr else normalize
    for line in _read_text(args.file).splitlines():
        out = fn(line, cfg.text)
        if out:
            print(out)


def cmd_sentences(args: argparse.Namespace) -> None:
    from .text.sentences import extract_sentences

    cfg = load_config(args.lang)
    result = extract_sentences(_iter_sources(args.files), cfg.sentences, cfg.text)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "sentences.txt").write_text(
        "\n".join(s for s, _ in result.accepted) + "\n", encoding="utf-8"
    )
    with (out / "sentences.tsv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", quoting=csv.QUOTE_NONE, escapechar="\\")
        w.writerow(["sentence", "source"])
        w.writerows(result.accepted)
    with (out / "rejected.tsv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", quoting=csv.QUOTE_NONE, escapechar="\\")
        w.writerow(["reason", "source", "sentence"])
        for r in result.rejected:
            w.writerow([r.reason, r.source, r.sentence])

    print(result.summary())
    print(f"\nwrote {out / 'sentences.txt'}, {out / 'sentences.tsv'}, {out / 'rejected.tsv'}")


def cmd_cv_stats(args: argparse.Namespace) -> None:
    from .data.common_voice import cv_stats, find_locale_dir

    cfg = load_config(args.lang)
    locale_dir = find_locale_dir(Path(args.cv_root), cfg.common_voice_locale)
    print(cv_stats(locale_dir, cfg))


def cmd_train(args: argparse.Namespace) -> None:
    from .data.common_voice import find_locale_dir
    from .train.whisper import train

    cfg = load_config(args.lang)
    if args.base_model:
        cfg.train.base_model = args.base_model
    if args.max_steps:
        cfg.train.max_steps = args.max_steps
    locale_dir = find_locale_dir(Path(args.cv_root), cfg.common_voice_locale)
    train(cfg, locale_dir, Path(args.out), max_train_samples=args.max_train_samples)


def cmd_evaluate(args: argparse.Namespace) -> None:
    from .metrics import evaluate_split

    cfg = load_config(args.lang)
    res = evaluate_split(
        args.model,
        cfg,
        Path(args.cv_root),
        split=args.split,
        limit=args.limit,
        out_tsv=Path(args.out_tsv) if args.out_tsv else None,
        batch_size=args.batch_size,
    )
    print(f"model: {args.model}")
    print(f"split: {args.split}  n={res['n']}")
    print(f"WER:   {res['wer']:.2f}")
    print(f"CER:   {res['cer']:.2f}")


def cmd_seed_prompts(args: argparse.Namespace) -> None:
    from .db import SessionLocal
    from .prompts.seed import seed_prompts

    db = SessionLocal()
    try:
        r = seed_prompts(db)
    finally:
        db.close()
    print(f"bank {r['bank']} prompts · inserted {r['inserted']} · table now {r['total']}")


def cmd_transcribe(args: argparse.Namespace) -> None:
    from .transcribe import WhisperTranscriber

    cfg = load_config(args.lang)
    t = WhisperTranscriber(args.model, cfg)
    for path, text in t.transcribe_files(args.files, batch_size=args.batch_size):
        print(f"{path}\t{text}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="lowres-asr", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def lang_arg(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("lang", help="language config: gju, phr, or a YAML path")

    s = sub.add_parser("charset", help="count code points used in text files")
    lang_arg(s)
    s.add_argument("files", nargs="+", type=Path)
    s.set_defaults(func=cmd_charset)

    s = sub.add_parser("normalize", help="print normalised text")
    lang_arg(s)
    s.add_argument("file", type=Path)
    s.add_argument("--asr", action="store_true", help="also strip punctuation")
    s.set_defaults(func=cmd_normalize)

    s = sub.add_parser("sentences", help="build a Common Voice sentence corpus from text")
    lang_arg(s)
    s.add_argument("files", nargs="+", type=Path, help="text/PDF files or directories")
    s.add_argument("--out", required=True, help="output directory")
    s.set_defaults(func=cmd_sentences)

    s = sub.add_parser("cv-stats", help="summarise a local Common Voice release")
    lang_arg(s)
    s.add_argument("--cv-root", required=True)
    s.set_defaults(func=cmd_cv_stats)

    s = sub.add_parser("train", help="fine-tune Whisper on Common Voice")
    lang_arg(s)
    s.add_argument("--cv-root", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--base-model", default=None)
    s.add_argument("--max-steps", type=int, default=None)
    s.add_argument("--max-train-samples", type=int, default=None, help="for smoke tests")
    s.set_defaults(func=cmd_train)

    s = sub.add_parser("evaluate", help="WER/CER of a model on a Common Voice split")
    lang_arg(s)
    s.add_argument("--cv-root", required=True)
    s.add_argument("--model", required=True, help="HF id or local checkpoint dir")
    s.add_argument("--split", default="test")
    s.add_argument("--limit", type=int, default=None)
    s.add_argument("--batch-size", type=int, default=8)
    s.add_argument("--out-tsv", default=None, help="write per-utterance ref/hyp/WER")
    s.set_defaults(func=cmd_evaluate)

    s = sub.add_parser("transcribe", help="transcribe audio files")
    lang_arg(s)
    s.add_argument("--model", required=True)
    s.add_argument("--batch-size", type=int, default=8)
    s.add_argument("files", nargs="+", type=Path)
    s.set_defaults(func=cmd_transcribe)

    s = sub.add_parser("seed-prompts", help="load/refresh the Talk question bank into PostgreSQL")
    s.set_defaults(func=cmd_seed_prompts)

    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except (FileNotFoundError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
