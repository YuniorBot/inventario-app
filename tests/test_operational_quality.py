from io import BytesIO
from unittest.mock import patch

from inventario_app.extensions import db
from inventario_app.models import Firma, Foto, Inmueble, Observacion, Seccion
from inventario_app.services.media_service import get_upload_object_key
from inventario_app.services import pdf_service


def test_dashboard_paginates_large_property_list(
    client, login, seeded_data, make_inmueble
):
    for index in range(15):
        make_inmueble(seeded_data["empresa_a"].id, direccion=f"Extra {index}")

    login(seeded_data["admin_a"].email)
    response = client.get("/?page=2")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "P\u00e1gina 2 de 2" in body or "Página 2 de 2" in body


def test_public_view_paginates_sections(client, seeded_data, make_seccion):
    for index in range(12):
        seccion = make_seccion(seeded_data["inventario_a"].id, nombre=f"Extra {index}")
        seccion.descripcion = f"Contenido {index}"
        db.session.commit()

    response = client.get(f"/publico/{seeded_data['inventario_a'].token}?page=2")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "P\u00e1gina 2 de 2" in body or "Página 2 de 2" in body


def test_pdf_generation_failure_returns_message(client, login, seeded_data):
    login(seeded_data["admin_a"].email)

    with patch(
        "inventario_app.jobs.pdf_jobs.build_inventory_pdf",
        side_effect=RuntimeError("boom"),
    ):
        response = client.get(
            f"/inventario_pdf/{seeded_data['inventario_a'].id}", follow_redirects=True
        )

    assert response.status_code == 200
    assert "No se pudo generar el PDF en este momento." in response.get_data(
        as_text=True
    )


def test_signature_rejects_non_image_payload(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)

    response = client.post(
        f"/guardar_firma/{seeded_data['inventario_a'].id}",
        data={"nombre": "Tester", "firma": "data:text/plain;base64,aG9sYQ=="},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Firma invalida." in response.get_data(as_text=True)
    with app.app_context():
        assert (
            Firma.query.filter_by(inventario_id=seeded_data["inventario_a"].id).count()
            == 0
        )


def test_signature_saves_optional_contact_fields(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)

    response = client.post(
        f"/guardar_firma/{seeded_data['inventario_a'].id}",
        data={
            "nombre": "Tester",
            "cedula": "1234567890",
            "celular": "3001234567",
            "correo": "tester@example.com",
            "firma": "data:image/png;base64,aGVsbG8=",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        firma = Firma.query.filter_by(
            inventario_id=seeded_data["inventario_a"].id
        ).one()
        assert firma.nombre == "Tester"
        assert firma.cedula == "1234567890"
        assert firma.celular == "3001234567"
        assert firma.correo == "tester@example.com"


def test_signature_rejects_invalid_email(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)

    response = client.post(
        f"/guardar_firma/{seeded_data['inventario_a'].id}",
        data={
            "nombre": "Tester",
            "correo": "correo-invalido",
            "firma": "data:image/png;base64,aGVsbG8=",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Correo invalido." in response.get_data(as_text=True)
    with app.app_context():
        assert (
            Firma.query.filter_by(inventario_id=seeded_data["inventario_a"].id).count()
            == 0
        )


def test_pdf_only_uses_sections_with_observations(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)

    with app.app_context():
        db.session.add(
            Observacion(
                seccion_id=seeded_data["seccion_a"].id,
                comentario="Detalle relevante",
            )
        )
        db.session.commit()

    with patch(
        "inventario_app.jobs.pdf_jobs.build_inventory_pdf"
    ) as build_pdf:
        build_pdf.return_value = "inventario_1.pdf"

        response = client.get(
            f"/inventario_pdf/{seeded_data['inventario_a'].id}", follow_redirects=False
        )

    assert response.status_code == 302
    _, secciones, _ = build_pdf.call_args.args
    assert [seccion.nombre for seccion in secciones] == [
        seeded_data["seccion_a"].nombre
    ]


def test_pdf_only_uses_sections_with_media(
    client, login, seeded_data, app, make_seccion
):
    login(seeded_data["admin_a"].email)
    extra = make_seccion(seeded_data["inventario_a"].id, nombre="Baños")

    with app.app_context():
        db.session.add(Foto(seccion_id=extra.id, archivo="evidencia.png"))
        db.session.commit()

    with patch(
        "inventario_app.jobs.pdf_jobs.build_inventory_pdf"
    ) as build_pdf:
        build_pdf.return_value = "inventario_1.pdf"

        response = client.get(
            f"/inventario_pdf/{seeded_data['inventario_a'].id}", follow_redirects=False
        )

    assert response.status_code == 302
    _, secciones, _ = build_pdf.call_args.args
    assert [seccion.nombre for seccion in secciones] == ["Baños"]


def test_pdf_only_uses_sections_with_description(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)

    save_response = client.post(
        f"/guardar_descripcion/{seeded_data['seccion_a'].id}",
        data={"descripcion": "Solo descripcion"},
        follow_redirects=False,
    )

    with patch(
        "inventario_app.jobs.pdf_jobs.build_inventory_pdf"
    ) as build_pdf:
        build_pdf.return_value = "inventario_1.pdf"

        response = client.get(
            f"/inventario_pdf/{seeded_data['inventario_a'].id}", follow_redirects=False
        )

    assert save_response.status_code == 302
    assert response.status_code == 302
    _, secciones, _ = build_pdf.call_args.args
    assert [seccion.nombre for seccion in secciones] == [
        seeded_data["seccion_a"].nombre
    ]


def test_pdf_places_description_between_media_and_observations(app, seeded_data):
    captured = []

    class FakeDoc:
        def __init__(self, *args, **kwargs):
            pass

        def build(self, elementos, **kwargs):
            captured.extend(elementos)

    class FakeImage:
        def __init__(self, source):
            self.source = source

        def _restrictSize(self, *_args):
            return None

    with app.app_context():
        seccion = db.session.get(Seccion, seeded_data["seccion_a"].id)
        seccion.descripcion = "Descripcion visible"
        db.session.add(
            Observacion(seccion_id=seccion.id, comentario="Observacion visible")
        )
        db.session.add(Foto(seccion_id=seccion.id, archivo="orden.jpg"))
        db.session.commit()

        app.extensions["s3_client"].put_object(
            Bucket=app.config["S3_BUCKET_NAME"],
            Key=get_upload_object_key("orden.jpg"),
            Body=b"fake image bytes",
            ContentType="image/jpeg",
        )

        with (
            patch.object(pdf_service, "SimpleDocTemplate", FakeDoc),
            patch.object(pdf_service, "Paragraph", lambda text, _style: text),
            patch.object(pdf_service, "Spacer", lambda *_args: "SPACER"),
            patch.object(pdf_service, "Image", FakeImage),
            patch.object(
                pdf_service, "_prepare_pdf_image", lambda _payload: BytesIO(b"image")
            ),
            patch.object(
                pdf_service,
                "_append_gallery",
                lambda elementos, _galeria: elementos.append("GALERIA"),
            ),
        ):
            pdf_service.build_inventory_pdf(
                seeded_data["inventario_a"],
                [seccion],
                [],
            )

    gallery_index = captured.index("GALERIA")
    descripcion_index = captured.index("<b>Descripcion:</b> Descripcion visible")
    observacion_index = captured.index("<b>Observacion:</b> Observacion visible")

    assert gallery_index < descripcion_index < observacion_index


def test_pdf_shows_optional_signature_contact_fields(app, seeded_data):
    captured = []

    class FakeDoc:
        def __init__(self, *args, **kwargs):
            pass

        def build(self, elementos, **kwargs):
            captured.extend(elementos)

    with app.app_context():
        firma = Firma(
            inventario_id=seeded_data["inventario_a"].id,
            nombre="Laura Perez",
            cedula="1234567890",
            celular="3001234567",
            correo="laura@example.com",
            imagen="data:image/png;base64,invalido",
        )

        with (
            patch.object(pdf_service, "SimpleDocTemplate", FakeDoc),
            patch.object(pdf_service, "Paragraph", lambda text, _style: text),
            patch.object(pdf_service, "Spacer", lambda *_args: "SPACER"),
            patch.object(pdf_service, "PageBreak", lambda: "PAGEBREAK"),
        ):
            pdf_service.build_inventory_pdf(
                seeded_data["inventario_a"],
                [],
                [firma],
            )

    assert "<b>Firmado por:</b> Laura Perez" in captured
    assert "<b>Cédula:</b> 1234567890" in captured
    assert "<b>Celular:</b> 3001234567" in captured
    assert "<b>Correo electrónico:</b> laura@example.com" in captured


def test_public_view_shows_section_description(client, login, seeded_data):
    login(seeded_data["admin_a"].email)
    save_response = client.post(
        f"/guardar_descripcion/{seeded_data['seccion_a'].id}",
        data={"descripcion": "Descripcion publica"},
        follow_redirects=False,
    )

    response = client.get(f"/publico/{seeded_data['inventario_a'].token}")
    body = response.get_data(as_text=True)

    assert save_response.status_code == 302
    assert response.status_code == 200
    assert "Descripcion publica" in body
    assert "No hay descripción cargada en esta sección." not in body


def test_public_view_only_shows_sections_with_content(
    client, seeded_data, app, make_seccion
):
    with app.app_context():
        vacia = make_seccion(seeded_data["inventario_a"].id, nombre="Vacia")
        con_descripcion = make_seccion(seeded_data["inventario_a"].id, nombre="Baños")
        con_descripcion.descripcion = "Contenido visible"
        db.session.commit()
        vacia_nombre = vacia.nombre
        con_descripcion_nombre = con_descripcion.nombre

    response = client.get(f"/publico/{seeded_data['inventario_a'].token}")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Sala A" not in body
    assert vacia_nombre not in body
    assert con_descripcion_nombre in body
    assert "Contenido visible" in body
