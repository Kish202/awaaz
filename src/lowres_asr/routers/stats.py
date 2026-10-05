"""Live counts for the dashboard, plus an export of validated (audio, text) pairs."""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from ..db import Recording, RecordingStatus, Sentence, SentenceStatus
from ..settings import get_settings
from ..storage import get_storage
from .deps import DB
from .schemas import StatsOut

router = APIRouter(prefix="/api", tags=["stats"])


def _queue_depth() -> int | None:
    try:
        import redis

        r = redis.Redis.from_url(get_settings().redis_url, socket_connect_timeout=0.5)
        return int(r.llen("recordings")) + int(r.llen("text"))
    except Exception:  # noqa: BLE001 - stats must never fail the page
        return None


@router.get("/stats", response_model=StatsOut)
def stats(lang: str, db: DB) -> StatsOut:
    def count(stmt):
        return db.scalar(stmt) or 0

    sentences = count(
        select(func.count(Sentence.id)).where(Sentence.lang == lang, Sentence.status == SentenceStatus.approved)
    )
    total = count(select(func.count(Recording.id)).where(Recording.lang == lang))
    ready = count(
        select(func.count(Recording.id)).where(Recording.lang == lang, Recording.status == RecordingStatus.ready)
    )
    validated = count(
        select(func.count(Recording.id)).where(
            Recording.lang == lang, Recording.status == RecordingStatus.validated
        )
    )
    seconds = db.scalar(
        select(func.coalesce(func.sum(Recording.duration_s), 0.0)).where(
            Recording.lang == lang, Recording.status == RecordingStatus.validated
        )
    ) or 0.0
    contributors = count(
        select(func.count(func.distinct(Recording.contributor_id))).where(Recording.lang == lang)
    )
    return StatsOut(
        lang=lang,
        sentences=sentences,
        recordings_total=total,
        recordings_ready=ready,
        recordings_validated=validated,
        hours_validated=round(seconds / 3600, 2),
        contributors=contributors,
        queue_depth=_queue_depth(),
    )


@router.get("/export/{lang}.tsv")
def export_tsv(
    lang: str,
    db: DB,
    authorization: str | None = Header(default=None),
) -> StreamingResponse:
    """Validated (wav_path, text, speaker) rows: the training manifest. Admin only."""
    token = get_settings().admin_token
    if not token or authorization != f"Bearer {token}":
        raise HTTPException(401, "Admin token required")

    stmt = (
        select(Recording.wav_path, Sentence.text, Recording.contributor_id, Recording.duration_s)
        .join(Sentence, Sentence.id == Recording.sentence_id)
        .where(Recording.lang == lang, Recording.status == RecordingStatus.validated)
        .order_by(Recording.created_at)
    )

    storage = get_storage()

    def gen():
        buf = io.StringIO()
        w = csv.writer(buf, delimiter="\t", quoting=csv.QUOTE_NONE, escapechar="\\")
        w.writerow(["path", "sentence", "speaker_id", "duration_s"])
        yield buf.getvalue()
        for key, text, spk, dur in db.execute(stmt):
            buf.seek(0)
            buf.truncate()
            # Cloudinary: a downloadable https URL. Local: the key relative to STORAGE_DIR.
            w.writerow([storage.url(key) or key, text, str(spk), f"{dur:.3f}" if dur is not None else ""])
            yield buf.getvalue()

    return StreamingResponse(
        gen(), media_type="text/tab-separated-values", headers={"Content-Disposition": f"attachment; filename={lang}.tsv"}
    )
