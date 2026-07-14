from datetime import date

from inventario_app.extensions import db
from inventario_app.models import Foto, Inmueble, Inventario, Observacion, Seccion
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

    with app.app_context():
        seeded_data["inventario_a"].pdf_status = "ready"
        seeded_data["inventario_a"].pdf_filename = "inventario_1.pdf"
        db.session.commit()

    response = client.post(
        f"/editar_direccion_inmueble/{seeded_data['inmueble_a'].id}",
        data={"direccion": "Calle A actualizada"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        inmueble = db.session.get(Inmueble, seeded_data["inmueble_a"].id)
        inventario = db.session.get(Inventario, seeded_data["inventario_a"].id)
        assert inmueble.direccion == "Calle A actualizada"
        assert inventario.pdf_status == "not_started"
        assert inventario.pdf_filename is None


def test_admin_can_edit_inmueble_owner(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)

    with app.app_context():
        seeded_data["inventario_a"].pdf_status = "ready"
        seeded_data["inventario_a"].pdf_filename = "inventario_1.pdf"
        db.session.commit()

    response = client.post(
        f"/editar_propietario_inmueble/{seeded_data['inmueble_a'].id}",
        data={"propietario": "Nuevo propietario"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        inmueble = db.session.get(Inmueble, seeded_data["inmueble_a"].id)
        inventario = db.session.get(Inventario, seeded_data["inventario_a"].id)
        assert inmueble.propietario == "Nuevo propietario"
        assert inventario.pdf_status == "not_started"
        assert inventario.pdf_filename is None


def test_admin_can_edit_inmueble_reception_date(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)

    with app.app_context():
        seeded_data["inventario_a"].pdf_status = "ready"
        seeded_data["inventario_a"].pdf_filename = "inventario_1.pdf"
        db.session.commit()

    response = client.post(
        f"/editar_fecha_recepcion_inmueble/{seeded_data['inmueble_a'].id}",
        data={"fecha_recepcion": "2026-05-20"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        inmueble = db.session.get(Inmueble, seeded_data["inmueble_a"].id)
        inventario = db.session.get(Inventario, seeded_data["inventario_a"].id)
        assert inmueble.fecha_recepcion == date(2026, 5, 20)
        assert inventario.pdf_status == "not_started"
        assert inventario.pdf_filename is None


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


def test_empty_inmueble_owner_is_rejected(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)

    response = client.post(
        f"/editar_propietario_inmueble/{seeded_data['inmueble_a'].id}",
        data={"propietario": "   "},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        inmueble = db.session.get(Inmueble, seeded_data["inmueble_a"].id)
        assert inmueble.propietario == "Owner"


def test_invalid_inmueble_reception_date_is_rejected(
    client, login, seeded_data, app
):
    login(seeded_data["admin_a"].email)

    response = client.post(
        f"/editar_fecha_recepcion_inmueble/{seeded_data['inmueble_a'].id}",
        data={"fecha_recepcion": "fecha-invalida"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        inmueble = db.session.get(Inmueble, seeded_data["inmueble_a"].id)
        assert inmueble.fecha_recepcion == date(2026, 4, 1)


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
        assert inventario.created_by_id == seeded_data["admin_a"].id
        assert inventario.creador.nombre == "Admin A"
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


def test_admin_can_edit_inventory_name(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)

    response = client.post(
        f"/editar_nombre_inventario/{seeded_data['inventario_a'].id}",
        data={"nombre": "Inventario actualizado"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        inventario = db.session.get(Inventario, seeded_data["inventario_a"].id)
        assert inventario.nombre == "Inventario actualizado"


def test_admin_can_edit_inventory_date(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)

    with app.app_context():
        seeded_data["inventario_a"].pdf_status = "ready"
        seeded_data["inventario_a"].pdf_filename = "inventario_1.pdf"
        db.session.commit()

    response = client.post(
        f"/editar_fecha_inventario/{seeded_data['inventario_a'].id}",
        data={"fecha": "2026-06-15"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        inventario = db.session.get(Inventario, seeded_data["inventario_a"].id)
        assert inventario.fecha == date(2026, 6, 15)
        assert inventario.pdf_status == "not_started"
        assert inventario.pdf_filename is None


def test_empty_inventory_name_is_rejected(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)

    response = client.post(
        f"/editar_nombre_inventario/{seeded_data['inventario_a'].id}",
        data={"nombre": "   "},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        inventario = db.session.get(Inventario, seeded_data["inventario_a"].id)
        assert inventario.nombre == "Entrega inicial"


def test_invalid_inventory_date_is_rejected(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)

    response = client.post(
        f"/editar_fecha_inventario/{seeded_data['inventario_a'].id}",
        data={"fecha": "fecha-invalida"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        inventario = db.session.get(Inventario, seeded_data["inventario_a"].id)
        assert inventario.fecha == date(2026, 4, 2)


def test_admin_can_duplicate_inventory_structure_only(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)

    with app.app_context():
        original = db.session.get(Inventario, seeded_data["inventario_a"].id)
        seccion = db.session.get(Seccion, seeded_data["seccion_a"].id)
        seccion.descripcion = "No copiar descripcion"
        db.session.add(Foto(seccion_id=seccion.id, archivo="foto.jpg"))
        db.session.add(
            Observacion(seccion_id=seccion.id, comentario="No copiar observacion")
        )
        db.session.commit()
        original_id = original.id
        original_token = original.token

    response = client.post(
        f"/duplicar_inventario/{original_id}",
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        nuevo = (
            Inventario.query.filter_by(inmueble_id=seeded_data["inmueble_a"].id)
            .order_by(Inventario.id.desc())
            .first()
        )
        assert nuevo.id != original_id
        assert nuevo.nombre == "Entrega inicial - copia"
        assert nuevo.created_by_id == seeded_data["admin_a"].id
        assert nuevo.token != original_token
        assert response.headers["Location"].endswith(f"/inventario/{nuevo.id}")

        secciones_nuevas = (
            Seccion.query.filter_by(inventario_id=nuevo.id).order_by(Seccion.id.asc()).all()
        )
        assert [seccion.nombre for seccion in secciones_nuevas] == ["Sala A"]
        assert all(seccion.descripcion is None for seccion in secciones_nuevas)
        assert sum(len(seccion.fotos) for seccion in secciones_nuevas) == 0
        assert sum(len(seccion.observaciones) for seccion in secciones_nuevas) == 0


def test_inmueble_inventory_card_shows_creator_only_when_present(
    client, login, seeded_data, app
):
    login(seeded_data["admin_a"].email)

    client.post(
        f"/crear_inventario/{seeded_data['inmueble_a'].id}",
        data={"nombre": "Entrega con creador", "fecha": "2026-04-12"},
        follow_redirects=False,
    )

    response = client.get(f"/inmueble/{seeded_data['inmueble_a'].id}")

    assert response.status_code == 200
    assert b"Creado por Admin A" in response.data
    assert response.data.count(b"Creado por") == 1


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


def test_admin_can_edit_observation(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)

    with app.app_context():
        observacion = Observacion(
            seccion_id=seeded_data["seccion_a"].id,
            comentario="Texto original",
        )
        db.session.add(observacion)
        db.session.commit()
        observacion_id = observacion.id

    response = client.post(
        f"/editar_observacion/{observacion_id}",
        data={"comentario": "Texto actualizado"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        observacion = db.session.get(Observacion, observacion_id)
        assert observacion.comentario == "Texto actualizado"


def test_empty_observation_edit_is_rejected(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)

    with app.app_context():
        observacion = Observacion(
            seccion_id=seeded_data["seccion_a"].id,
            comentario="Texto original",
        )
        db.session.add(observacion)
        db.session.commit()
        observacion_id = observacion.id

    response = client.post(
        f"/editar_observacion/{observacion_id}",
        data={"comentario": "   "},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        observacion = db.session.get(Observacion, observacion_id)
        assert observacion.comentario == "Texto original"


def test_admin_can_delete_observation(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)

    with app.app_context():
        observacion = Observacion(
            seccion_id=seeded_data["seccion_a"].id,
            comentario="Texto a eliminar",
        )
        db.session.add(observacion)
        db.session.commit()
        observacion_id = observacion.id

    response = client.post(
        f"/eliminar_observacion/{observacion_id}",
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(Observacion, observacion_id) is None


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
