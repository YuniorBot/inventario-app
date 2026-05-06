from dataclasses import dataclass

from flask import current_app

from ..extensions import db
from ..models import Foto, Observacion, Seccion
from ..services.media_service import (
    MediaProcessingError,
    delete_uploaded_file,
    save_uploaded_file,
)
from ..services.pdf_queue_service import mark_inventory_pdf_dirty
from ..utils.files import validate_uploaded_file


@dataclass
class UploadSectionFilesResult:
    saved_count: int
    errors: list[str]


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

        db.session.add(Foto(seccion_id=seccion.id, archivo=nombre_archivo))
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


def delete_section_photo(foto: Foto) -> int:
    seccion_id = foto.seccion_id
    mark_inventory_pdf_dirty(foto.seccion.inventario)
    db.session.delete(foto)
    db.session.commit()
    delete_uploaded_file(foto.archivo)
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
