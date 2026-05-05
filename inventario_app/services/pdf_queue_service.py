from datetime import datetime, timezone

from flask import current_app
from redis import Redis
from rq import Queue

from ..constants import (
    PDF_ACTIVE_STATUSES,
    PDF_STATUS_FAILED,
    PDF_STATUS_NOT_STARTED,
    PDF_STATUS_PENDING,
    PDF_STATUS_PROCESSING,
    PDF_STATUS_READY,
)
from ..extensions import db
from ..models import Inventario
from .media_service import get_pdf_file_url, pdf_file_exists


def enqueue_inventory_pdf(inventario: Inventario):
    filename = inventario.pdf_filename or f"inventario_{inventario.id}.pdf"
    if inventario.pdf_status == PDF_STATUS_READY and pdf_file_exists(filename):
        return inventario

    if inventario.pdf_status in PDF_ACTIVE_STATUSES:
        return inventario

    now = datetime.now(timezone.utc)
    inventario.pdf_status = PDF_STATUS_PENDING
    inventario.pdf_error = None
    inventario.pdf_requested_at = now
    inventario.pdf_generated_at = None
    db.session.commit()

    if current_app.config.get("PDF_QUEUE_SYNC") or current_app.config.get("TESTING"):
        from ..jobs.pdf_jobs import generate_inventory_pdf_job

        generate_inventory_pdf_job(inventario.id, inventario.pdf_version, False)
        db.session.refresh(inventario)
        return inventario

    queue = _get_pdf_queue()
    job = queue.enqueue(
        "inventario_app.jobs.pdf_jobs.generate_inventory_pdf_job",
        inventario.id,
        inventario.pdf_version,
        job_timeout=current_app.config.get("PDF_JOB_TIMEOUT_SECONDS", 900),
    )
    inventario.pdf_job_id = job.id
    db.session.commit()
    return inventario


def get_pdf_status_payload(inventario: Inventario) -> dict:
    filename = inventario.pdf_filename or f"inventario_{inventario.id}.pdf"
    is_ready = inventario.pdf_status == PDF_STATUS_READY and pdf_file_exists(filename)
    status = inventario.pdf_status
    if is_ready:
        status = PDF_STATUS_READY
    elif inventario.pdf_status == PDF_STATUS_READY:
        status = PDF_STATUS_NOT_STARTED

    return {
        "status": status,
        "download_url": get_pdf_file_url(inventario.id) if is_ready else None,
        "error": inventario.pdf_error if status == PDF_STATUS_FAILED else None,
    }


def mark_inventory_pdf_dirty(inventario: Inventario) -> None:
    inventario.pdf_status = PDF_STATUS_NOT_STARTED
    inventario.pdf_filename = None
    inventario.pdf_error = None
    inventario.pdf_generated_at = None
    inventario.pdf_job_id = None
    inventario.pdf_version = (inventario.pdf_version or 0) + 1


def _get_pdf_queue() -> Queue:
    redis_conn = Redis.from_url(current_app.config["REDIS_URL"])
    return Queue(current_app.config.get("PDF_QUEUE_NAME", "pdfs"), connection=redis_conn)


def set_pdf_processing(inventario: Inventario) -> None:
    inventario.pdf_status = PDF_STATUS_PROCESSING
    inventario.pdf_error = None
    db.session.commit()


def set_pdf_ready(inventario: Inventario, filename: str) -> None:
    inventario.pdf_status = PDF_STATUS_READY
    inventario.pdf_filename = filename
    inventario.pdf_error = None
    inventario.pdf_generated_at = datetime.now(timezone.utc)
    db.session.commit()


def set_pdf_failed(inventario: Inventario, message: str) -> None:
    inventario.pdf_status = PDF_STATUS_FAILED
    inventario.pdf_error = message[:1000]
    db.session.commit()
