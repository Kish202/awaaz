"""Database schema for the contribution platform.

    contributors  who recorded or submitted text. Anonymous by default; a display name
                  is optional. Consent timestamps are mandatory before any contribution.
    sentences     text to be read aloud. One row per unique normalised sentence per language.
    prompts       questions the bot asks in English / Hindi ("What did you eat today?",
                  "How do you say 'it is raining'?"). Language-neutral; answered in gju or phr.
    responses     one contributor's answer to one prompt in the target language: typed text,
                  a voice clip, or both. Text that passes the read-aloud rules is also copied
                  into `sentences` so other speakers can read it.
    recordings    one audio clip by one contributor: either reading a sentence (sentence_id)
                  or answering a prompt (response_id). The worker fills in duration, the
                  16 kHz WAV path and the accept/reject decision.
    validations   a second contributor's verdict on a recording ("does the audio match the text?").

A recording that is `ready` and has `votes_to_settle` good verdicts becomes `validated`:
that is the set you export for training.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class SentenceStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class RecordingStatus(str, enum.Enum):
    uploaded = "uploaded"  # file saved, task queued
    processing = "processing"
    ready = "ready"  # passed automatic checks, awaiting human validation
    validated = "validated"  # enough "good" votes
    rejected = "rejected"  # failed automatic checks or enough "bad" votes
    failed = "failed"  # worker error; see `error`


class Verdict(str, enum.Enum):
    good = "good"
    bad = "bad"
    skip = "skip"


class Contributor(Base):
    __tablename__ = "contributors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    display_name: Mapped[str | None] = mapped_column(String(80))
    # Consent is recorded as timestamps so you can prove *when* it was given.
    consent_cc0_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consent_storage_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consent_version: Mapped[str] = mapped_column(String(16), nullable=False, default="2026-10")
    # Self-reported, optional, never verified.
    age_band: Mapped[str | None] = mapped_column(String(16))
    gender: Mapped[str | None] = mapped_column(String(16))
    region: Mapped[str | None] = mapped_column(String(80))
    native_languages: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    recordings: Mapped[list[Recording]] = relationship(back_populates="contributor")


class Sentence(Base):
    __tablename__ = "sentences"
    __table_args__ = (
        UniqueConstraint("lang", "normalized", name="uq_sentence_lang_normalized"),
        Index("ix_sentences_lang_status", "lang", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    lang: Mapped[str] = mapped_column(String(8), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[SentenceStatus] = mapped_column(
        Enum(SentenceStatus, name="sentence_status"), nullable=False, default=SentenceStatus.approved
    )
    contributor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contributors.id", ondelete="SET NULL"))
    recording_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    recordings: Mapped[list[Recording]] = relationship(back_populates="sentence")


class PromptKind(str, enum.Enum):
    question = "question"  # open question: answer freely
    translate = "translate"  # "How do you say: <sentence>?"
    word = "word"  # "What is the word for <thing>?"


class Prompt(Base):
    __tablename__ = "prompts"
    __table_args__ = (
        UniqueConstraint("text_en", name="uq_prompt_text_en"),
        Index("ix_prompts_active_category", "active", "category"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    kind: Mapped[PromptKind] = mapped_column(Enum(PromptKind, name="prompt_kind"), nullable=False)
    text_en: Mapped[str] = mapped_column(Text, nullable=False)
    text_hi: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    response_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    responses: Mapped[list[Response]] = relationship(back_populates="prompt")


class Response(Base):
    __tablename__ = "responses"
    __table_args__ = (
        Index("ix_responses_prompt", "prompt_id"),
        Index("ix_responses_contributor_lang", "contributor_id", "lang"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    prompt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("prompts.id", ondelete="CASCADE"), nullable=False)
    contributor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contributors.id", ondelete="RESTRICT"), nullable=False
    )
    lang: Mapped[str] = mapped_column(String(8), nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    normalized: Mapped[str | None] = mapped_column(Text)
    # Set when the text passed the read-aloud rules and was copied into `sentences`.
    sentence_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sentences.id", ondelete="SET NULL"))
    # Why the text was *not* copied (too_long, digits, ...) or None.
    pool_reason: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    prompt: Mapped[Prompt] = relationship(back_populates="responses")
    recordings: Mapped[list[Recording]] = relationship(back_populates="response")


class Recording(Base):
    __tablename__ = "recordings"
    __table_args__ = (
        Index("ix_recordings_status", "status"),
        Index("ix_recordings_sentence", "sentence_id"),
        Index("ix_recordings_response", "response_id"),
        Index("ix_recordings_contributor", "contributor_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    # Exactly one of sentence_id (read aloud) / response_id (answer to a prompt) is set,
    # except that an answer whose text entered the pool carries both.
    sentence_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sentences.id", ondelete="CASCADE"))
    response_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("responses.id", ondelete="CASCADE"))
    contributor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contributors.id", ondelete="RESTRICT"), nullable=False
    )
    lang: Mapped[str] = mapped_column(String(8), nullable=False)
    original_path: Mapped[str] = mapped_column(String(400), nullable=False)
    original_mime: Mapped[str | None] = mapped_column(String(80))
    wav_path: Mapped[str | None] = mapped_column(String(400))
    duration_s: Mapped[float | None] = mapped_column(Float)
    rms: Mapped[float | None] = mapped_column(Float)
    status: Mapped[RecordingStatus] = mapped_column(
        Enum(RecordingStatus, name="recording_status"), nullable=False, default=RecordingStatus.uploaded
    )
    reject_reason: Mapped[str | None] = mapped_column(String(80))
    error: Mapped[str | None] = mapped_column(Text)
    good_votes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bad_votes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    client_ip_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sentence: Mapped[Sentence | None] = relationship(back_populates="recordings")
    response: Mapped[Response | None] = relationship(back_populates="recordings")
    contributor: Mapped[Contributor] = relationship(back_populates="recordings")
    validations: Mapped[list[Validation]] = relationship(back_populates="recording")


class Validation(Base):
    __tablename__ = "validations"
    __table_args__ = (UniqueConstraint("recording_id", "contributor_id", name="uq_validation_once"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    recording_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("recordings.id", ondelete="CASCADE"), nullable=False)
    contributor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contributors.id", ondelete="CASCADE"), nullable=False
    )
    verdict: Mapped[Verdict] = mapped_column(Enum(Verdict, name="verdict"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    recording: Mapped[Recording] = relationship(back_populates="validations")
