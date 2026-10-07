"""Upload a recording (fast path: write file, insert row, enqueue) and poll its status."""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from tempfile import SpooledTemporaryFile
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, RedirectResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..db import Contributor, Recording, RecordingStatus, Sentence, SentenceStatus
from ..queue.tasks import process_recording
from ..settings import get_settings
from ..storage import LocalStorage, get_storage, recording_key
from .deps import DB
from .schemas import RecordingOut

router = APIRouter(prefix="/api/recordings", tags=["recordings"])
limiter = Limiter(key_func=get_remote_address)

_ALLOWED_MIME_PREFIXES = ("audio/", "video/webm", "video/mp4", "application/octet-stream")
_EXT_BY_MIME = {
    "audio/webm": "webm",
    "video/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "m4a",
    "video/mp4": "m4a",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/flac": "flac",
}


def _ext_for(upload: UploadFile) -> str:
    mime = (upload.content_type or "").split(";")[0].strip().lower()
    if mime in _EXT_BY_MIME:
        return _EXT_BY_MIME[mime]
    suffix = Path(upload.filename or "").suffix.lstrip(".").lower()
    return suffix or "bin"


def check_mime(file: UploadFile) -> str:
    mime = (file.content_type or "").split(";")[0].strip().lower()
    if mime and not mime.startswith(_ALLOWED_MIME_PREFIXES):
        raise HTTPException(415, f"Unsupported content type {mime}")
    return mime


async def store_upload(
    request: Request,
    file: UploadFile,
    *,
    lang: str,
    contributor_id: uuid.UUID,
    sentence_id: uuid.UUID | None,
    response_id: uuid.UUID | None,
) -> Recording:
    """Save the bytes, build the (uncommitted) Recording row. Shared by Speak and Talk.

    Reads with a hard size cap into a spool (memory up to 1 MB, then a temp file), then
    hands it to the storage backend off the event loop: Cloudinary uploads are blocking
    network calls; local writes are cheap either way.
    """
    s = get_settings()
    mime = check_mime(file)
    rec_id = uuid.uuid4()
    key = recording_key(lang, str(rec_id), _ext_for(file))

    written = 0
    with SpooledTemporaryFile(max_size=1024 * 1024) as spool:
        while chunk := await file.read(1024 * 256):
            written += len(chunk)
            if written > s.max_upload_bytes:
                raise HTTPException(413, "Recording too large")
            spool.write(chunk)
        if written == 0:
            raise HTTPException(400, "Empty upload")
        spool.seek(0)
        await run_in_threadpool(get_storage().save, key, spool, mime or None)

    ip = get_remote_address(request) or ""
    return Recording(
        id=rec_id,
        sentence_id=sentence_id,
        response_id=response_id,
        contributor_id=contributor_id,
        lang=lang,
        original_path=key,
        original_mime=mime or None,
        status=RecordingStatus.uploaded,
        client_ip_hash=hashlib.sha256(ip.encode()).hexdigest() if ip else None,
    )


@router.post("", response_model=RecordingOut, status_code=202)
@limiter.limit(get_settings().recording_rate_limit)
async def upload_recording(
    request: Request,
    contributor_id: Annotated[uuid.UUID, Form()],
    sentence_id: Annotated[uuid.UUID, Form()],
    file: Annotated[UploadFile, File()],
    db: DB,
) -> Recording:
    check_mime(file)
    contributor = db.get(Contributor, contributor_id)
    if contributor is None:
        raise HTTPException(404, "Unknown contributor; give consent first.")
    sentence = db.get(Sentence, sentence_id)
    if sentence is None or sentence.status != SentenceStatus.approved:
        raise HTTPException(404, "Unknown or unapproved sentence.")

    rec = await store_upload(
        request, file, lang=sentence.lang, contributor_id=contributor.id, sentence_id=sentence.id, response_id=None
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    process_recording.delay(str(rec.id))
    return rec


@router.get("/{recording_id}", response_model=RecordingOut)
def get_recording(recording_id: uuid.UUID, db: DB) -> Recording:
    rec = db.get(Recording, recording_id)
    if rec is None:
        raise HTTPException(404, "Unknown recording")
    return rec


@router.get("/{recording_id}/audio")
def get_audio(recording_id: uuid.UUID, db: DB) -> Response:
    """The processed 16 kHz WAV for the validation UI.

    Cloudinary backend: redirect to the CDN URL. Local backend: stream the file.
    """
    rec = db.get(Recording, recording_id)
    if rec is None or not rec.wav_path:
        raise HTTPException(404, "Audio not available")
    storage = get_storage()
    href = storage.url(rec.wav_path)
    if href:
        return RedirectResponse(href, status_code=302)
    if isinstance(storage, LocalStorage):
        return FileResponse(storage.path(rec.wav_path), media_type="audio/wav")
    raise HTTPException(404, "Audio not available")
