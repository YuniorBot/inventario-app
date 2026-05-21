from flask import current_app
from redis import Redis
from rq import Queue

from ..constants import (
    VIDEO_STATUS_FAILED,
    VIDEO_STATUS_PENDING_PROCESSING,
    VIDEO_STATUS_PROCESSED,
    VIDEO_STATUS_PROCESSING,
    VIDEO_STATUS_READY,
)
from ..extensions import db
from ..models import Foto


def enqueue_video_processing(foto: Foto) -> None:
    if foto.processing_status != VIDEO_STATUS_READY:
        foto.processing_status = VIDEO_STATUS_PENDING_PROCESSING
    foto.processing_error = None
    db.session.commit()

    if current_app.config.get("TESTING") and not current_app.config.get("VIDEO_QUEUE_SYNC"):
        return

    if current_app.config.get("VIDEO_QUEUE_SYNC"):
        from ..jobs.video_jobs import process_video_job

        process_video_job(foto.id, False)
        return

    queue = _get_video_queue()
    try:
        queue.enqueue(
            "inventario_app.jobs.video_jobs.process_video_job",
            foto.id,
            job_timeout=current_app.config.get("VIDEO_PROCESSING_TIMEOUT_SECONDS", 1800),
        )
    except Exception:
        current_app.logger.exception("video_enqueue_failed foto_id=%s", foto.id)
        set_video_failed(foto, "No se pudo iniciar el procesamiento del video.")


def _get_video_queue() -> Queue:
    redis_conn = Redis.from_url(current_app.config["REDIS_URL"])
    return Queue(current_app.config.get("VIDEO_QUEUE_NAME", "videos"), connection=redis_conn)


def set_video_processing(foto: Foto) -> None:
    foto.processing_status = VIDEO_STATUS_PROCESSING
    foto.processing_error = None
    db.session.commit()


def set_video_processed(foto: Foto, filename: str, duration_seconds: int | None = None) -> None:
    foto.archivo = filename
    foto.processing_status = VIDEO_STATUS_PROCESSED
    foto.processing_error = None
    foto.duration_seconds = duration_seconds
    db.session.commit()


def set_video_failed(foto: Foto, message: str) -> None:
    foto.processing_status = VIDEO_STATUS_FAILED
    foto.processing_error = message[:1000]
    db.session.commit()


def set_video_ready_with_warning(foto: Foto, message: str) -> None:
    foto.processing_status = VIDEO_STATUS_READY
    foto.processing_error = message[:1000]
    db.session.commit()
