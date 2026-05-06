from io import BytesIO

from PIL import Image

from inventario_app.extensions import db
from inventario_app.models import Foto
from inventario_app.services.media_service import get_pdf_object_key, get_upload_object_key


def make_image_bytes(format="PNG", size=(40, 30), color=(24, 64, 180)):
    payload = BytesIO()
    Image.new("RGB", size, color).save(payload, format=format)
    payload.seek(0)
    return payload


def test_upload_rejects_mismatched_image_mimetype(client, login, seeded_data, app):
    login(seeded_data["editor_a"].email)

    response = client.post(
        f"/subir_foto/{seeded_data['seccion_a'].id}",
        data={"fotos": (BytesIO(b"fake image content"), "evidencia.jpg", "text/plain")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "formato de imagen valido" in body
    assert "No se pudo subir ningun archivo valido." in body

    with app.app_context():
        assert Foto.query.filter_by(seccion_id=seeded_data["seccion_a"].id).count() == 0


def test_upload_accepts_valid_image_file(client, login, seeded_data, app):
    login(seeded_data["editor_a"].email)

    response = client.post(
        f"/subir_foto/{seeded_data['seccion_a'].id}",
        data={"fotos": (make_image_bytes("PNG"), "evidencia.png", "image/png")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Se subieron 1 archivo(s)." in response.get_data(as_text=True)

    with app.app_context():
        assert Foto.query.filter_by(seccion_id=seeded_data["seccion_a"].id).count() == 1


def test_upload_rejects_hidden_extension_only_filename(client, login, seeded_data, app):
    login(seeded_data["editor_a"].email)

    response = client.post(
        f"/subir_foto/{seeded_data['seccion_a'].id}",
        data={"fotos": (BytesIO(b"fake image content"), ".jpg", "image/jpeg")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Archivo no permitido" in body
    assert "No se pudo subir ningun archivo valido." in body

    with app.app_context():
        assert Foto.query.filter_by(seccion_id=seeded_data["seccion_a"].id).count() == 0


def test_uploaded_media_is_served_from_media_route(client, login, seeded_data, app):
    login(seeded_data["editor_a"].email)

    client.post(
        f"/subir_foto/{seeded_data['seccion_a'].id}",
        data={"fotos": (make_image_bytes("PNG"), "evidencia.png", "image/png")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    with app.app_context():
        foto = Foto.query.filter_by(seccion_id=seeded_data["seccion_a"].id).first()
        assert foto is not None
        response = client.get(f"/media/uploads/{foto.id}")

    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        f"/test-bucket/{get_upload_object_key(foto.archivo)}?expires=300"
    )


def test_upload_optimizes_png_to_jpeg_in_s3(client, login, seeded_data, app):
    login(seeded_data["editor_a"].email)

    response = client.post(
        f"/subir_foto/{seeded_data['seccion_a'].id}",
        data={
            "fotos": (
                make_image_bytes("PNG", size=(2200, 1800)),
                "foto-celular.png",
                "image/png",
            )
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Se subieron 1 archivo(s)." in response.get_data(as_text=True)

    with app.app_context():
        foto = Foto.query.filter_by(seccion_id=seeded_data["seccion_a"].id).one()
        assert foto.archivo.endswith(".jpg")
        stored = app.extensions["s3_client"].objects[
            (app.config["S3_BUCKET_NAME"], get_upload_object_key(foto.archivo))
        ]
        assert stored["ContentType"] == "image/jpeg"
        with Image.open(BytesIO(stored["Body"])) as optimized:
            assert optimized.format == "JPEG"
            assert optimized.width <= 1600
            assert optimized.height <= 1200


def test_upload_keeps_video_extension_without_optimization(client, login, seeded_data, app):
    login(seeded_data["editor_a"].email)

    response = client.post(
        f"/subir_foto/{seeded_data['seccion_a'].id}",
        data={"fotos": (BytesIO(b"video bytes"), "recorrido.mp4", "video/mp4")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Se subieron 1 archivo(s)." in response.get_data(as_text=True)

    with app.app_context():
        foto = Foto.query.filter_by(seccion_id=seeded_data["seccion_a"].id).one()
        assert foto.archivo.endswith(".mp4")
        stored = app.extensions["s3_client"].objects[
            (app.config["S3_BUCKET_NAME"], get_upload_object_key(foto.archivo))
        ]
        assert stored["ContentType"] == "video/mp4"


def test_upload_rejects_corrupt_image_payload(client, login, seeded_data, app):
    login(seeded_data["editor_a"].email)

    response = client.post(
        f"/subir_foto/{seeded_data['seccion_a'].id}",
        data={"fotos": (BytesIO(b"not an image"), "foto.jpg", "image/jpeg")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "archivo invalido o corrupto" in body
    assert "No se pudo subir ningun archivo valido." in body

    with app.app_context():
        assert Foto.query.filter_by(seccion_id=seeded_data["seccion_a"].id).count() == 0


def test_uploaded_media_requires_company_access(client, login, seeded_data, app):
    with app.app_context():
        foto = Foto(seccion_id=seeded_data["seccion_a"].id, archivo="privada.png")
        db.session.add(foto)
        db.session.commit()
        foto_id = foto.id

    app.extensions["s3_client"].put_object(
        Bucket=app.config["S3_BUCKET_NAME"],
        Key=get_upload_object_key("privada.png"),
        Body=b"private image",
        ContentType="image/png",
    )
    anonymous_response = client.get(f"/media/uploads/{foto_id}", follow_redirects=False)
    assert anonymous_response.status_code == 302

    login(seeded_data["admin_b"].email)
    forbidden_response = client.get(f"/media/uploads/{foto_id}")
    assert forbidden_response.status_code == 403


def test_public_media_route_requires_matching_token(client, seeded_data, app):
    with app.app_context():
        foto = Foto(seccion_id=seeded_data["seccion_a"].id, archivo="publica.png")
        db.session.add(foto)
        db.session.commit()
        foto_id = foto.id

    app.extensions["s3_client"].put_object(
        Bucket=app.config["S3_BUCKET_NAME"],
        Key=get_upload_object_key("publica.png"),
        Body=b"public image",
        ContentType="image/png",
    )
    ok_response = client.get(
        f"/publico/{seeded_data['inventario_a'].token}/media/{foto_id}"
    )
    assert ok_response.status_code == 302
    assert ok_response.headers["Location"].endswith(
        f"/test-bucket/{get_upload_object_key('publica.png')}?expires=300"
    )

    bad_response = client.get(
        f"/publico/{seeded_data['inventario_b'].token}/media/{foto_id}"
    )
    assert bad_response.status_code == 404


def test_generated_pdf_route_requires_login(client, login, seeded_data, app):
    filename = f"inventario_{seeded_data['inventario_a'].id}.pdf"
    app.extensions["s3_client"].put_object(
        Bucket=app.config["S3_BUCKET_NAME"],
        Key=get_pdf_object_key(filename),
        Body=b"%PDF-1.4\nmock pdf",
        ContentType="application/pdf",
    )
    seeded_data["inventario_a"].pdf_status = "ready"
    seeded_data["inventario_a"].pdf_filename = filename
    db.session.commit()

    anonymous_response = client.get(
        f"/media/pdfs/{seeded_data['inventario_a'].id}", follow_redirects=False
    )
    assert anonymous_response.status_code == 302
    assert (
        f"/login?next=%2Fmedia%2Fpdfs%2F{seeded_data['inventario_a'].id}"
        in anonymous_response.headers["Location"]
    )

    login(seeded_data["admin_a"].email)
    authenticated_response = client.get(f"/media/pdfs/{seeded_data['inventario_a'].id}")

    assert authenticated_response.status_code == 302
    assert authenticated_response.headers["Location"].endswith(
        f"/test-bucket/{get_pdf_object_key(filename)}?expires=300"
    )


def test_generated_pdf_route_rejects_stale_pdf(client, login, seeded_data, app):
    filename = f"inventario_{seeded_data['inventario_a'].id}.pdf"
    app.extensions["s3_client"].put_object(
        Bucket=app.config["S3_BUCKET_NAME"],
        Key=get_pdf_object_key(filename),
        Body=b"%PDF-1.4\nstale pdf",
        ContentType="application/pdf",
    )
    seeded_data["inventario_a"].pdf_status = "not_started"
    seeded_data["inventario_a"].pdf_filename = None
    db.session.commit()

    login(seeded_data["admin_a"].email)
    response = client.get(f"/media/pdfs/{seeded_data['inventario_a'].id}")

    assert response.status_code == 404


def test_generated_pdf_route_blocks_other_company(client, login, seeded_data, app):
    filename = f"inventario_{seeded_data['inventario_a'].id}.pdf"
    app.extensions["s3_client"].put_object(
        Bucket=app.config["S3_BUCKET_NAME"],
        Key=get_pdf_object_key(filename),
        Body=b"%PDF-1.4\nprivate pdf",
        ContentType="application/pdf",
    )
    seeded_data["inventario_a"].pdf_status = "ready"
    seeded_data["inventario_a"].pdf_filename = filename
    db.session.commit()

    login(seeded_data["admin_b"].email)
    response = client.get(f"/media/pdfs/{seeded_data['inventario_a'].id}")

    assert response.status_code == 403
