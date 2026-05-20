from io import BytesIO

from inventario_app.constants import (
    MEDIA_TYPE_VIDEO,
    VIDEO_STATUS_PENDING_PROCESSING,
    VIDEO_STATUS_PROCESSED,
)
from inventario_app.extensions import db
from inventario_app.models import Foto
from inventario_app.services.media_service import get_upload_object_key


def test_video_presign_rejects_large_file(client, login, seeded_data):
    login(seeded_data["editor_a"].email)

    response = client.post(
        f"/seccion/{seeded_data['seccion_a'].id}/videos/presign",
        json={
            "filename": "recorrido.mp4",
            "content_type": "video/mp4",
            "size_bytes": 600 * 1024 * 1024,
        },
    )

    assert response.status_code == 400
    assert "maximo permitido" in response.get_json()["error"]


def test_video_presign_requires_edit_permission(client, login, seeded_data):
    login(seeded_data["viewer_a"].email)

    response = client.post(
        f"/seccion/{seeded_data['seccion_a'].id}/videos/presign",
        json={
            "filename": "recorrido.mp4",
            "content_type": "video/mp4",
            "size_bytes": 1024,
        },
    )

    assert response.status_code == 403


def test_video_presign_generates_s3_post(client, login, seeded_data):
    login(seeded_data["editor_a"].email)

    response = client.post(
        f"/seccion/{seeded_data['seccion_a'].id}/videos/presign",
        json={
            "filename": "recorrido.mp4",
            "content_type": "video/mp4",
            "size_bytes": 111 * 1024 * 1024,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["filename"].startswith("videos/originals/")
    assert payload["filename"].endswith(".mp4")
    assert payload["max_size"] == 500 * 1024 * 1024
    assert payload["upload"]["fields"]["key"].startswith("uploads/videos/originals/")
    assert payload["upload"]["fields"]["Content-Type"] == "video/mp4"


def test_video_complete_creates_pending_record(client, login, seeded_data, app):
    login(seeded_data["editor_a"].email)
    filename = "videos/originals/recorrido.mp4"
    app.extensions["s3_client"].put_object(
        Bucket=app.config["S3_BUCKET_NAME"],
        Key=get_upload_object_key(filename),
        Body=b"video bytes",
        ContentType="video/mp4",
    )

    response = client.post(
        f"/seccion/{seeded_data['seccion_a'].id}/videos/complete",
        json={"filename": filename, "size_bytes": len(b"video bytes")},
    )

    assert response.status_code == 200
    foto_id = response.get_json()["foto_id"]
    with app.app_context():
        foto = db.session.get(Foto, foto_id)
        assert foto.tipo == MEDIA_TYPE_VIDEO
        assert foto.archivo == filename
        assert foto.archivo_original == filename
        assert foto.processing_status == VIDEO_STATUS_PENDING_PROCESSING
        assert foto.size_bytes == len(b"video bytes")


def test_pending_video_is_not_served(client, login, seeded_data, app):
    with app.app_context():
        foto = Foto(
            seccion_id=seeded_data["seccion_a"].id,
            archivo="videos/originals/pendiente.mp4",
            tipo=MEDIA_TYPE_VIDEO,
            processing_status=VIDEO_STATUS_PENDING_PROCESSING,
        )
        db.session.add(foto)
        db.session.commit()
        foto_id = foto.id

    login(seeded_data["editor_a"].email)
    response = client.get(f"/media/uploads/{foto_id}")

    assert response.status_code == 404


def test_processed_video_is_served(client, login, seeded_data, app):
    filename = "videos/processed/final.mp4"
    app.extensions["s3_client"].put_object(
        Bucket=app.config["S3_BUCKET_NAME"],
        Key=get_upload_object_key(filename),
        Body=b"video bytes",
        ContentType="video/mp4",
    )
    with app.app_context():
        foto = Foto(
            seccion_id=seeded_data["seccion_a"].id,
            archivo=filename,
            tipo=MEDIA_TYPE_VIDEO,
            processing_status=VIDEO_STATUS_PROCESSED,
        )
        db.session.add(foto)
        db.session.commit()
        foto_id = foto.id

    login(seeded_data["editor_a"].email)
    response = client.get(f"/media/uploads/{foto_id}")

    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        f"/test-bucket/{get_upload_object_key(filename)}?expires=300"
    )
