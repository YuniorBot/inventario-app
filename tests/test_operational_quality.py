from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from inventario_app.constants import (
    PDF_STATUS_FAILED,
    PDF_STATUS_PENDING,
    PDF_STATUS_PROCESSING,
)
from inventario_app.extensions import db
from inventario_app.models import Firma, Foto, Inmueble, Inventario, Observacion, Seccion
from inventario_app.services.media_service import get_pdf_object_key
from inventario_app.services import pdf_service


class FailingPdfQueue:
    def enqueue(self, *_args, **_kwargs):
        raise RuntimeError("redis down")


class RecordingPdfQueue:
    def __init__(self):
        self.calls = []

    def enqueue(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return SimpleNamespace(id=f"job-{len(self.calls)}")


def _force_async_pdf_queue(app):
    app.config["TESTING"] = False
    app.config["PDF_QUEUE_SYNC"] = False


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


def test_pdf_enqueue_failure_marks_failed(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)
    _force_async_pdf_queue(app)

    with patch(
        "inventario_app.services.pdf_queue_service._get_pdf_queue",
        return_value=FailingPdfQueue(),
    ):
        response = client.get(
            f"/inventario_pdf/{seeded_data['inventario_a'].id}", follow_redirects=True
        )

    assert response.status_code == 200
    assert "No se pudo generar el PDF en este momento." in response.get_data(
        as_text=True
    )

    with app.app_context():
        inventario = db.session.get(Inventario, seeded_data["inventario_a"].id)
        assert inventario.pdf_status == PDF_STATUS_FAILED
        assert "No se pudo iniciar" in inventario.pdf_error
        assert inventario.pdf_job_id is None


def test_failed_pdf_can_be_retried(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)
    _force_async_pdf_queue(app)
    queue = RecordingPdfQueue()

    with app.app_context():
        inventario = db.session.get(Inventario, seeded_data["inventario_a"].id)
        inventario.pdf_status = PDF_STATUS_FAILED
        inventario.pdf_error = "Fallo anterior"
        db.session.commit()
        db.session.remove()

    with patch(
        "inventario_app.services.pdf_queue_service._get_pdf_queue",
        return_value=queue,
    ):
        response = client.get(f"/inventario_pdf/{seeded_data['inventario_a'].id}")

    assert response.status_code == 302
    assert len(queue.calls) == 1

    with app.app_context():
        db.session.expire_all()
        inventario = db.session.get(Inventario, seeded_data["inventario_a"].id)
        assert inventario.pdf_status == PDF_STATUS_PENDING
        assert inventario.pdf_error is None
        assert inventario.pdf_job_id == "job-1"


def test_fresh_pending_pdf_is_not_duplicated(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)
    _force_async_pdf_queue(app)
    queue = RecordingPdfQueue()

    with app.app_context():
        inventario = db.session.get(Inventario, seeded_data["inventario_a"].id)
        inventario.pdf_status = PDF_STATUS_PENDING
        inventario.pdf_requested_at = datetime.now(timezone.utc)
        inventario.pdf_job_id = "existing-job"
        db.session.commit()
        db.session.remove()

    with patch(
        "inventario_app.services.pdf_queue_service._get_pdf_queue",
        return_value=queue,
    ):
        response = client.get(f"/inventario_pdf/{seeded_data['inventario_a'].id}")

    assert response.status_code == 302
    assert queue.calls == []

    with app.app_context():
        db.session.expire_all()
        inventario = db.session.get(Inventario, seeded_data["inventario_a"].id)
        assert inventario.pdf_status == PDF_STATUS_PENDING
        assert inventario.pdf_job_id == "existing-job"


@pytest.mark.parametrize("stale_status", [PDF_STATUS_PENDING, PDF_STATUS_PROCESSING])
def test_stale_active_pdf_can_be_retried(
    client, login, seeded_data, app, stale_status
):
    login(seeded_data["admin_a"].email)
    _force_async_pdf_queue(app)
    queue = RecordingPdfQueue()

    with app.app_context():
        inventario = db.session.get(Inventario, seeded_data["inventario_a"].id)
        inventario.pdf_status = stale_status
        inventario.pdf_requested_at = datetime.now(timezone.utc) - timedelta(
            seconds=301
        )
        inventario.pdf_job_id = "stale-job"
        db.session.commit()
        db.session.remove()

    with patch(
        "inventario_app.services.pdf_queue_service._get_pdf_queue",
        return_value=queue,
    ):
        response = client.get(f"/inventario_pdf/{seeded_data['inventario_a'].id}")

    assert response.status_code == 302
    assert len(queue.calls) == 1

    with app.app_context():
        db.session.expire_all()
        inventario = db.session.get(Inventario, seeded_data["inventario_a"].id)
        assert inventario.pdf_status == PDF_STATUS_PENDING
        assert inventario.pdf_error is None
        assert inventario.pdf_job_id == "job-1"


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


def test_pdf_places_description_between_media_summary_and_observations(
    app, seeded_data
):
    captured = []

    class FakeDoc:
        def __init__(self, filename, *args, **kwargs):
            self.filename = filename

        def build(self, elementos, **kwargs):
            captured.extend(elementos)
            with open(self.filename, "wb") as pdf_file:
                pdf_file.write(b"%PDF-1.4\n")

    with app.app_context():
        seccion = db.session.get(Seccion, seeded_data["seccion_a"].id)
        seccion.descripcion = "Descripcion visible"
        db.session.add(
            Observacion(seccion_id=seccion.id, comentario="Observacion visible")
        )
        db.session.add(Foto(seccion_id=seccion.id, archivo="orden.jpg"))
        db.session.commit()

        with (
            patch.object(pdf_service, "SimpleDocTemplate", FakeDoc),
            patch.object(pdf_service, "Paragraph", lambda text, _style: text),
            patch.object(pdf_service, "Spacer", lambda *_args: "SPACER"),
        ):
            pdf_service.build_inventory_pdf(
                seeded_data["inventario_a"],
                [seccion],
                [],
            )

    media_index = captured.index(
        "Evidencia multimedia registrada: 1 archivo(s). No incluida en el PDF."
    )
    descripcion_index = captured.index("<b>Descripcion:</b> Descripcion visible")
    observacion_index = captured.index("<b>Observacion:</b> Observacion visible")

    assert media_index < descripcion_index < observacion_index


def test_pdf_shows_optional_signature_contact_fields(app, seeded_data):
    captured = []

    class FakeDoc:
        def __init__(self, filename, *args, **kwargs):
            self.filename = filename

        def build(self, elementos, **kwargs):
            captured.extend(elementos)
            with open(self.filename, "wb") as pdf_file:
                pdf_file.write(b"%PDF-1.4\n")

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


def test_pdf_generation_summarizes_media_without_embedding_images(app, seeded_data):
    captured = []

    class FakeDoc:
        def __init__(self, filename, *args, **kwargs):
            self.filename = filename

        def build(self, elementos, **kwargs):
            captured.extend(elementos)
            with open(self.filename, "wb") as pdf_file:
                pdf_file.write(b"%PDF-1.4\n")

    with app.app_context():
        seccion = db.session.get(Seccion, seeded_data["seccion_a"].id)
        for index in range(120):
            filename = f"masiva-{index}.jpg"
            db.session.add(Foto(seccion_id=seccion.id, archivo=filename))
        db.session.commit()

        with (
            patch.object(pdf_service, "SimpleDocTemplate", FakeDoc),
            patch.object(pdf_service, "Paragraph", lambda text, _style: text),
            patch.object(pdf_service, "Spacer", lambda *_args: "SPACER"),
            patch.object(pdf_service, "Image") as image,
        ):
            filename = pdf_service.build_inventory_pdf(
                seeded_data["inventario_a"],
                [seccion],
                [],
            )

    assert (
        app.config["S3_BUCKET_NAME"],
        get_pdf_object_key(filename),
    ) in app.extensions["s3_client"].objects
    assert (
        "Evidencia multimedia registrada: 120 archivo(s). No incluida en el PDF."
        in captured
    )
    image.assert_not_called()


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
