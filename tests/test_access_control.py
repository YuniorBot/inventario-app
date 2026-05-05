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


def test_public_inventory_token_is_accessible_without_login(client, seeded_data):
    response = client.get(f"/publico/{seeded_data['inventario_a'].token}")

    assert response.status_code == 200
    assert seeded_data["inventario_a"].nombre in response.get_data(as_text=True)
