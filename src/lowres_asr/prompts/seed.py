"""Load the prompt bank into the `prompts` table. Idempotent: upserts on text_en."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..db import Prompt, PromptKind
from .bank import build_bank

log = logging.getLogger(__name__)


def seed_prompts(db: Session) -> dict[str, int]:
    specs = build_bank()
    rows = [
        {
            "id": uuid.uuid4(),
            "category": s.category,
            "kind": PromptKind(s.kind),
            "text_en": s.en,
            "text_hi": s.hi,
            "active": True,
            "response_count": 0,
        }
        for s in specs
    ]
    before = db.scalar(select(func.count()).select_from(Prompt)) or 0
    stmt = pg_insert(Prompt).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_prompt_text_en",
        set_={"text_hi": stmt.excluded.text_hi, "category": stmt.excluded.category, "kind": stmt.excluded.kind},
    )
    db.execute(stmt)
    db.commit()
    after = db.scalar(select(func.count()).select_from(Prompt)) or 0
    result = {"bank": len(specs), "inserted": after - before, "total": after}
    log.info("prompts seeded: %s", result)
    return result


def seed_if_empty(db: Session) -> bool:
    """Called at API start-up so a fresh deployment has questions to ask."""
    if (db.scalar(select(func.count()).select_from(Prompt)) or 0) > 0:
        return False
    seed_prompts(db)
    return True
