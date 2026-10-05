"""Sentence pool: contribute text, fetch the next sentence to record."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from ..db import Recording, Sentence, SentenceStatus
from ..queue.tasks import ingest_sentences
from .deps import DB
from .schemas import QueuedOut, SentenceBatchIn, SentenceOut

router = APIRouter(prefix="/api/sentences", tags=["sentences"])


@router.post("/contribute", response_model=QueuedOut, status_code=202)
def contribute_sentences(body: SentenceBatchIn) -> QueuedOut:
    """Queue a batch of sentences for normalisation, filtering and insertion."""
    task = ingest_sentences.delay(
        body.lang, body.sentences, body.source, str(body.contributor_id) if body.contributor_id else None
    )
    return QueuedOut(task_id=task.id, queued=len(body.sentences))


@router.get("/next", response_model=list[SentenceOut])
def next_sentences(
    lang: str,
    db: DB,
    contributor_id: uuid.UUID | None = None,
    limit: int = Query(default=5, ge=1, le=20),
) -> list[Sentence]:
    """Sentences this contributor has not recorded yet, fewest recordings first.

    Ordering by `recording_count` spreads voices evenly across the corpus instead of
    letting everyone record the same first page. Random tie-break avoids two people
    online at the same time getting identical batches.
    """
    stmt = select(Sentence).where(Sentence.lang == lang, Sentence.status == SentenceStatus.approved)
    if contributor_id is not None:
        done = select(Recording.sentence_id).where(Recording.contributor_id == contributor_id)
        stmt = stmt.where(Sentence.id.not_in(done))
    stmt = stmt.order_by(Sentence.recording_count.asc(), func.random()).limit(limit)
    rows = list(db.scalars(stmt))
    if not rows:
        raise HTTPException(404, "No sentences left to record for this language. Contribute some text first.")
    return rows


@router.get("/count")
def count_sentences(lang: str, db: DB) -> dict:
    n = db.scalar(
        select(func.count(Sentence.id)).where(Sentence.lang == lang, Sentence.status == SentenceStatus.approved)
    )
    return {"lang": lang, "approved": n or 0}
