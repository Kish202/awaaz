"""Pydantic request/response models shared by the routers."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

CONSENT_VERSION = "2026-10"


class ContributorCreate(BaseModel):
    display_name: str | None = Field(default=None, max_length=80)
    consent_cc0: bool
    consent_storage: bool
    age_band: str | None = Field(default=None, max_length=16)
    gender: str | None = Field(default=None, max_length=16)
    region: str | None = Field(default=None, max_length=80)
    native_languages: str | None = Field(default=None, max_length=80)

    @field_validator("display_name")
    @classmethod
    def _strip_name(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        return v or None


class ContributorOut(BaseModel):
    id: uuid.UUID
    display_name: str | None
    consent_version: str
    created_at: datetime
    recording_count: int = 0
    validation_count: int = 0
    response_count: int = 0

    model_config = {"from_attributes": True}


class SentenceOut(BaseModel):
    id: uuid.UUID
    lang: str
    text: str
    source: str | None
    recording_count: int

    model_config = {"from_attributes": True}


class SentenceBatchIn(BaseModel):
    lang: str
    sentences: list[str] = Field(min_length=1, max_length=2000)
    source: str | None = Field(default=None, max_length=200)
    contributor_id: uuid.UUID | None = None


class QueuedOut(BaseModel):
    task_id: str
    queued: int


class PromptOut(BaseModel):
    id: uuid.UUID
    category: str
    kind: str
    text_en: str
    text_hi: str
    response_count: int

    model_config = {"from_attributes": True}


class CategoryOut(BaseModel):
    key: str
    label_en: str
    label_hi: str
    prompts: int


class ResponseOut(BaseModel):
    id: uuid.UUID
    prompt_id: uuid.UUID
    lang: str
    text: str | None
    added_to_pool: bool
    pool_reason: str | None
    recording: RecordingOut | None


class RecordingOut(BaseModel):
    id: uuid.UUID
    sentence_id: uuid.UUID | None
    response_id: uuid.UUID | None = None
    lang: str
    status: str
    duration_s: float | None
    reject_reason: str | None
    created_at: datetime
    processed_at: datetime | None

    model_config = {"from_attributes": True}


class ValidationItem(BaseModel):
    recording_id: uuid.UUID
    sentence: str
    lang: str
    duration_s: float | None
    audio_url: str
    # Set when the clip answers a prompt: show the reviewer what was asked.
    prompt_en: str | None = None
    prompt_hi: str | None = None


class ValidationIn(BaseModel):
    recording_id: uuid.UUID
    contributor_id: uuid.UUID
    verdict: str  # good | bad | skip


class StatsOut(BaseModel):
    lang: str
    prompts: int
    responses: int
    sentences: int
    recordings_total: int
    recordings_ready: int
    recordings_validated: int
    hours_validated: float
    contributors: int
    queue_depth: int | None
