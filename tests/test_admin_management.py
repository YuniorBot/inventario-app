from werkzeug.security import check_password_hash

from inventario_app.constants import (
    INTERNAL_COMPANY_SLUG,
    ROLE_ADMIN,
    ROLE_EDITOR,
    ROLE_SUPERADMIN,
    ROLE_VIEWER,
    STATUS_CANCELLED,
    STATUS_SUSPENDED,
)
from inventario_app.extensions import db
from inventario_app.models import Empresa, Usuario


def make_superadmin(app, make_company, make_user):
    with app.app_context():
        interna = Empresa.query.filter_by(slug=INTERNAL_COMPANY_SLUG).first()
        if not interna:
            interna = make_company("Plataforma Interna", INTERNAL_COMPANY_SLUG)
        usuario = make_user(
            interna.id,
            "Super Admin",
            "superadmin@test.com",
            rol=ROLE_SUPERADMIN,
        )
        return {"id": usuario.id, "email": usuario.email}


def test_superadmin_can_create_company_with_primary_admin(
    client, login, app, make_company, make_user
):
    superadmin = make_superadmin(app, make_company, make_user)
    login(superadmin["email"])

    response = client.post(
        "/superadmin/empresas",
        data={
            "empresa": "Empresa Nueva",
            "nombre": "Admin Nueva",
            "email": "admin-nueva@test.com",
            "password": "temporal123",
            "estado": STATUS_SUSPENDED,
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        empresa = Empresa.query.filter_by(nombre="Empresa Nueva").first()
        assert empresa is not None
        assert empresa.estado == STATUS_SUSPENDED
        admin = Usuario.query.filter_by(email="admin-nueva@test.com").first()
        assert admin is not None
        assert admin.empresa_id == empresa.id
        assert admin.rol == ROLE_ADMIN


def test_superadmin_status_change_clears_company_mode(
    client, login, seeded_data, app, make_company, make_user
):
    superadmin = make_superadmin(app, make_company, make_user)
    login(superadmin["email"])

    with client.session_transaction() as session:
        session["superadmin_company_id"] = seeded_data["empresa_a"].id

    response = client.post(
        f"/superadmin/empresas/{seeded_data['empresa_a'].id}/estado",
        data={"estado": STATUS_CANCELLED},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        empresa = db.session.get(Empresa, seeded_data["empresa_a"].id)
        assert empresa.estado == STATUS_CANCELLED
        assert empresa.activo is False

    with client.session_transaction() as session:
        assert "superadmin_company_id" not in session


def test_superadmin_can_reset_primary_admin_password(
    client, login, seeded_data, app, make_company, make_user
):
    superadmin = make_superadmin(app, make_company, make_user)
    login(superadmin["email"])

    response = client.post(
        f"/superadmin/empresas/{seeded_data['empresa_a'].id}/admin-password",
        data={"password": "temporal-nueva-123"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        admin = db.session.get(Usuario, seeded_data["admin_a"].id)
        assert check_password_hash(admin.password, "temporal-nueva-123")


def test_superadmin_cannot_reset_primary_admin_password_with_short_password(
    client, login, seeded_data, app, make_company, make_user
):
    superadmin = make_superadmin(app, make_company, make_user)
    login(superadmin["email"])

    with app.app_context():
        original_hash = db.session.get(Usuario, seeded_data["admin_a"].id).password

    response = client.post(
        f"/superadmin/empresas/{seeded_data['empresa_a'].id}/admin-password",
        data={"password": "123"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "La nueva contrasena debe tener al menos 6 caracteres" in response.get_data(
        as_text=True
    )
    with app.app_context():
        admin = db.session.get(Usuario, seeded_data["admin_a"].id)
        assert admin.password == original_hash


def test_superadmin_can_enter_and_exit_company_mode(
    client, login, seeded_data, app, make_company, make_user
):
    superadmin = make_superadmin(app, make_company, make_user)
    login(superadmin["email"])

    enter_response = client.post(
        f"/superadmin/empresas/{seeded_data['empresa_a'].id}/entrar",
        follow_redirects=False,
    )
    assert enter_response.status_code == 302
    assert enter_response.headers["Location"].endswith("/")

    with client.session_transaction() as session:
        assert session.get("superadmin_company_id") == seeded_data["empresa_a"].id

    exit_response = client.post("/superadmin/salir-empresa", follow_redirects=False)
    assert exit_response.status_code == 302

    with client.session_transaction() as session:
        assert "superadmin_company_id" not in session


def test_admin_can_change_employee_role(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)

    response = client.post(
        f"/usuarios/{seeded_data['viewer_a'].id}/rol",
        data={"rol": ROLE_EDITOR},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        usuario = db.session.get(Usuario, seeded_data["viewer_a"].id)
        assert usuario.rol == ROLE_EDITOR


def test_admin_cannot_change_own_role(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)

    response = client.post(
        f"/usuarios/{seeded_data['admin_a'].id}/rol",
        data={"rol": ROLE_VIEWER},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "No puedes cambiar tu propio rol" in response.get_data(as_text=True)
    with app.app_context():
        usuario = db.session.get(Usuario, seeded_data["admin_a"].id)
        assert usuario.rol == ROLE_ADMIN


def test_admin_can_toggle_employee_status(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)

    response = client.post(
        f"/usuarios/{seeded_data['viewer_a'].id}/estado",
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        usuario = db.session.get(Usuario, seeded_data["viewer_a"].id)
        assert usuario.activo is False


def test_admin_can_reset_employee_password(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)

    response = client.post(
        f"/usuarios/{seeded_data['viewer_a'].id}/password",
        data={"password": "nueva-clave-123"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        usuario = db.session.get(Usuario, seeded_data["viewer_a"].id)
        assert check_password_hash(usuario.password, "nueva-clave-123")


def test_admin_cannot_reset_primary_admin_password(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)

    with app.app_context():
        original_hash = db.session.get(Usuario, seeded_data["admin_a"].id).password

    response = client.post(
        f"/usuarios/{seeded_data['admin_a'].id}/password",
        data={"password": "otra-clave-123"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "La cuenta principal no cambia su contrasena" in response.get_data(
        as_text=True
    )
    with app.app_context():
        usuario = db.session.get(Usuario, seeded_data["admin_a"].id)
        assert usuario.password == original_hash
