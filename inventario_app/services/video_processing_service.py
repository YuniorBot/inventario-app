from pathlib import Path
import json
import subprocess
from tempfile import TemporaryDirectory

from flask import current_app

from ..models import Foto
from ..utils.files import unique_filename
from .media_service import (
    build_relative_upload_key,
    get_uploaded_file_bytes,
    upload_uploaded_bytes,
)


class VideoProcessingError(Exception):
    pass


def process_video_file(foto: Foto) -> tuple[str, int | None]:
    source_filename = foto.archivo_original or foto.archivo
    payload = get_uploaded_file_bytes(source_filename)
    if payload is None:
        raise VideoProcessingError("No se encontro el video original en el almacenamiento.")

    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        input_path = tmp_path / "input_video"
        output_path = tmp_path / "output.mp4"
        input_path.write_bytes(payload)

        _run_ffmpeg(input_path, output_path)
        output_filename = build_relative_upload_key(
            current_app.config.get("VIDEO_PROCESSED_PREFIX", "videos/processed"),
            unique_filename("processed.mp4"),
        )
        upload_uploaded_bytes(output_filename, output_path.read_bytes(), "video/mp4")
        duration = _probe_duration(output_path)
        return output_filename, duration


def _run_ffmpeg(input_path: Path, output_path: Path) -> None:
    max_width = current_app.config.get("VIDEO_OUTPUT_MAX_WIDTH", 1280)
    max_height = current_app.config.get("VIDEO_OUTPUT_MAX_HEIGHT", 720)
    scale_filter = f"scale={max_width}:{max_height}:force_original_aspect_ratio=decrease"
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vf",
        scale_filter,
        "-c:v",
        "libx264",
        "-preset",
        current_app.config.get("VIDEO_OUTPUT_PRESET", "veryfast"),
        "-crf",
        str(current_app.config.get("VIDEO_OUTPUT_CRF", 28)),
        "-c:a",
        "aac",
        "-b:a",
        current_app.config.get("VIDEO_OUTPUT_AUDIO_BITRATE", "96k"),
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=current_app.config.get("VIDEO_PROCESSING_TIMEOUT_SECONDS", 1800))
    except FileNotFoundError as error:
        raise VideoProcessingError("ffmpeg no esta instalado en el servidor.") from error
    except subprocess.TimeoutExpired as error:
        raise VideoProcessingError("El procesamiento del video excedio el tiempo permitido.") from error
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or "").strip()[-500:]
        raise VideoProcessingError(f"ffmpeg no pudo procesar el video. {detail}") from error


def _probe_duration(path: Path) -> int | None:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
    except Exception:
        return None
    try:
        duration = float(json.loads(result.stdout)["format"]["duration"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return int(round(duration))
