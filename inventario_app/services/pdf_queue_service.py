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
    db.session.refresh(inventario)
    filename = inventario.pdf_filename or f"inventario_{inventario.id}.pdf"
    if inventario.pdf_status == PDF_STATUS_READY and pdf_file_exists(filename):
        return inventario

    if inventario.pdf_status in PDF_ACTIVE_STATUSES:
        if not _pdf_state_is_stale(inventario):
            return inventario
        current_app.logger.warning(
            "pdf_state_stale inventario_id=%s status=%s job_id=%s",
            inventario.id,
            inventario.pdf_status,
            inventario.pdf_job_id,
        )
        inventario.pdf_status = PDF_STATUS_NOT_STARTED
        inventario.pdf_job_id = None
        inventario.pdf_error = "La generacion anterior no finalizo a tiempo. Reintentando."

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
    try:
        job = queue.enqueue(
            "inventario_app.jobs.pdf_jobs.generate_inventory_pdf_job",
            inventario.id,
            inventario.pdf_version,
            job_timeout=current_app.config.get("PDF_JOB_TIMEOUT_SECONDS", 900),
        )
    except Exception:
        current_app.logger.exception("pdf_enqueue_failed inventario_id=%s", inventario.id)
        inventario.pdf_status = PDF_STATUS_FAILED
        inventario.pdf_error = (
            "No se pudo iniciar la generacion del PDF. Intenta nuevamente."
        )
        inventario.pdf_job_id = None
        db.session.commit()
        return inventario

    inventario.pdf_job_id = job.id
    db.session.commit()
    return inventario


def _pdf_state_is_stale(inventario: Inventario) -> bool:
    if inventario.pdf_status not in PDF_ACTIVE_STATUSES:
        return False
    if not inventario.pdf_requested_at:
        return True

    requested_at = inventario.pdf_requested_at
    if requested_at.tzinfo is None:
        requested_at = requested_at.replace(tzinfo=timezone.utc)

    stale_after = current_app.config.get("PDF_STALE_AFTER_SECONDS", 300)
    elapsed = datetime.now(timezone.utc) - requested_at.astimezone(timezone.utc)
    return elapsed.total_seconds() >= stale_after


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
