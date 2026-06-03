import base64
import binascii
import re
import uuid
from dataclasses import dataclass

from flask import current_app

from ..extensions import db
from ..models import Firma, Inventario, Seccion
from ..services.pdf_queue_service import mark_inventory_pdf_dirty
from ..utils.dates import parse_iso_date

DEFAULT_SECTION_NAMES = [
    "Fachada",
    "Sala",
    "Comedor",
    "Cocina",
    "Baños",
    "Habitación principal",
    "Habitación auxiliar",
]


@dataclass
class CreateInventoryResult:
    inventory: Inventario | None
    is_valid: bool


@dataclass
class SaveSignatureResult:
    is_valid: bool
    error_message: str | None = None


@dataclass
class GenerateInventoryPdfResult:
    pdf_name: str | None
    failed: bool


def create_inventory(
    inmueble_id: int, nombre: str, fecha_raw: str
) -> CreateInventoryResult:
    nombre = nombre.strip()
    fecha = parse_iso_date(fecha_raw)
    if not nombre or not fecha:
        return CreateInventoryResult(inventory=None, is_valid=False)

    nuevo = Inventario(
        inmueble_id=inmueble_id,
        nombre=nombre,
        fecha=fecha,
        token=str(uuid.uuid4()),
    )
    db.session.add(nuevo)
    db.session.flush()

    for nombre_seccion in DEFAULT_SECTION_NAMES:
        db.session.add(Seccion(inventario_id=nuevo.id, nombre=nombre_seccion))

    db.session.commit()
    current_app.logger.info(
        "inventario_created inmueble_id=%s inventario_id=%s", inmueble_id, nuevo.id
    )
    return CreateInventoryResult(inventory=nuevo, is_valid=True)


def rename_inventory(inventario: Inventario, nombre: str) -> bool:
    nombre = nombre.strip()
    if not nombre:
        return False

    inventario.nombre = nombre
    mark_inventory_pdf_dirty(inventario)
    db.session.commit()
    current_app.logger.info("inventario_renamed inventario_id=%s", inventario.id)
    return True


def list_inventory_sections(inventario_id: int) -> list[Seccion]:
    return (
        Seccion.query.filter_by(inventario_id=inventario_id)
        .order_by(Seccion.id.asc())
        .all()
    )


def save_inventory_signature(
    inventario_id: int,
    nombre: str,
    cedula: str,
    celular: str,
    correo: str,
    imagen: str,
) -> SaveSignatureResult:
    nombre = nombre.strip()
    cedula = cedula.strip() or None
    celular = celular.strip() or None
    correo = correo.strip() or None
    imagen = imagen.strip()

    if not nombre or not imagen or "," not in imagen:
        return SaveSignatureResult(is_valid=False, error_message="Firma invalida.")

    if correo and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", correo):
        return SaveSignatureResult(is_valid=False, error_message="Correo invalido.")

    encabezado, datos_base64 = imagen.split(",", 1)
    encabezado = encabezado.lower()
    if not encabezado.startswith("data:image/") or ";base64" not in encabezado:
        return SaveSignatureResult(is_valid=False, error_message="Firma invalida.")

    try:
        base64.b64decode(datos_base64, validate=True)
    except (ValueError, binascii.Error):
        return SaveSignatureResult(is_valid=False, error_message="Firma invalida.")

    db.session.add(
        Firma(
            inventario_id=inventario_id,
            nombre=nombre,
            cedula=cedula,
            celular=celular,
            correo=correo,
            imagen=imagen,
        )
    )
    inventario = db.session.get(Inventario, inventario_id)
    if inventario:
        mark_inventory_pdf_dirty(inventario)
    db.session.commit()
    return SaveSignatureResult(is_valid=True)


def get_pdf_sections(inventario_id: int) -> list[Seccion]:
    return [
        seccion
        for seccion in list_inventory_sections(inventario_id)
        if seccion.fotos or seccion.observaciones or (seccion.descripcion or "").strip()
    ]


def get_inventory_signatures(inventario_id: int) -> list[Firma]:
    return (
        Firma.query.filter_by(inventario_id=inventario_id)
        .order_by(Firma.id.asc())
        .all()
    )


def generate_inventory_pdf(
    inventario: Inventario, pdf_builder
) -> GenerateInventoryPdfResult:
    secciones = get_pdf_sections(inventario.id)
    firmas = get_inventory_signatures(inventario.id)
    try:
        nombre_pdf = pdf_builder(inventario, secciones, firmas)
    except Exception:
        current_app.logger.exception(
            "pdf_generation_failed inventario_id=%s", inventario.id
        )
        return GenerateInventoryPdfResult(pdf_name=None, failed=True)

    current_app.logger.info(
        "pdf_generated inventario_id=%s archivo=%s", inventario.id, nombre_pdf
    )
    return GenerateInventoryPdfResult(pdf_name=nombre_pdf, failed=False)
