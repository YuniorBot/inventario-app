from flask import abort, session
from flask_login import current_user, logout_user

from ..constants import EDIT_ROLES, ROLE_ADMIN, ROLE_SUPERADMIN, STATUS_ACTIVE
from ..extensions import db
from ..models import Empresa, Foto, Inmueble, Inventario, Observacion, Seccion, Usuario


def user_can_edit(user) -> bool:
    return bool(user and user.is_authenticated and user.rol in EDIT_ROLES)


def user_is_superadmin(user) -> bool:
    return bool(user and user.is_authenticated and user.rol == ROLE_SUPERADMIN)


def user_is_admin(user) -> bool:
    return bool(user and user.is_authenticated and user.rol == ROLE_ADMIN)


def user_has_admin_access(user) -> bool:
    return user_is_admin(user) or user_is_superadmin(user)


def get_effective_company_for_user(
    user, selected_company_id: int | None
) -> Empresa | None:
    if not user or not user.is_authenticated:
        return None
    if user_is_superadmin(user):
        if not selected_company_id:
            return None
        return db.session.get(Empresa, selected_company_id)
    return user.empresa


def user_has_active_company_access(user, empresa: Empresa | None) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user_is_superadmin(user):
        return empresa is not None
    return bool(
        getattr(user, "activo", True)
        and empresa
        and empresa.activo
        and empresa.estado == STATUS_ACTIVE
    )


def entity_belongs_to_company(entity, company_id: int | None, resolver) -> bool:
    if not entity or company_id is None:
        return False
    return resolver(entity) == company_id


def require_edit_permission() -> None:
    if not user_can_edit(current_user):
        abort(403)


def require_admin_permission() -> None:
    if not user_has_admin_access(current_user):
        abort(403)


def require_superadmin_permission() -> None:
    if not user_is_superadmin(current_user):
        abort(403)


def get_effective_company() -> Empresa | None:
    return get_effective_company_for_user(
        current_user, session.get("superadmin_company_id")
    )


def get_effective_company_id() -> int | None:
    empresa = get_effective_company()
    return empresa.id if empresa else None


def company_required() -> None:
    empresa = get_effective_company()
    if user_has_active_company_access(current_user, empresa):
        return
    if current_user.is_authenticated and not user_is_superadmin(current_user):
        logout_user()
    abort(403)


def _get_entity_for_current_company_or_404(entity_id: int, model, resolver):
    company_required()
    entity = db.session.get(model, entity_id)
    if not entity:
        abort(404)
    if not entity_belongs_to_company(entity, get_effective_company_id(), resolver):
        abort(403)
    return entity


def get_inmueble_for_current_company_or_404(inmueble_id: int) -> Inmueble:
    return _get_entity_for_current_company_or_404(
        inmueble_id,
        Inmueble,
        lambda inmueble: inmueble.empresa_id,
    )


def get_inventario_for_current_company_or_404(inventario_id: int) -> Inventario:
    return _get_entity_for_current_company_or_404(
        inventario_id,
        Inventario,
        lambda inventario: inventario.inmueble.empresa_id,
    )


def get_seccion_for_current_company_or_404(seccion_id: int) -> Seccion:
    return _get_entity_for_current_company_or_404(
        seccion_id,
        Seccion,
        lambda seccion: seccion.inventario.inmueble.empresa_id,
    )


def get_foto_for_current_company_or_404(foto_id: int) -> Foto:
    return _get_entity_for_current_company_or_404(
        foto_id,
        Foto,
        lambda foto: foto.seccion.inventario.inmueble.empresa_id,
    )


def get_observacion_for_current_company_or_404(observacion_id: int) -> Observacion:
    return _get_entity_for_current_company_or_404(
        observacion_id,
        Observacion,
        lambda observacion: observacion.seccion.inventario.inmueble.empresa_id,
    )


def get_user_for_current_company_or_404(user_id: int) -> Usuario:
    return _get_entity_for_current_company_or_404(
        user_id,
        Usuario,
        lambda usuario: usuario.empresa_id,
    )
