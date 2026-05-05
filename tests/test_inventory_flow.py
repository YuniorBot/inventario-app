from inventario_app.extensions import db
from inventario_app.models import Foto, Inmueble, Inventario, Seccion
from inventario_app.services.media_service import get_upload_object_key


def test_admin_can_create_inmueble(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)

    response = client.post(
        "/crear",
        data={
            "direccion": "Carrera 123",
            "propietario": "Maria",
            "fecha": "2026-04-10",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        inmueble = Inmueble.query.filter_by(direccion="Carrera 123").first()
        assert inmueble is not None
        assert inmueble.empresa_id == seeded_data["empresa_a"].id


def test_admin_can_edit_inmueble_address(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)

    response = client.post(
        f"/editar_direccion_inmueble/{seeded_data['inmueble_a'].id}",
        data={"direccion": "Calle A actualizada"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        inmueble = db.session.get(Inmueble, seeded_data["inmueble_a"].id)
        assert inmueble.direccion == "Calle A actualizada"


def test_empty_inmueble_address_is_rejected(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)

    response = client.post(
        f"/editar_direccion_inmueble/{seeded_data['inmueble_a'].id}",
        data={"direccion": "   "},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        inmueble = db.session.get(Inmueble, seeded_data["inmueble_a"].id)
        assert inmueble.direccion == "Calle A"


def test_admin_can_create_inventory_with_default_sections(
    client, login, seeded_data, app
):
    login(seeded_data["admin_a"].email)

    response = client.post(
        f"/crear_inventario/{seeded_data['inmueble_a'].id}",
        data={"nombre": "Entrega abril", "fecha": "2026-04-11"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        inventario = Inventario.query.filter_by(nombre="Entrega abril").first()
        assert inventario is not None
        secciones = Seccion.query.filter_by(inventario_id=inventario.id).all()
        assert len(secciones) == 7
        assert {seccion.nombre for seccion in secciones} == {
            "Fachada",
            "Sala",
            "Comedor",
            "Cocina",
            "Baños",
            "Habitación principal",
            "Habitación auxiliar",
        }


def test_admin_can_edit_section_name(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)

    response = client.post(
        f"/editar_seccion/{seeded_data['seccion_a'].id}",
        data={"nombre": "Sala remodelada"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        seccion = db.session.get(Seccion, seeded_data["seccion_a"].id)
        assert seccion.nombre == "Sala remodelada"


def test_admin_can_create_manual_section(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)

    response = client.post(
        f"/crear_seccion/{seeded_data['inventario_a'].id}",
        data={"nombre": "Balcon"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        assert (
            Seccion.query.filter_by(
                inventario_id=seeded_data["inventario_a"].id,
                nombre="Balcon",
            ).count()
            == 1
        )


def test_admin_can_save_section_description(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)

    response = client.post(
        f"/guardar_descripcion/{seeded_data['seccion_a'].id}",
        data={"descripcion": "Estado general del baño y accesorios completos."},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        seccion = db.session.get(Seccion, seeded_data["seccion_a"].id)
        assert seccion.descripcion == "Estado general del baño y accesorios completos."


def test_deleting_section_removes_uploaded_files(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)

    with app.app_context():
        foto = Foto(seccion_id=seeded_data["seccion_a"].id, archivo="temporal.png")
        db.session.add(foto)
        db.session.commit()

    object_key = get_upload_object_key("temporal.png")
    app.extensions["s3_client"].put_object(
        Bucket=app.config["S3_BUCKET_NAME"],
        Key=object_key,
        Body=b"temporary file",
        ContentType="image/png",
    )

    response = client.post(
        f"/eliminar_seccion/{seeded_data['seccion_a'].id}",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert (app.config["S3_BUCKET_NAME"], object_key) not in app.extensions["s3_client"].objects
    with app.app_context():
        assert db.session.get(Seccion, seeded_data["seccion_a"].id) is None
        assert Foto.query.filter_by(seccion_id=seeded_data["seccion_a"].id).count() == 0


def test_viewer_can_open_inventory_without_signature_canvas(client, login, seeded_data):
    login(seeded_data["viewer_a"].email)

    response = client.get(f"/inventario/{seeded_data['inventario_a'].id}")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="canvas"' not in body
    assert "if (canvas)" in body
