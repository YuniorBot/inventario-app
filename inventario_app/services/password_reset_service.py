import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

from flask import current_app, render_template, request, url_for
from werkzeug.security import generate_password_hash

from ..constants import ROLE_SUPERADMIN, STATUS_ACTIVE, VALID_ROLES
from ..extensions import db
from ..models import PasswordResetToken, Usuario
from .email_service import send_html_email


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _password_reset_ttl_seconds() -> int:
    return max(60, int(current_app.config.get("PASSWORD_RESET_TOKEN_TTL_SECONDS", 300)))


def _password_reset_ttl_minutes_label() -> int:
    return max(1, _password_reset_ttl_seconds() // 60)


def _build_reset_url(token: str) -> str:
    reset_path = url_for("auth.reset_password", token=token)
    base_url = (current_app.config.get("APP_BASE_URL") or request.host_url or "").strip()
    if not base_url:
        raise RuntimeError("No se pudo construir la URL de restablecimiento.")
    return urljoin(f"{base_url.rstrip('/')}/", reset_path.lstrip("/"))


def _invalidate_user_tokens(user_id: int) -> None:
    now = _utcnow()
    active_tokens = PasswordResetToken.query.filter_by(usuario_id=user_id, used_at=None).all()
    for token in active_tokens:
        token.used_at = now


def _is_user_eligible_for_password_reset(usuario: Usuario | None) -> bool:
    return bool(
        usuario
        and usuario.rol != ROLE_SUPERADMIN
        and usuario.activo
        and usuario.rol in VALID_ROLES
        and usuario.empresa
        and usuario.empresa.activo
        and usuario.empresa.estado == STATUS_ACTIVE
    )


def request_password_reset(email: str) -> None:
    normalized_email = email.strip().lower()
    if not normalized_email:
        return

    usuario = Usuario.query.filter_by(email=normalized_email).first()
    if not _is_user_eligible_for_password_reset(usuario):
        return

    _invalidate_user_tokens(usuario.id)

    raw_token = secrets.token_urlsafe(32)
    now = _utcnow()
    token_record = PasswordResetToken(
        usuario_id=usuario.id,
        token_hash=_hash_token(raw_token),
        expires_at=now + timedelta(seconds=_password_reset_ttl_seconds()),
    )
    db.session.add(token_record)
    db.session.commit()

    reset_url = _build_reset_url(raw_token)
    ttl_minutes = _password_reset_ttl_minutes_label()
    html_body = render_template(
        "emails/password_reset.html",
        usuario=usuario,
        reset_url=reset_url,
        ttl_minutes=ttl_minutes,
    )
    text_body = render_template(
        "emails/password_reset.txt",
        usuario=usuario,
        reset_url=reset_url,
        ttl_minutes=ttl_minutes,
    )
    send_html_email(
        usuario.email,
        "Restablece tu contrasena en Intoryx",
        html_body,
        text_body,
    )


def get_valid_password_reset_token(raw_token: str) -> PasswordResetToken | None:
    if not raw_token:
        return None

    token_record = PasswordResetToken.query.filter_by(token_hash=_hash_token(raw_token)).first()
    if token_record is None or token_record.used_at is not None:
        return None

    if _ensure_utc(token_record.expires_at) < _utcnow():
        return None

    if not _is_user_eligible_for_password_reset(token_record.usuario):
        return None

    return token_record


def reset_password_with_token(raw_token: str, new_password: str) -> tuple[bool, str]:
    token_record = get_valid_password_reset_token(raw_token)
    if token_record is None:
        return False, "El enlace de restablecimiento no es valido o ya expiro."

    if len(new_password) < 6:
        return False, "La nueva contrasena debe tener al menos 6 caracteres."

    now = _utcnow()
    token_record.usuario.password = generate_password_hash(new_password)
    token_record.used_at = now

    active_tokens = PasswordResetToken.query.filter(
        PasswordResetToken.usuario_id == token_record.usuario_id,
        PasswordResetToken.id != token_record.id,
        PasswordResetToken.used_at.is_(None),
    ).all()
    for active_token in active_tokens:
        active_token.used_at = now

    db.session.commit()
    return True, "Contrasena actualizada correctamente. Ya puedes iniciar sesion."
