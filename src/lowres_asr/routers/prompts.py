"""Talk: the bot asks in English/Hindi, the contributor answers in Gojri/Pahari.

GET  /api/prompts/next        questions this contributor has not answered in this language
GET  /api/prompts/categories  topic list for the picker
POST /api/responses           an answer: typed text, a voice clip, or both (multipart)
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..config import load_config
from ..db import Contributor, Prompt, Recording, Response, Sentence, SentenceStatus
from ..prompts.bank import CATEGORY_LABELS
from ..queue.tasks import process_recording
from ..text.normalize import normalize, normalize_for_asr
from ..text.sentences import SentenceFilter
from .deps import DB
from .recordings import check_mime, limiter, store_upload
from .schemas import CategoryOut, PromptOut, RecordingOut, ResponseOut

router = APIRouter(prefix="/api", tags=["talk"])

MAX_TEXT_CHARS = 1000


@router.get("/prompts/next", response_model=list[PromptOut])
def next_prompts(
    lang: str,
    contributor_id: uuid.UUID,
    db: DB,
    category: str | None = Query(default=None, max_length=40),
    kind: str | None = Query(default=None, pattern="^(question|translate|word)$"),
    limit: int = Query(default=5, ge=1, le=20),
) -> list[Prompt]:
    """Unanswered prompts, least-answered first, randomised within ties."""
    answered = select(Response.prompt_id).where(
        Response.contributor_id == contributor_id, Response.lang == lang
    )
    stmt = select(Prompt).where(Prompt.active.is_(True), Prompt.id.not_in(answered))
    if category:
        stmt = stmt.where(Prompt.category == category)
    if kind:
        stmt = stmt.where(Prompt.kind == kind)
    stmt = stmt.order_by(Prompt.response_count.asc(), func.random()).limit(limit)
    rows = list(db.scalars(stmt))
    if not rows:
        raise HTTPException(404, "You have answered every question here. Try another topic.")
    return rows


@router.get("/prompts/categories", response_model=list[CategoryOut])
def categories(db: DB) -> list[CategoryOut]:
    counts = dict(
        db.execute(
            select(Prompt.category, func.count()).where(Prompt.active.is_(True)).group_by(Prompt.category)
        ).all()
    )
    out = []
    for key, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        en, hi = CATEGORY_LABELS.get(key, (key.replace("_", " ").title(), key))
        out.append(CategoryOut(key=key, label_en=en, label_hi=hi, prompts=n))
    return out


@router.get("/prompts/count")
def prompt_count(db: DB) -> dict:
    return {"prompts": db.scalar(select(func.count()).select_from(Prompt).where(Prompt.active.is_(True))) or 0}


@router.post("/responses", response_model=ResponseOut, status_code=202)
@limiter.limit("30/minute")
async def submit_response(
    request: Request,
    db: DB,
    contributor_id: Annotated[uuid.UUID, Form()],
    prompt_id: Annotated[uuid.UUID, Form()],
    lang: Annotated[str, Form(max_length=8)],
    text: Annotated[str | None, Form(max_length=MAX_TEXT_CHARS)] = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> ResponseOut:
    text = (text or "").strip() or None
    if text is None and file is None:
        raise HTTPException(400, "Type an answer, record one, or both.")
    if file is not None:
        check_mime(file)

    contributor = db.get(Contributor, contributor_id)
    if contributor is None:
        raise HTTPException(404, "Unknown contributor; give consent first.")
    prompt = db.get(Prompt, prompt_id)
    if prompt is None or not prompt.active:
        raise HTTPException(404, "Unknown prompt")
    try:
        cfg = load_config(lang)
    except FileNotFoundError as e:
        raise HTTPException(400, f"Unknown language {lang!r}") from e

    resp = Response(id=uuid.uuid4(), prompt_id=prompt.id, contributor_id=contributor.id, lang=lang)
    sentence_id: uuid.UUID | None = None

    if text is not None:
        # Keep diacritics in what we store; dedupe on the stripped form.
        clean = normalize(text, replace(cfg.text, strip_diacritics=False))
        resp.text = clean or text
        resp.normalized = normalize_for_asr(clean, cfg.text) if clean else None
        reason = SentenceFilter(cfg.sentences, cfg.text).check(clean) if clean else "empty"
        if reason is None:
            # Good enough to be read aloud by others: copy into the sentence pool.
            stmt = (
                pg_insert(Sentence)
                .values(
                    id=uuid.uuid4(),
                    lang=lang,
                    text=clean,
                    normalized=resp.normalized,
                    source=f"talk:{prompt.kind.value}",
                    status=SentenceStatus.approved,
                    contributor_id=contributor.id,
                    recording_count=0,
                )
                .on_conflict_do_nothing(constraint="uq_sentence_lang_normalized")
                .returning(Sentence.id)
            )
            sentence_id = db.execute(stmt).scalar_one_or_none()
            if sentence_id is None:  # already in the pool: link to the existing row
                sentence_id = db.scalar(
                    select(Sentence.id).where(Sentence.lang == lang, Sentence.normalized == resp.normalized)
                )
            resp.sentence_id = sentence_id
        else:
            resp.pool_reason = reason

    db.add(resp)
    prompt.response_count += 1
    db.flush()

    rec: Recording | None = None
    if file is not None:
        rec = await store_upload(
            request,
            file,
            lang=lang,
            contributor_id=contributor.id,
            sentence_id=sentence_id,
            response_id=resp.id,
        )
        db.add(rec)

    db.commit()
    if rec is not None:
        db.refresh(rec)
        process_recording.delay(str(rec.id))

    return ResponseOut(
        id=resp.id,
        prompt_id=prompt.id,
        lang=lang,
        text=resp.text,
        added_to_pool=sentence_id is not None,
        pool_reason=resp.pool_reason,
        recording=RecordingOut.model_validate(rec) if rec is not None else None,
    )
