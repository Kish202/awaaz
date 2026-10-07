"""Peer validation: does the audio match the sentence?"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from ..db import (
    Contributor,
    Prompt,
    Recording,
    RecordingStatus,
    Response,
    Sentence,
    Validation,
    Verdict,
)
from ..settings import get_settings
from .deps import DB
from .schemas import ValidationIn, ValidationItem

router = APIRouter(prefix="/api/validations", tags=["validations"])


@router.get("/next", response_model=list[ValidationItem])
def next_to_validate(
    lang: str,
    contributor_id: uuid.UUID,
    db: DB,
    limit: int = Query(default=5, ge=1, le=20),
) -> list[ValidationItem]:
    """Ready recordings by *other* people that this contributor has not judged yet.

    A clip is reviewable when there is text to compare it with: the sentence it reads,
    or the typed answer that came with it. Voice-only answers wait for transcription.
    """
    judged = select(Validation.recording_id).where(Validation.contributor_id == contributor_id)
    text_col = func.coalesce(Sentence.text, Response.text)
    stmt = (
        select(Recording, text_col, Prompt.text_en, Prompt.text_hi)
        .outerjoin(Sentence, Sentence.id == Recording.sentence_id)
        .outerjoin(Response, Response.id == Recording.response_id)
        .outerjoin(Prompt, Prompt.id == Response.prompt_id)
        .where(
            Recording.lang == lang,
            Recording.status == RecordingStatus.ready,
            Recording.contributor_id != contributor_id,
            Recording.id.not_in(judged),
            text_col.is_not(None),
        )
        .order_by((Recording.good_votes + Recording.bad_votes).asc(), func.random())
        .limit(limit)
    )
    rows = db.execute(stmt).all()
    return [
        ValidationItem(
            recording_id=rec.id,
            sentence=text,
            lang=rec.lang,
            duration_s=rec.duration_s,
            audio_url=f"/api/recordings/{rec.id}/audio",
            prompt_en=p_en,
            prompt_hi=p_hi,
        )
        for rec, text, p_en, p_hi in rows
    ]


@router.post("", status_code=201)
def submit_validation(body: ValidationIn, db: DB) -> dict:
    try:
        verdict = Verdict(body.verdict)
    except ValueError as e:
        raise HTTPException(400, "verdict must be good, bad or skip") from e
    if db.get(Contributor, body.contributor_id) is None:
        raise HTTPException(404, "Unknown contributor")
    rec = db.get(Recording, body.recording_id)
    if rec is None:
        raise HTTPException(404, "Unknown recording")
    if rec.contributor_id == body.contributor_id:
        raise HTTPException(400, "You cannot validate your own recording")

    db.add(Validation(recording_id=rec.id, contributor_id=body.contributor_id, verdict=verdict))
    try:
        db.flush()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(409, "Already validated this recording") from e

    if verdict == Verdict.good:
        rec.good_votes += 1
    elif verdict == Verdict.bad:
        rec.bad_votes += 1

    settle = get_settings().votes_to_settle
    if rec.status == RecordingStatus.ready:
        if rec.good_votes >= settle and rec.good_votes > rec.bad_votes:
            rec.status = RecordingStatus.validated
        elif rec.bad_votes >= settle and rec.bad_votes > rec.good_votes:
            rec.status = RecordingStatus.rejected
            rec.reject_reason = "peer_rejected"
    db.commit()
    return {"recording_id": str(rec.id), "status": rec.status.value, "good": rec.good_votes, "bad": rec.bad_votes}
