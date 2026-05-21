from dataclasses import dataclass

from flask import current_app

from ..constants import (
    MEDIA_TYPE_IMAGE,
    MEDIA_TYPE_VIDEO,
    VIDEO_STATUS_READY,
)
from ..extensions import db
from ..models import Foto, Observacion, Seccion
from ..services.media_service import (
    MediaProcessingError,
    build_relative_upload_key,
    create_presigned_upload_post,
    delete_uploaded_file,
    get_uploaded_file_size,
    save_uploaded_file,
    uploaded_file_exists,
)
from ..services.pdf_queue_service import mark_inventory_pdf_dirty
from ..services.video_queue_service import enqueue_video_processing
from ..utils.files import VIDEO_EXTENSIONS, is_video_filename, unique_filename, validate_uploaded_file


@dataclass
class UploadSectionFilesResult:
    saved_count: int
    errors: list[str]


@dataclass
class VideoUploadPreparationResult:
    is_valid: bool
    error_message: str | None = None
    payload: dict | None = None


@dataclass
class VideoUploadCompletionResult:
    is_valid: bool
    error_message: str | None = None
    foto_id: int | None = None


def save_section_description(seccion: Seccion, descripcion: str) -> None:
    seccion.descripcion = descripcion.strip() or None
    mark_inventory_pdf_dirty(seccion.inventario)
    db.session.commit()
    current_app.logger.info("descripcion_updated seccion_id=%s", seccion.id)


def upload_section_files(seccion: Seccion, archivos) -> UploadSectionFilesResult:
    errors: list[str] = []
    saved_count = 0

    for archivo in archivos:
        if not archivo or not archivo.filename:
            continue

        validation_error = validate_uploaded_file(archivo)
        if validation_error:
            current_app.logger.warning(
                "upload_rejected seccion_id=%s filename=%s reason=%s",
                seccion.id,
                archivo.filename,
                validation_error,
            )
            errors.append(validation_error)
            continue

        try:
            nombre_archivo = save_uploaded_file(archivo)
        except MediaProcessingError as error:
            current_app.logger.warning(
                "upload_processing_rejected seccion_id=%s filename=%s reason=%s",
                seccion.id,
                archivo.filename,
                str(error),
            )
            errors.append(str(error))
            continue
        except Exception:
            current_app.logger.exception(
                "upload_failed seccion_id=%s filename=%s", seccion.id, archivo.filename
            )
            errors.append(f"No se pudo guardar el archivo: {archivo.filename}")
            continue

        tipo = MEDIA_TYPE_VIDEO if is_video_filename(nombre_archivo) else MEDIA_TYPE_IMAGE
        db.session.add(
            Foto(
                seccion_id=seccion.id,
                archivo=nombre_archivo,
                tipo=tipo,
            )
        )
        saved_count += 1

    if saved_count:
        mark_inventory_pdf_dirty(seccion.inventario)
        db.session.commit()
        current_app.logger.info(
            "upload_saved seccion_id=%s cantidad=%s", seccion.id, saved_count
        )
    else:
        db.session.rollback()

    return UploadSectionFilesResult(saved_count=saved_count, errors=errors)


def prepare_direct_video_upload(
    seccion: Seccion,
    filename: str,
    content_type: str,
    size_bytes: int,
) -> VideoUploadPreparationResult:
    filename = (filename or "").strip()
    content_type = (content_type or "").strip().lower()
    max_size = current_app.config.get("VIDEO_MAX_UPLOAD_BYTES", 500 * 1024 * 1024)

    if not filename or not is_video_filename(filename):
        return VideoUploadPreparationResult(False, "Selecciona un archivo de video valido.")
    if size_bytes <= 0 or size_bytes > max_size:
        return VideoUploadPreparationResult(
            False,
            f"El video supera el tamano maximo permitido de {max_size // (1024 * 1024)} MB.",
        )
    if content_type and not content_type.startswith("video/"):
        return VideoUploadPreparationResult(False, "El archivo no coincide con un formato de video valido.")

    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in VIDEO_EXTENSIONS:
        return VideoUploadPreparationResult(False, "Extension de video no permitida.")

    unique_name = unique_filename(filename)
    relative_key = build_relative_upload_key(
        current_app.config.get("VIDEO_ORIGINAL_PREFIX", "videos/originals"), unique_name
    )
    post = create_presigned_upload_post(
        relative_key, content_type or "video/mp4", max_size
    )
    return VideoUploadPreparationResult(
        True,
        payload={
            "upload": post,
            "filename": relative_key,
            "max_size": max_size,
        },
    )


def complete_direct_video_upload(
    seccion: Seccion,
    filename: str,
    size_bytes: int | None = None,
) -> VideoUploadCompletionResult:
    filename = (filename or "").strip()
    original_prefix = current_app.config.get("VIDEO_ORIGINAL_PREFIX", "videos/originals").strip("/")
    if not filename.startswith(f"{original_prefix}/") or not is_video_filename(filename):
        return VideoUploadCompletionResult(False, "Referencia de video invalida.")

    if not uploaded_file_exists(filename):
        return VideoUploadCompletionResult(False, "La subida del video no se completo en S3.")

    detected_size = get_uploaded_file_size(filename)
    final_size = detected_size if detected_size is not None else size_bytes
    max_size = current_app.config.get("VIDEO_MAX_UPLOAD_BYTES", 500 * 1024 * 1024)
    if final_size and final_size > max_size:
        delete_uploaded_file(filename)
        return VideoUploadCompletionResult(False, "El video supera el tamano maximo permitido.")

    foto = Foto(
        seccion_id=seccion.id,
        archivo=filename,
        archivo_original=filename,
        tipo=MEDIA_TYPE_VIDEO,
        processing_status=VIDEO_STATUS_READY,
        size_bytes=final_size,
    )
    db.session.add(foto)
    mark_inventory_pdf_dirty(seccion.inventario)
    db.session.commit()
    enqueue_video_processing(foto)
    current_app.logger.info("video_upload_completed foto_id=%s seccion_id=%s", foto.id, seccion.id)
    return VideoUploadCompletionResult(True, foto_id=foto.id)


def delete_section_photo(foto: Foto) -> int:
    seccion_id = foto.seccion_id
    mark_inventory_pdf_dirty(foto.seccion.inventario)
    db.session.delete(foto)
    db.session.commit()
    archivos = {foto.archivo, foto.archivo_original}
    for archivo in {archivo for archivo in archivos if archivo}:
        delete_uploaded_file(archivo)
    current_app.logger.info(
        "upload_deleted foto_id=%s seccion_id=%s", foto.id, seccion_id
    )
    return seccion_id


def create_section_observation(seccion: Seccion, comentario: str) -> bool:
    comentario = comentario.strip()
    if not comentario:
        return False

    db.session.add(Observacion(seccion_id=seccion.id, comentario=comentario))
    mark_inventory_pdf_dirty(seccion.inventario)
    db.session.commit()
    current_app.logger.info("observacion_created seccion_id=%s", seccion.id)
    return True


def create_inventory_section(inventario_id: int, nombre: str) -> bool:
    nombre = nombre.strip()
    if not nombre:
        return False

    seccion = Seccion(inventario_id=inventario_id, nombre=nombre)
    db.session.add(seccion)
    db.session.flush()
    mark_inventory_pdf_dirty(seccion.inventario)
    db.session.commit()
    return True


def delete_inventory_section(seccion: Seccion) -> int:
    inventario_id = seccion.inventario_id
    archivos = [foto.archivo for foto in seccion.fotos]
    mark_inventory_pdf_dirty(seccion.inventario)
    db.session.delete(seccion)
    db.session.commit()
    for archivo in archivos:
        delete_uploaded_file(archivo)
    return inventario_id


def rename_section(seccion: Seccion, nombre: str) -> bool:
    nombre = nombre.strip()
    if not nombre:
        return False

    seccion.nombre = nombre
    mark_inventory_pdf_dirty(seccion.inventario)
    db.session.commit()
    return True
