from flask import current_app, has_app_context

from inventario_app import create_app
from inventario_app.extensions import db
from inventario_app.models import Foto
from inventario_app.services.video_processing_service import process_video_file
from inventario_app.services.video_queue_service import (
    set_video_failed,
    set_video_processed,
    set_video_processing,
)


def process_video_job(foto_id: int, raise_on_error: bool = True) -> None:
    app = (
        current_app._get_current_object()
        if has_app_context()
        else create_app({"SKIP_DATA_SEED": True})
    )

    def run() -> None:
        foto = db.session.get(Foto, foto_id)
        if not foto:
            return

        set_video_processing(foto)
        try:
            filename, duration = process_video_file(foto)
        except Exception as error:
            app.logger.exception("video_processing_failed foto_id=%s", foto_id)
            set_video_failed(foto, "No se pudo procesar el video en este momento.")
            if raise_on_error:
                raise error
            return

        set_video_processed(foto, filename, duration)
        app.logger.info("video_processed foto_id=%s archivo=%s", foto.id, filename)

    if has_app_context():
        run()
        return

    with app.app_context():
        run()
