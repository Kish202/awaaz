"""FastAPI application behind the web UI.

Stateless text tools (sentences, charset, normalize, transcribe) live here; the
contribution platform (contributors, sentence pool, recordings, validations, stats)
is in `routers/` and is backed by PostgreSQL + Celery/Redis.

Run with:  lowres-asr-api            (reads .env; see settings.py)
Requires:  pip install -e '.[api]'   and a reachable PostgreSQL + Redis + ffmpeg.
"""

from __future__ import annotations

import os
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .config import CONFIG_DIR, load_config
from .routers import contributors, recordings, sentences, stats, validations
from .settings import get_settings
from .text.normalize import char_inventory, normalize, normalize_for_asr
from .text.sentences import extract_sentences


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="awaaz / lowres-asr", version="0.2.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.limiter = recordings.limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.include_router(contributors.router)
    app.include_router(sentences.router)
    app.include_router(recordings.router)
    app.include_router(validations.router)
    app.include_router(stats.router)
    _register_text_tools(app)
    return app


# ---------------------------------------------------------------- stateless text tools


class TextRequest(BaseModel):
    lang: str
    text: str
    source: str = "pasted"


class NormalizeRequest(BaseModel):
    lang: str
    text: str
    asr: bool = False


def _register_text_tools(app: FastAPI) -> None:
    @app.get("/api/languages")
    def languages() -> list[dict]:
        out = []
        for p in sorted(CONFIG_DIR.glob("*.yaml")):
            cfg = load_config(p.stem)
            out.append(
                {
                    "code": cfg.code,
                    "name": cfg.name,
                    "whisper_language": cfg.whisper_language,
                    "sentence_rules": {
                        "min_words": cfg.sentences.min_words,
                        "max_words": cfg.sentences.max_words,
                    },
                }
            )
        return out

    @app.post("/api/text/sentences")
    def split_sentences(req: TextRequest) -> dict:
        cfg = _cfg(req.lang)
        res = extract_sentences([(req.source, req.text)], cfg.sentences, cfg.text)
        reasons: dict[str, int] = {}
        for r in res.rejected:
            reasons[r.reason] = reasons.get(r.reason, 0) + 1
        return {
            "accepted": [{"sentence": s, "source": src} for s, src in res.accepted],
            "rejected": [
                {"sentence": r.sentence, "reason": r.reason, "source": r.source} for r in res.rejected
            ],
            "duplicates": res.duplicates,
            "reasons": reasons,
        }

    @app.post("/api/text/charset")
    def charset(req: TextRequest) -> list[dict]:
        rows = char_inventory([req.text])
        return [{"char": c, "codepoint": cp, "name": n, "count": k} for c, cp, n, k in rows]

    @app.post("/api/text/normalize")
    def normalize_endpoint(req: NormalizeRequest) -> dict:
        cfg = _cfg(req.lang)
        fn = normalize_for_asr if req.asr else normalize
        lines = [fn(line, cfg.text) for line in req.text.splitlines()]
        return {"text": "\n".join(line for line in lines if line)}

    @app.post("/api/transcribe")
    async def transcribe(
        lang: Annotated[str, Form()],
        file: Annotated[UploadFile, File()],
        model: Annotated[str | None, Form()] = None,
    ) -> dict:
        model = model or os.environ.get("LOWRES_ASR_MODEL", "openai/whisper-small")
        cfg = _cfg(lang)
        try:
            transcriber = _transcriber(model, lang)
        except ImportError as e:
            raise HTTPException(503, "ASR dependencies not installed: pip install -e '.[train]'") from e
        suffix = Path(file.filename or "clip").suffix or ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(await file.read())
            tmp_path = Path(tmp.name)
        try:
            ((_, text),) = list(transcriber.transcribe_files([tmp_path], batch_size=1))
        finally:
            tmp_path.unlink(missing_ok=True)
        return {"text": text, "normalized": normalize_for_asr(text, cfg.text), "model": model}


def _cfg(lang: str):
    try:
        return load_config(lang)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


@lru_cache(maxsize=2)
def _transcriber(model: str, lang: str):
    from .transcribe import WhisperTranscriber

    return WhisperTranscriber(model, load_config(lang))


app = create_app()


def main() -> None:
    import uvicorn

    s = get_settings()
    uvicorn.run(
        "lowres_asr.api:app",
        host=os.environ.get("HOST", s.host),
        port=int(os.environ.get("PORT", s.port)),
        reload=bool(os.environ.get("RELOAD")),
    )
