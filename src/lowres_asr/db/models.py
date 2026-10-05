"""Database schema for the contribution platform.

    contributors  who recorded or submitted text. Anonymous by default; a display name
                  is optional. Consent timestamps are mandatory before any contribution.
    sentences     text to be read aloud. One row per unique normalised sentence per language.
    recordings    one audio clip of one contributor reading one sentence. The worker fills in
                  duration, the 16 kHz WAV path and the accept/reject decision.
    validations   a second contributor's verdict on a recording ("does the audio match the text?").

A recording that is `ready` and has `votes_to_settle` good verdicts becomes `validated`:
that is the set you export for training.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
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


class Recording(Base):
    __tablename__ = "recordings"
    __table_args__ = (
        Index("ix_recordings_status", "status"),
        Index("ix_recordings_sentence", "sentence_id"),
        Index("ix_recordings_contributor", "contributor_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    sentence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sentences.id", ondelete="CASCADE"), nullable=False)
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

    sentence: Mapped[Sentence] = relationship(back_populates="recordings")
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
