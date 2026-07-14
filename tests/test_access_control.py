from inventario_app.extensions import db
from inventario_app.models import Observacion, Seccion


def test_viewer_cannot_create_inmueble(client, login, seeded_data):
    login(seeded_data["viewer_a"].email)

    response = client.post(
        "/crear",
        data={
            "direccion": "Nueva direccion",
            "propietario": "Nuevo propietario",
            "fecha": "2026-04-10",
        },
    )

    assert response.status_code == 403


def test_viewer_cannot_edit_inmueble_address(client, login, seeded_data):
    login(seeded_data["viewer_a"].email)

    response = client.post(
        f"/editar_direccion_inmueble/{seeded_data['inmueble_a'].id}",
        data={"direccion": "Cambio no permitido"},
    )

    assert response.status_code == 403


def test_viewer_cannot_edit_inmueble_owner(client, login, seeded_data):
    login(seeded_data["viewer_a"].email)

    response = client.post(
        f"/editar_propietario_inmueble/{seeded_data['inmueble_a'].id}",
        data={"propietario": "Cambio no permitido"},
    )

    assert response.status_code == 403


def test_viewer_cannot_edit_inmueble_reception_date(client, login, seeded_data):
    login(seeded_data["viewer_a"].email)

    response = client.post(
        f"/editar_fecha_recepcion_inmueble/{seeded_data['inmueble_a'].id}",
        data={"fecha_recepcion": "2026-05-20"},
    )

    assert response.status_code == 403


def test_editor_cannot_open_user_admin_panel(client, login, seeded_data):
    login(seeded_data["editor_a"].email)

    response = client.get("/usuarios")

    assert response.status_code == 403


def test_admin_cannot_access_other_company_inmueble(client, login, seeded_data):
    login(seeded_data["admin_a"].email)

    response = client.get(f"/inmueble/{seeded_data['inmueble_b'].id}")

    assert response.status_code == 403


def test_admin_cannot_edit_other_company_inmueble_address(client, login, seeded_data):
    login(seeded_data["admin_a"].email)

    response = client.post(
        f"/editar_direccion_inmueble/{seeded_data['inmueble_b'].id}",
        data={"direccion": "Cambio cruzado"},
    )

    assert response.status_code == 403


def test_admin_cannot_edit_other_company_inmueble_owner(client, login, seeded_data):
    login(seeded_data["admin_a"].email)

    response = client.post(
        f"/editar_propietario_inmueble/{seeded_data['inmueble_b'].id}",
        data={"propietario": "Cambio cruzado"},
    )

    assert response.status_code == 403


def test_admin_cannot_edit_other_company_inmueble_reception_date(
    client, login, seeded_data
):
    login(seeded_data["admin_a"].email)

    response = client.post(
        f"/editar_fecha_recepcion_inmueble/{seeded_data['inmueble_b'].id}",
        data={"fecha_recepcion": "2026-05-20"},
    )

    assert response.status_code == 403


def test_viewer_cannot_edit_inventory_name(client, login, seeded_data):
    login(seeded_data["viewer_a"].email)

    response = client.post(
        f"/editar_nombre_inventario/{seeded_data['inventario_a'].id}",
        data={"nombre": "Cambio no permitido"},
    )

    assert response.status_code == 403


def test_viewer_cannot_edit_inventory_date(client, login, seeded_data):
    login(seeded_data["viewer_a"].email)

    response = client.post(
        f"/editar_fecha_inventario/{seeded_data['inventario_a'].id}",
        data={"fecha": "2026-06-15"},
    )

    assert response.status_code == 403


def test_admin_cannot_edit_other_company_inventory_name(client, login, seeded_data):
    login(seeded_data["admin_a"].email)

    response = client.post(
        f"/editar_nombre_inventario/{seeded_data['inventario_b'].id}",
        data={"nombre": "Cambio cruzado"},
    )

    assert response.status_code == 403


def test_admin_cannot_edit_other_company_inventory_date(client, login, seeded_data):
    login(seeded_data["admin_a"].email)

    response = client.post(
        f"/editar_fecha_inventario/{seeded_data['inventario_b'].id}",
        data={"fecha": "2026-06-15"},
    )

    assert response.status_code == 403


def test_viewer_cannot_duplicate_inventory(client, login, seeded_data):
    login(seeded_data["viewer_a"].email)

    response = client.post(f"/duplicar_inventario/{seeded_data['inventario_a'].id}")

    assert response.status_code == 403


def test_admin_cannot_duplicate_other_company_inventory(client, login, seeded_data):
    login(seeded_data["admin_a"].email)

    response = client.post(f"/duplicar_inventario/{seeded_data['inventario_b'].id}")

    assert response.status_code == 403


def test_viewer_cannot_edit_observation(client, login, seeded_data, app):
    login(seeded_data["viewer_a"].email)

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
        data={"comentario": "Cambio no permitido"},
    )

    assert response.status_code == 403


def test_viewer_cannot_delete_observation(client, login, seeded_data, app):
    login(seeded_data["viewer_a"].email)

    with app.app_context():
        observacion = Observacion(
            seccion_id=seeded_data["seccion_a"].id,
            comentario="Texto original",
        )
        db.session.add(observacion)
        db.session.commit()
        observacion_id = observacion.id

    response = client.post(f"/eliminar_observacion/{observacion_id}")

    assert response.status_code == 403


def test_admin_cannot_edit_other_company_observation(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)

    with app.app_context():
        seccion_b = Seccion(inventario_id=seeded_data["inventario_b"].id, nombre="Sala B")
        db.session.add(seccion_b)
        db.session.flush()
        observacion = Observacion(
            seccion_id=seccion_b.id,
            comentario="Texto empresa B",
        )
        db.session.add(observacion)
        db.session.commit()
        observacion_id = observacion.id

    response = client.post(
        f"/editar_observacion/{observacion_id}",
        data={"comentario": "Cambio cruzado"},
    )

    assert response.status_code == 403


def test_admin_cannot_delete_other_company_observation(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)

    with app.app_context():
        seccion_b = Seccion(inventario_id=seeded_data["inventario_b"].id, nombre="Sala B")
        db.session.add(seccion_b)
        db.session.flush()
        observacion = Observacion(
            seccion_id=seccion_b.id,
            comentario="Texto empresa B",
        )
        db.session.add(observacion)
        db.session.commit()
        observacion_id = observacion.id

    response = client.post(f"/eliminar_observacion/{observacion_id}")

    assert response.status_code == 403


def test_public_inventory_token_is_accessible_without_login(client, seeded_data):
    response = client.get(f"/publico/{seeded_data['inventario_a'].token}")

    assert response.status_code == 200
    assert seeded_data["inventario_a"].nombre in response.get_data(as_text=True)
