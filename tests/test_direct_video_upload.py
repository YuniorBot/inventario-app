from io import BytesIO

from inventario_app.constants import (
    MEDIA_TYPE_VIDEO,
    VIDEO_STATUS_PENDING_PROCESSING,
    VIDEO_STATUS_PROCESSED,
    VIDEO_STATUS_PROCESSING,
    VIDEO_STATUS_READY,
)
from inventario_app.extensions import db
from inventario_app.jobs.video_jobs import process_video_job
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


def test_video_complete_creates_ready_record(client, login, seeded_data, app):
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
        assert foto.processing_status == VIDEO_STATUS_READY
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


def test_processing_video_original_is_served(client, login, seeded_data, app):
    filename = "videos/originals/procesando.mp4"
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
            archivo_original=filename,
            tipo=MEDIA_TYPE_VIDEO,
            processing_status=VIDEO_STATUS_PROCESSING,
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


def test_video_processing_success_uses_processed_file_and_deletes_original(
    client, login, seeded_data, app, monkeypatch
):
    login(seeded_data["editor_a"].email)
    original = "videos/originals/recorrido.mp4"
    processed = "videos/processed/recorrido.mp4"
    app.extensions["s3_client"].put_object(
        Bucket=app.config["S3_BUCKET_NAME"],
        Key=get_upload_object_key(original),
        Body=b"original video bytes",
        ContentType="video/mp4",
    )
    response = client.post(
        f"/seccion/{seeded_data['seccion_a'].id}/videos/complete",
        json={"filename": original, "size_bytes": len(b"original video bytes")},
    )
    foto_id = response.get_json()["foto_id"]

    def fake_process_video_file(_foto):
        app.extensions["s3_client"].put_object(
            Bucket=app.config["S3_BUCKET_NAME"],
            Key=get_upload_object_key(processed),
            Body=b"processed video bytes",
            ContentType="video/mp4",
        )
        return processed, 12

    monkeypatch.setattr(
        "inventario_app.jobs.video_jobs.process_video_file", fake_process_video_file
    )

    with app.app_context():
        process_video_job(foto_id)
        foto = db.session.get(Foto, foto_id)
        assert foto.archivo == processed
        assert foto.archivo_original is None
        assert foto.processing_status == VIDEO_STATUS_PROCESSED
        assert foto.duration_seconds == 12

    assert (
        app.config["S3_BUCKET_NAME"],
        get_upload_object_key(original),
    ) not in app.extensions["s3_client"].objects
    assert (
        app.config["S3_BUCKET_NAME"],
        get_upload_object_key(processed),
    ) in app.extensions["s3_client"].objects


def test_video_processing_failure_keeps_original_visible(
    client, login, seeded_data, app, monkeypatch
):
    login(seeded_data["editor_a"].email)
    original = "videos/originals/falla.mp4"
    app.extensions["s3_client"].put_object(
        Bucket=app.config["S3_BUCKET_NAME"],
        Key=get_upload_object_key(original),
        Body=b"original video bytes",
        ContentType="video/mp4",
    )
    response = client.post(
        f"/seccion/{seeded_data['seccion_a'].id}/videos/complete",
        json={"filename": original, "size_bytes": len(b"original video bytes")},
    )
    foto_id = response.get_json()["foto_id"]

    def fake_process_video_file(_foto):
        raise RuntimeError("ffmpeg failed")

    monkeypatch.setattr(
        "inventario_app.jobs.video_jobs.process_video_file", fake_process_video_file
    )

    with app.app_context():
        process_video_job(foto_id, raise_on_error=False)
        foto = db.session.get(Foto, foto_id)
        assert foto.archivo == original
        assert foto.archivo_original == original
        assert foto.processing_status == VIDEO_STATUS_READY
        assert "original" in foto.processing_error

    response = client.get(f"/media/uploads/{foto_id}")

    assert response.status_code == 302
    assert (
        app.config["S3_BUCKET_NAME"],
        get_upload_object_key(original),
    ) in app.extensions["s3_client"].objects
