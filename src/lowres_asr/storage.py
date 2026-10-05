"""Where audio bytes live.

Two backends behind one four-method interface:

  LocalStorage       development default. Files under STORAGE_DIR.
  CloudinaryStorage  production. Set STORAGE_BACKEND=cloudinary and CLOUDINARY_URL.

A *key* is backend-neutral and is what the database stores:

    <lang>/<yyyy>/<mm>/<recording_id>.<ext>        the upload as received
    <lang>/<yyyy>/<mm>/<recording_id>.16k.wav      written by the worker

On Cloudinary the key maps to public_id ``<folder>/<key-without-ext>`` with the
extension as the asset format, under ``resource_type="video"`` (Cloudinary files
all audio under "video"). The API and the worker share nothing but the database
and Cloudinary, so they can run on different machines.
"""

from __future__ import annotations

import logging
import shutil
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO, Protocol
from urllib.parse import urlparse

from .settings import get_settings

log = logging.getLogger(__name__)


class Storage(Protocol):
    def save(self, key: str, stream: BinaryIO, content_type: str | None = None) -> str:
        """Persist the bytes under *key* and return the key."""
        ...

    def fetch(self, key: str, dest: Path) -> Path:
        """Make the bytes available on local disk for processing; return their path."""
        ...

    def url(self, key: str) -> str | None:
        """Browser-playable URL, or None when the API must serve the file itself."""
        ...

    def delete(self, key: str) -> None: ...


# ------------------------------------------------------------------------- local disk


class LocalStorage:
    def __init__(self, root: Path):
        self.root = Path(root)

    def save(self, key: str, stream: BinaryIO, content_type: str | None = None) -> str:
        dest = self.path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as f:
            shutil.copyfileobj(stream, f)
        return key

    def fetch(self, key: str, dest: Path) -> Path:
        # Already on disk; no copy needed.
        return self.path(key)

    def url(self, key: str) -> str | None:
        return None

    def delete(self, key: str) -> None:
        self.path(key).unlink(missing_ok=True)

    def path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root.resolve() not in p.parents:
            raise ValueError("storage key escapes root")
        return p


# ------------------------------------------------------------------------- cloudinary


def split_key(key: str) -> tuple[str, str]:
    """``phr/2026/10/abc.16k.wav`` -> (``phr/2026/10/abc.16k``, ``wav``)."""
    stem, _, ext = key.rpartition(".")
    if not stem or "/" in ext:
        raise ValueError(f"storage key needs an extension: {key!r}")
    return stem, ext.lower()


def parse_cloudinary_url(url: str) -> dict[str, str]:
    """``cloudinary://<api_key>:<api_secret>@<cloud_name>`` -> config kwargs."""
    u = urlparse(url)
    if u.scheme != "cloudinary" or not (u.username and u.password and u.hostname):
        raise ValueError("CLOUDINARY_URL must look like cloudinary://api_key:api_secret@cloud_name")
    return {"cloud_name": u.hostname, "api_key": u.username, "api_secret": u.password}


class CloudinaryStorage:
    RESOURCE_TYPE = "video"  # Cloudinary's bucket for all audio

    def __init__(self, cloudinary_url: str, folder: str = "awaaz"):
        import cloudinary  # lazy: optional dependency

        self._cld = cloudinary
        cloudinary.config(**parse_cloudinary_url(cloudinary_url), secure=True)
        self.folder = folder.strip("/")

    def public_id(self, key: str) -> str:
        stem, _ = split_key(key)
        return f"{self.folder}/{stem}" if self.folder else stem

    def save(self, key: str, stream: BinaryIO, content_type: str | None = None) -> str:
        import cloudinary.uploader

        _, ext = split_key(key)
        cloudinary.uploader.upload(
            stream,
            public_id=self.public_id(key),
            resource_type=self.RESOURCE_TYPE,
            format=ext,
            overwrite=True,
            invalidate=True,
            unique_filename=False,
            use_filename=False,
        )
        return key

    def url(self, key: str) -> str | None:
        from cloudinary.utils import cloudinary_url

        _, ext = split_key(key)
        href, _ = cloudinary_url(
            self.public_id(key), resource_type=self.RESOURCE_TYPE, format=ext, secure=True
        )
        return href

    def fetch(self, key: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        href = self.url(key)
        with urllib.request.urlopen(href, timeout=60) as resp, dest.open("wb") as out:
            shutil.copyfileobj(resp, out)
        return dest

    def delete(self, key: str) -> None:
        import cloudinary.uploader

        cloudinary.uploader.destroy(self.public_id(key), resource_type=self.RESOURCE_TYPE, invalidate=True)


# ------------------------------------------------------------------------- helpers


def recording_key(lang: str, recording_id: str, ext: str) -> str:
    now = datetime.now(UTC)
    return f"{lang}/{now:%Y}/{now:%m}/{recording_id}.{ext.lstrip('.')}"


def wav_key_for(original_key: str) -> str:
    stem, _ = split_key(original_key)
    return f"{stem}.16k.wav"


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        s = get_settings()
        if s.storage_backend == "cloudinary":
            if not s.cloudinary_url:
                raise RuntimeError("STORAGE_BACKEND=cloudinary requires CLOUDINARY_URL")
            _storage = CloudinaryStorage(s.cloudinary_url, s.cloudinary_folder)
            log.info("storage: cloudinary folder=%s", s.cloudinary_folder)
        else:
            _storage = LocalStorage(s.storage_dir)
            log.info("storage: local dir=%s", s.storage_dir)
    return _storage
