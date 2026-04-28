import re
from datetime import timedelta

from werkzeug.security import check_password_hash

from inventario_app.constants import INTERNAL_COMPANY_SLUG, ROLE_SUPERADMIN
from inventario_app.extensions import db
from inventario_app.models import Empresa, PasswordResetToken, Usuario
from inventario_app.services.password_reset_service import get_valid_password_reset_token


def _extract_reset_token(message) -> str:
    html_body = message["Message"]["Body"]["Html"]["Data"]
    match = re.search(r"/restablecer-password/([A-Za-z0-9_\-\.]+)", html_body)
    assert match is not None
    return match.group(1)


def _make_superadmin(app, make_company, make_user):
    with app.app_context():
        interna = Empresa.query.filter_by(slug=INTERNAL_COMPANY_SLUG).first()
        if not interna:
            interna = make_company("Plataforma Interna", INTERNAL_COMPANY_SLUG)
        usuario = make_user(
            interna.id,
            "Super Admin",
            "superadmin-reset@test.com",
            rol=ROLE_SUPERADMIN,
        )
        return {"id": usuario.id, "email": usuario.email}


def test_forgot_password_creates_token_and_sends_email(client, app, seeded_data):
    response = client.post(
        "/olvide-password",
        data={"email": seeded_data["admin_a"].email},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert (
        "Si el correo existe y esta habilitado" in response.get_data(as_text=True)
    )

    with app.app_context():
        token = PasswordResetToken.query.filter_by(
            usuario_id=seeded_data["admin_a"].id
        ).one()
        assert token.used_at is None
        assert get_valid_password_reset_token(_extract_reset_token(app.extensions["ses_client"].messages[0])) is not None

    message = app.extensions["ses_client"].messages[0]
    assert len(app.extensions["ses_client"].messages) == 1
    assert message["Source"] == "Intoryx <no-reply@intoryx.com>"
    assert message["Destination"] == {"ToAddresses": [seeded_data["admin_a"].email]}
    assert "https://intoryx.test/restablecer-password/" in message["Message"]["Body"]["Html"]["Data"]
    assert "expira en 5 minutos" in message["Message"]["Body"]["Html"]["Data"]


def test_forgot_password_keeps_generic_response_for_unknown_email(client, app):
    response = client.post(
        "/olvide-password",
        data={"email": "desconocido@test.com"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert (
        "Si el correo existe y esta habilitado" in response.get_data(as_text=True)
    )
    assert app.extensions["ses_client"].messages == []

    with app.app_context():
        assert PasswordResetToken.query.count() == 0


def test_forgot_password_rejects_superadmin_without_revealing_it(
    client, app, make_company, make_user
):
    superadmin = _make_superadmin(app, make_company, make_user)

    response = client.post(
        "/olvide-password",
        data={"email": superadmin["email"]},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert (
        "Si el correo existe y esta habilitado" in response.get_data(as_text=True)
    )
    assert app.extensions["ses_client"].messages == []

    with app.app_context():
        assert PasswordResetToken.query.filter_by(usuario_id=superadmin["id"]).count() == 0


def test_requesting_new_reset_invalidates_previous_token(client, app, seeded_data):
    client.post("/olvide-password", data={"email": seeded_data["admin_a"].email})
    first_token = _extract_reset_token(app.extensions["ses_client"].messages[-1])

    client.post("/olvide-password", data={"email": seeded_data["admin_a"].email})
    second_token = _extract_reset_token(app.extensions["ses_client"].messages[-1])

    assert first_token != second_token

    with app.app_context():
        records = PasswordResetToken.query.filter_by(usuario_id=seeded_data["admin_a"].id).all()
        assert len(records) == 2
        used_count = sum(1 for record in records if record.used_at is not None)
        assert used_count == 1
        assert get_valid_password_reset_token(first_token) is None
        assert get_valid_password_reset_token(second_token) is not None


def test_reset_password_updates_hash_and_invalidates_token(client, app, seeded_data):
    client.post("/olvide-password", data={"email": seeded_data["admin_a"].email})
    token = _extract_reset_token(app.extensions["ses_client"].messages[-1])

    response = client.post(
        f"/restablecer-password/{token}",
        data={"password": "nueva-clave-123", "password_confirm": "nueva-clave-123"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Contrasena actualizada correctamente" in response.get_data(as_text=True)

    with app.app_context():
        usuario = db.session.get(Usuario, seeded_data["admin_a"].id)
        assert check_password_hash(usuario.password, "nueva-clave-123")
        token_record = PasswordResetToken.query.filter_by(usuario_id=usuario.id).one()
        assert token_record.used_at is not None
        assert get_valid_password_reset_token(token) is None


def test_reset_password_rejects_expired_token(client, app, seeded_data):
    client.post("/olvide-password", data={"email": seeded_data["admin_a"].email})
    token = _extract_reset_token(app.extensions["ses_client"].messages[-1])

    with app.app_context():
        token_record = PasswordResetToken.query.filter_by(usuario_id=seeded_data["admin_a"].id).one()
        token_record.expires_at = token_record.expires_at - timedelta(minutes=10)
        db.session.commit()

    response = client.get(f"/restablecer-password/{token}", follow_redirects=True)

    assert response.status_code == 200
    assert "no es valido o ya expiro" in response.get_data(as_text=True)


def test_reset_password_rejects_reused_token(client, app, seeded_data):
    client.post("/olvide-password", data={"email": seeded_data["admin_a"].email})
    token = _extract_reset_token(app.extensions["ses_client"].messages[-1])

    first_response = client.post(
        f"/restablecer-password/{token}",
        data={"password": "nueva-clave-123", "password_confirm": "nueva-clave-123"},
        follow_redirects=True,
    )
    second_response = client.get(f"/restablecer-password/{token}", follow_redirects=True)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert "no es valido o ya expiro" in second_response.get_data(as_text=True)


def test_reset_password_rejects_mismatched_confirmation(client, app, seeded_data):
    client.post("/olvide-password", data={"email": seeded_data["admin_a"].email})
    token = _extract_reset_token(app.extensions["ses_client"].messages[-1])

    response = client.post(
        f"/restablecer-password/{token}",
        data={"password": "nueva-clave-123", "password_confirm": "otra-clave-123"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Las contrasenas no coinciden." in response.get_data(as_text=True)

    with app.app_context():
        token_record = PasswordResetToken.query.filter_by(usuario_id=seeded_data["admin_a"].id).one()
        assert token_record.used_at is None
