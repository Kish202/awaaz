"""Celery application. Redis is the broker and result backend.

Run a worker with:  lowres-asr-worker
(equivalent to `celery -A lowres_asr.queue.celery_app:celery worker`)

The API only ever *enqueues*; all audio processing happens here, so 500 people
uploading at once costs the API nothing more than 500 small file writes and 500
Redis pushes. Workers drain the queue at whatever rate the machine allows, and you
scale by starting more workers.
"""

from __future__ import annotations

import sys

from celery import Celery

from ..settings import get_settings

_s = get_settings()

celery = Celery(
    "lowres_asr",
    broker=_s.redis_url,
    backend=_s.redis_url,
    include=["lowres_asr.queue.tasks"],
)
celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Don't ack until the task finishes: if a worker dies mid-conversion the job is redelivered.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # One job at a time per process; ffmpeg is CPU-bound so prefetching gains nothing.
    worker_prefetch_multiplier=1,
    task_time_limit=120,
    task_soft_time_limit=90,
    result_expires=3600,
    task_default_queue="recordings",
    task_routes={
        "lowres_asr.queue.tasks.process_recording": {"queue": "recordings"},
        "lowres_asr.queue.tasks.ingest_sentences": {"queue": "text"},
    },
)


def main() -> None:
    """Console entry point: `lowres-asr-worker [extra celery args]`.

    On macOS the default prefork pool uses the `spawn` start method, which breaks
    Celery's task tracer (`_loc` is never initialised in the child). The thread pool
    is the right choice there anyway: the work is an ffmpeg subprocess, so threads
    sit idle waiting on I/O rather than fighting over the GIL. Linux keeps prefork.
    """
    extra = sys.argv[1:]
    argv = ["worker", "--loglevel=INFO", "-Q", "recordings,text"]
    if sys.platform == "darwin" and not any(a.startswith(("--pool", "-P")) for a in extra):
        argv.append("--pool=threads")
    celery.worker_main([*argv, *extra])
