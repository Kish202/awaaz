"""Anonymous contributors. Creating one is the consent step."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from ..db import Contributor, Recording, Response, Validation
from .deps import DB
from .schemas import CONSENT_VERSION, ContributorCreate, ContributorOut

router = APIRouter(prefix="/api/contributors", tags=["contributors"])


@router.post("", response_model=ContributorOut, status_code=201)
def create_contributor(body: ContributorCreate, db: DB) -> ContributorOut:
    if not (body.consent_cc0 and body.consent_storage):
        raise HTTPException(400, "Both consents are required before contributing.")
    now = datetime.now(UTC)
    c = Contributor(
        display_name=body.display_name,
        consent_cc0_at=now,
        consent_storage_at=now,
        consent_version=CONSENT_VERSION,
        age_band=body.age_band,
        gender=body.gender,
        region=body.region,
        native_languages=body.native_languages,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return _out(c, 0, 0, 0)


def _out(c: Contributor, recs: int, vals: int, answers: int) -> ContributorOut:
    return ContributorOut(
        id=c.id,
        display_name=c.display_name,
        consent_version=c.consent_version,
        created_at=c.created_at,
        recording_count=recs,
        validation_count=vals,
        response_count=answers,
    )


@router.get("/{contributor_id}", response_model=ContributorOut)
def get_contributor(contributor_id: uuid.UUID, db: DB) -> ContributorOut:
    c = db.get(Contributor, contributor_id)
    if c is None:
        raise HTTPException(404, "Unknown contributor")
    c.last_seen_at = datetime.now(UTC)
    db.commit()
    recs = db.scalar(select(func.count(Recording.id)).where(Recording.contributor_id == c.id)) or 0
    vals = db.scalar(select(func.count(Validation.id)).where(Validation.contributor_id == c.id)) or 0
    answers = db.scalar(select(func.count(Response.id)).where(Response.contributor_id == c.id)) or 0
    return _out(c, recs, vals, answers)
