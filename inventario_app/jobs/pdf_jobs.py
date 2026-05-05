from flask import current_app, has_app_context

from inventario_app import create_app
from inventario_app.extensions import db
from inventario_app.models import Inventario
from inventario_app.services.inventory_service import get_inventory_signatures, get_pdf_sections
from inventario_app.services.pdf_queue_service import (
    set_pdf_failed,
    set_pdf_processing,
    set_pdf_ready,
)
from inventario_app.services.pdf_service import build_inventory_pdf


def generate_inventory_pdf_job(
    inventario_id: int, pdf_version: int, raise_on_error: bool = True
) -> None:
    app = (
        current_app._get_current_object()
        if has_app_context()
        else create_app({"SKIP_DATA_SEED": True})
    )

    def run() -> None:
        inventario = db.session.get(Inventario, inventario_id)
        if not inventario or inventario.pdf_version != pdf_version:
            return

        set_pdf_processing(inventario)
        try:
            secciones = get_pdf_sections(inventario.id)
            firmas = get_inventory_signatures(inventario.id)
            filename = build_inventory_pdf(inventario, secciones, firmas)
        except Exception as error:
            app.logger.exception("pdf_generation_failed inventario_id=%s", inventario_id)
            set_pdf_failed(inventario, "No se pudo generar el PDF en este momento.")
            if raise_on_error:
                raise error
            return

        set_pdf_ready(inventario, filename)
        app.logger.info(
            "pdf_generated inventario_id=%s archivo=%s", inventario.id, filename
        )

    if has_app_context():
        run()
        return

    with app.app_context():
        run()
