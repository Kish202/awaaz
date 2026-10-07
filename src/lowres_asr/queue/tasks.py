"""Background jobs.

process_recording  convert the uploaded clip to 16 kHz mono WAV with ffmpeg, measure it,
                   and accept or reject it. Runs once per upload.
ingest_sentences   normalise, filter and dedupe a batch of contributed sentences against
                   the database. Runs once per Sentence Studio submission.
"""

from __future__ import annotations

import array
import logging
import math
import subprocess
import uuid
import wave
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..config import load_config
from ..db import Recording, RecordingStatus, Sentence, SentenceStatus, SessionLocal
from ..settings import get_settings
from ..storage import get_storage, wav_key_for
from ..text.normalize import normalize, normalize_for_asr
from ..text.sentences import SentenceFilter
from .celery_app import celery

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- audio


def _to_wav16k(src: Path, dst: Path, sample_rate: int) -> None:
    """Decode anything ffmpeg understands (webm/opus, m4a, mp3, wav...) to 16-bit mono PCM."""
    cmd = [
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(src),
        "-ac", "1", "-ar", str(sample_rate), "-sample_fmt", "s16",
        "-af", (
            "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.3,areverse,"
            "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.3,areverse"
        ),
        str(dst),
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=60)


def _measure(wav_path: Path) -> tuple[float, float]:
    """Return (duration_seconds, rms as fraction of full scale) using only the stdlib."""
    with wave.open(str(wav_path), "rb") as w:
        n = w.getnframes()
        rate = w.getframerate()
        frames = w.readframes(n)
    if n == 0:
        return 0.0, 0.0
    samples = array.array("h")
    samples.frombytes(frames)
    sq = sum(s * s for s in samples)
    rms = math.sqrt(sq / len(samples)) / 32768.0
    return n / rate, rms


@celery.task(bind=True, name="lowres_asr.queue.tasks.process_recording", max_retries=2, default_retry_delay=5)
def process_recording(self, recording_id: str) -> dict:
    s = get_settings()
    storage = get_storage()
    db = SessionLocal()
    try:
        rec = db.get(Recording, uuid.UUID(recording_id))
        if rec is None:
            return {"id": recording_id, "status": "missing"}
        if rec.status not in (RecordingStatus.uploaded, RecordingStatus.processing, RecordingStatus.failed):
            return {"id": recording_id, "status": rec.status.value, "note": "already processed"}

        rec.status = RecordingStatus.processing
        db.commit()

        wav_key = wav_key_for(rec.original_path)
        with TemporaryDirectory(prefix="awaaz-") as tmp:
            work = Path(tmp)
            src = storage.fetch(rec.original_path, work / f"src.{rec.original_path.rsplit('.', 1)[-1]}")
            dst = work / "out.16k.wav"
            try:
                _to_wav16k(src, dst, s.target_sample_rate)
            except subprocess.CalledProcessError as e:
                rec.status = RecordingStatus.rejected
                rec.reject_reason = "undecodable"
                rec.error = e.stderr.decode(errors="replace")[-500:]
                rec.processed_at = datetime.now(UTC)
                db.commit()
                return {"id": recording_id, "status": "rejected", "reason": "undecodable"}

            duration, rms = _measure(dst)
            with dst.open("rb") as f:
                storage.save(wav_key, f, "audio/wav")
        rec.wav_path = wav_key
        rec.duration_s = round(duration, 3)
        rec.rms = round(rms, 5)

        # Answers to questions may run long; read-aloud clips are one short sentence.
        max_seconds = s.max_response_seconds if rec.response_id else s.max_clip_seconds

        # The ffmpeg filter trims leading/trailing silence, so an all-silent clip comes
        # out with (near) zero length. Report that as silence, not as too short.
        if duration < 0.05 or rms < s.silence_rms_threshold:
            rec.status, rec.reject_reason = RecordingStatus.rejected, "silent"
        elif duration < s.min_clip_seconds:
            rec.status, rec.reject_reason = RecordingStatus.rejected, "too_short"
        elif duration > max_seconds:
            rec.status, rec.reject_reason = RecordingStatus.rejected, "too_long"
        else:
            rec.status = RecordingStatus.ready
            if rec.sentence_id is not None:
                sentence = db.get(Sentence, rec.sentence_id)
                if sentence is not None:
                    sentence.recording_count += 1

        rec.processed_at = datetime.now(UTC)
        db.commit()
        log.info("recording %s -> %s (%.2fs, rms %.4f)", recording_id, rec.status.value, duration, rms)
        return {"id": recording_id, "status": rec.status.value, "duration_s": rec.duration_s}
    except Exception as exc:  # noqa: BLE001 - record then retry
        db.rollback()
        rec = db.get(Recording, uuid.UUID(recording_id))
        if rec is not None:
            rec.status = RecordingStatus.failed
            rec.error = f"{type(exc).__name__}: {exc}"[:1000]
            db.commit()
        raise self.retry(exc=exc)
    finally:
        db.close()


# ---------------------------------------------------------------------------- text


@celery.task(name="lowres_asr.queue.tasks.ingest_sentences")
def ingest_sentences(lang: str, sentences: list[str], source: str | None, contributor_id: str | None) -> dict:
    cfg = load_config(lang)
    filt = SentenceFilter(cfg.sentences, cfg.text)
    # Keep diacritics in the stored text (readers want them); dedupe on the stripped form.
    display_cfg = replace(cfg.text, strip_diacritics=False)
    rows: dict[str, dict] = {}
    rejected = 0
    for raw in sentences:
        clean = normalize(raw, display_cfg)
        if not clean or filt.check(clean):
            rejected += 1
            continue
        key = normalize_for_asr(clean, cfg.text)
        rows.setdefault(
            key,
            {
                "id": uuid.uuid4(),
                "lang": lang,
                "text": clean,
                "normalized": key,
                "source": (source or "")[:200] or None,
                "status": SentenceStatus.approved,
                "contributor_id": uuid.UUID(contributor_id) if contributor_id else None,
                "recording_count": 0,
            },
        )
    if not rows:
        return {"inserted": 0, "duplicates": 0, "rejected": rejected}

    db = SessionLocal()
    try:
        stmt = pg_insert(Sentence).values(list(rows.values())).on_conflict_do_nothing(
            constraint="uq_sentence_lang_normalized"
        )
        result = db.execute(stmt)
        db.commit()
        inserted = result.rowcount or 0
        return {"inserted": inserted, "duplicates": len(rows) - inserted, "rejected": rejected}
    finally:
        db.close()
