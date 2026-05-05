from flask import Blueprint, abort, redirect, send_from_directory
from flask_login import login_required

from ..extensions import db
from ..constants import PDF_STATUS_READY
from ..models import Foto
from ..services.access import (
    get_foto_for_current_company_or_404,
    get_inventario_for_current_company_or_404,
)
from ..services.media_service import (
    get_pdf_dir,
    get_pdf_file_download_url,
    get_upload_dir,
    get_uploaded_file_download_url,
    pdf_file_exists,
    storage_backend_is_s3,
    uploaded_file_exists,
)


bp = Blueprint("media", __name__)


@bp.route("/media/uploads/<int:foto_id>", endpoint="uploaded_file")
@login_required
def uploaded_file(foto_id):
    foto = get_foto_for_current_company_or_404(foto_id)
    if not uploaded_file_exists(foto.archivo):
        return ("", 404)
    if storage_backend_is_s3():
        return redirect(get_uploaded_file_download_url(foto.archivo))
    return send_from_directory(get_upload_dir(), foto.archivo)


@bp.route(
    "/publico/<string:token>/media/<int:foto_id>", endpoint="public_uploaded_file"
)
def public_uploaded_file(token, foto_id):
    foto = db.session.get(Foto, foto_id)
    if not foto:
        abort(404)
    if foto.seccion.inventario.token != token:
        abort(404)

    if not uploaded_file_exists(foto.archivo):
        abort(404)
    if storage_backend_is_s3():
        return redirect(get_uploaded_file_download_url(foto.archivo))
    return send_from_directory(get_upload_dir(), foto.archivo)


@bp.route("/media/pdfs/<int:inventario_id>", endpoint="generated_pdf")
@login_required
def generated_pdf(inventario_id):
    inventario = get_inventario_for_current_company_or_404(inventario_id)
    filename = inventario.pdf_filename
    if inventario.pdf_status != PDF_STATUS_READY or not filename:
        return ("", 404)
    if not pdf_file_exists(filename):
        return ("", 404)
    if storage_backend_is_s3():
        return redirect(get_pdf_file_download_url(filename))
    return send_from_directory(get_pdf_dir(), filename)
