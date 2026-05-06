from io import BytesIO
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from flask import current_app, url_for
from PIL import Image as PILImage, ImageOps, UnidentifiedImageError

from ..config import PDF_DIR, UPLOAD_DIR
from ..utils.files import unique_filename


OPTIMIZABLE_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


class MediaProcessingError(Exception):
    pass


def storage_backend_is_s3() -> bool:
    return current_app.config.get("STORAGE_BACKEND", "local") == "s3"


def validate_storage_config(app) -> None:
    if app.config.get("STORAGE_BACKEND", "local") != "s3":
        return

    if not app.config.get("S3_BUCKET_NAME"):
        raise RuntimeError(
            "Configura S3_BUCKET_NAME antes de iniciar la app con STORAGE_BACKEND=s3."
        )


def get_s3_client():
    client = current_app.extensions.get("s3_client")
    if client is None:
        region_name = current_app.config.get("AWS_REGION") or None
        client = boto3.client("s3", region_name=region_name)
        current_app.extensions["s3_client"] = client
    return client


def get_s3_bucket_name() -> str:
    bucket = current_app.config.get("S3_BUCKET_NAME")
    if not bucket:
        raise RuntimeError("S3_BUCKET_NAME no esta configurado.")
    return bucket


def _normalize_prefix(prefix: str | None) -> str:
    return (prefix or "").strip("/")


def _build_object_key(prefix: str | None, filename: str) -> str:
    normalized_prefix = _normalize_prefix(prefix)
    return f"{normalized_prefix}/{filename}" if normalized_prefix else filename


def get_upload_dir() -> Path:
    return Path(current_app.config.get("UPLOAD_FOLDER", UPLOAD_DIR))


def get_pdf_dir() -> Path:
    return Path(current_app.config.get("PDF_FOLDER", PDF_DIR))


def get_upload_object_key(filename: str) -> str:
    return _build_object_key(current_app.config.get("S3_UPLOAD_PREFIX"), filename)


def get_pdf_object_key(filename: str) -> str:
    return _build_object_key(current_app.config.get("S3_PDF_PREFIX"), filename)


def ensure_storage_dirs() -> None:
    if storage_backend_is_s3():
        return
    get_upload_dir().mkdir(parents=True, exist_ok=True)
    get_pdf_dir().mkdir(parents=True, exist_ok=True)


def save_uploaded_file(storage) -> str:
    optimized_payload = _optimize_uploaded_image(storage)
    if optimized_payload is not None:
        filename = unique_filename("optimized.jpg")
        payload = optimized_payload.getvalue()
        if storage_backend_is_s3():
            get_s3_client().upload_fileobj(
                BytesIO(payload),
                get_s3_bucket_name(),
                get_upload_object_key(filename),
                ExtraArgs={"ContentType": "image/jpeg"},
            )
            return filename

        get_uploaded_file_path(filename).write_bytes(payload)
        return filename

    filename = unique_filename(storage.filename)
    if storage_backend_is_s3():
        storage.stream.seek(0)
        get_s3_client().upload_fileobj(
            storage.stream,
            get_s3_bucket_name(),
            get_upload_object_key(filename),
            ExtraArgs={"ContentType": storage.mimetype or "application/octet-stream"},
        )
        return filename

    storage.save(get_upload_dir() / filename)
    return filename


def _optimize_uploaded_image(storage) -> BytesIO | None:
    ext = Path(storage.filename or "").suffix.lower().lstrip(".")
    if ext not in OPTIMIZABLE_IMAGE_EXTENSIONS:
        return None

    try:
        storage.stream.seek(0)
        with PILImage.open(storage.stream) as source:
            image = ImageOps.exif_transpose(source)
            image.thumbnail(
                (
                    current_app.config.get("UPLOAD_IMAGE_MAX_WIDTH", 1600),
                    current_app.config.get("UPLOAD_IMAGE_MAX_HEIGHT", 1200),
                )
            )
            if image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")

            output = BytesIO()
            image.save(
                output,
                format="JPEG",
                optimize=True,
                quality=current_app.config.get("UPLOAD_IMAGE_JPEG_QUALITY", 80),
            )
            output.seek(0)
            return output
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise MediaProcessingError(
            "No se pudo procesar la imagen: archivo invalido o corrupto."
        ) from error
    finally:
        storage.stream.seek(0)


def delete_uploaded_file(filename: str) -> None:
    if storage_backend_is_s3():
        get_s3_client().delete_object(
            Bucket=get_s3_bucket_name(), Key=get_upload_object_key(filename)
        )
        return

    path = get_upload_dir() / filename
    if path.exists():
        path.unlink(missing_ok=True)


def get_uploaded_file_path(filename: str) -> Path:
    return get_upload_dir() / filename


def get_pdf_file_path(filename: str) -> Path:
    return get_pdf_dir() / filename


def upload_pdf_bytes(filename: str, payload: bytes) -> None:
    if storage_backend_is_s3():
        get_s3_client().put_object(
            Bucket=get_s3_bucket_name(),
            Key=get_pdf_object_key(filename),
            Body=payload,
            ContentType="application/pdf",
        )
        return

    get_pdf_file_path(filename).write_bytes(payload)


def _object_exists(object_key: str) -> bool:
    try:
        get_s3_client().head_object(Bucket=get_s3_bucket_name(), Key=object_key)
        return True
    except KeyError:
        return False
    except ClientError as error:
        error_code = (error.response or {}).get("Error", {}).get("Code")
        if error_code in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise


def uploaded_file_exists(filename: str) -> bool:
    if storage_backend_is_s3():
        return _object_exists(get_upload_object_key(filename))
    return get_uploaded_file_path(filename).is_file()


def pdf_file_exists(filename: str) -> bool:
    if storage_backend_is_s3():
        return _object_exists(get_pdf_object_key(filename))
    return get_pdf_file_path(filename).is_file()


def _generate_presigned_url(object_key: str) -> str:
    return get_s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": get_s3_bucket_name(), "Key": object_key},
        ExpiresIn=current_app.config.get("S3_SIGNED_URL_EXPIRES", 300),
    )


def get_uploaded_file_download_url(filename: str) -> str:
    return _generate_presigned_url(get_upload_object_key(filename))


def get_pdf_file_download_url(filename: str) -> str:
    return _generate_presigned_url(get_pdf_object_key(filename))


def get_uploaded_file_bytes(filename: str) -> bytes | None:
    if storage_backend_is_s3():
        try:
            response = get_s3_client().get_object(
                Bucket=get_s3_bucket_name(), Key=get_upload_object_key(filename)
            )
        except KeyError:
            return None
        except ClientError as error:
            error_code = (error.response or {}).get("Error", {}).get("Code")
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise
        return response["Body"].read()

    path = get_uploaded_file_path(filename)
    if not path.is_file():
        return None
    return path.read_bytes()


def get_uploaded_file_url(foto_id: int) -> str:
    return url_for("media.uploaded_file", foto_id=foto_id)


def get_public_uploaded_file_url(token: str, foto_id: int) -> str:
    return url_for("media.public_uploaded_file", token=token, foto_id=foto_id)


def get_pdf_file_url(inventario_id: int) -> str:
    return url_for("media.generated_pdf", inventario_id=inventario_id)
