import io
from pathlib import Path

import pytest

from lowres_asr.storage import (
    CloudinaryStorage,
    LocalStorage,
    parse_cloudinary_url,
    split_key,
    wav_key_for,
)


def test_split_key_and_wav_key():
    assert split_key("phr/2026/10/abc.webm") == ("phr/2026/10/abc", "webm")
    assert split_key("phr/2026/10/abc.16k.wav") == ("phr/2026/10/abc.16k", "wav")
    assert wav_key_for("gju/2026/10/abc.m4a") == "gju/2026/10/abc.16k.wav"
    with pytest.raises(ValueError):
        split_key("phr/2026/10/noext")


def test_parse_cloudinary_url():
    assert parse_cloudinary_url("cloudinary://123:s3cret@mycloud") == {
        "cloud_name": "mycloud",
        "api_key": "123",
        "api_secret": "s3cret",
    }
    with pytest.raises(ValueError):
        parse_cloudinary_url("https://example.com")


def test_local_storage_roundtrip(tmp_path: Path):
    st = LocalStorage(tmp_path)
    st.save("phr/2026/10/x.wav", io.BytesIO(b"RIFF"))
    assert st.fetch("phr/2026/10/x.wav", tmp_path / "unused").read_bytes() == b"RIFF"
    assert st.url("phr/2026/10/x.wav") is None
    with pytest.raises(ValueError):
        st.path("../escape.wav")


def test_cloudinary_storage_maps_keys_and_uploads(monkeypatch):
    pytest.importorskip("cloudinary")
    import cloudinary.uploader

    calls: list[dict] = []
    monkeypatch.setattr(cloudinary.uploader, "upload", lambda f, **o: calls.append(o) or {"public_id": o["public_id"]})

    st = CloudinaryStorage("cloudinary://k:s@democloud", folder="awaaz")
    key = "phr/2026/10/abc.16k.wav"
    assert st.public_id(key) == "awaaz/phr/2026/10/abc.16k"
    assert st.save(key, io.BytesIO(b"RIFF"), "audio/wav") == key
    assert calls[0]["resource_type"] == "video"
    assert calls[0]["format"] == "wav"
    assert calls[0]["public_id"] == "awaaz/phr/2026/10/abc.16k"
    assert st.url(key) == "https://res.cloudinary.com/democloud/video/upload/v1/awaaz/phr/2026/10/abc.16k.wav"
