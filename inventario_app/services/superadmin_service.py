from dataclasses import dataclass

from werkzeug.security import generate_password_hash

from ..constants import (
    INTERNAL_COMPANY_SLUG,
    ROLE_ADMIN,
    STATUS_CANCELLED,
    VALID_COMPANY_STATUSES,
)
from ..extensions import db
from ..models import Empresa, Usuario
from ..services.company_service import unique_company_slug


@dataclass
class ServiceResult:
    is_valid: bool
    error_message: str | None = None


def create_company_with_primary_admin(
    empresa_nombre: str,
    admin_nombre: str,
    email: str,
    password_raw: str,
    estado: str,
) -> ServiceResult:
    empresa_nombre = empresa_nombre.strip()
    admin_nombre = admin_nombre.strip()
    email = email.strip().lower()
    estado = estado.strip()

    if not empresa_nombre or not admin_nombre or not email or not password_raw:
        return ServiceResult(
            False,
            "Empresa, admin, correo y contrasena temporal son obligatorios.",
        )

    if estado not in VALID_COMPANY_STATUSES:
        return ServiceResult(False, "Selecciona un estado valido para la empresa.")

    existe = Usuario.query.filter_by(email=email).first()
    if existe:
        return ServiceResult(False, "Ese correo ya esta registrado.")

    empresa = Empresa(
        nombre=empresa_nombre,
        slug=unique_company_slug(empresa_nombre),
        estado=estado,
        activo=True,
    )
    db.session.add(empresa)
    db.session.flush()

    nuevo = Usuario(
        nombre=admin_nombre,
        email=email,
        password=generate_password_hash(password_raw),
        empresa_id=empresa.id,
        rol=ROLE_ADMIN,
        activo=True,
    )
    db.session.add(nuevo)
    db.session.commit()
    return ServiceResult(True)


def list_managed_companies() -> list[Empresa]:
    return (
        Empresa.query.filter(Empresa.slug != INTERNAL_COMPANY_SLUG)
        .order_by(Empresa.nombre.asc())
        .all()
    )


def update_company_status(empresa: Empresa, estado: str) -> ServiceResult:
    estado = estado.strip()
    if estado not in VALID_COMPANY_STATUSES:
        return ServiceResult(False, "Selecciona un estado valido.")

    empresa.estado = estado
    empresa.activo = estado != STATUS_CANCELLED
    db.session.commit()
    return ServiceResult(True)


def reset_company_admin_password(empresa: Empresa, password_raw: str) -> ServiceResult:
    if len(password_raw) < 6:
        return ServiceResult(
            False, "La nueva contrasena debe tener al menos 6 caracteres."
        )

    admin = Usuario.query.filter_by(empresa_id=empresa.id, rol=ROLE_ADMIN).first()
    if not admin:
        return ServiceResult(False, "La empresa no tiene admin principal configurado.")

    admin.password = generate_password_hash(password_raw)
    db.session.commit()
    return ServiceResult(True)
