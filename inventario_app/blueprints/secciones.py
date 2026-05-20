from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import login_required

from ..models import Foto, Observacion, Seccion
from ..services.access import (
    get_foto_for_current_company_or_404,
    get_inventario_for_current_company_or_404,
    get_seccion_for_current_company_or_404,
    require_edit_permission,
)
from ..services.media_service import get_uploaded_file_url
from ..services.section_service import (
    create_inventory_section,
    create_section_observation,
    complete_direct_video_upload,
    delete_inventory_section,
    delete_section_photo,
    prepare_direct_video_upload,
    rename_section,
    save_section_description,
    upload_section_files,
)
from ..utils.files import is_video_filename


bp = Blueprint("secciones", __name__)


@bp.route("/seccion/<int:id>", endpoint="ver_seccion")
@login_required
def ver_seccion(id):
    seccion = get_seccion_for_current_company_or_404(id)
    fotos = Foto.query.filter_by(seccion_id=id).order_by(Foto.id.desc()).all()
    observaciones = (
        Observacion.query.filter_by(seccion_id=id).order_by(Observacion.id.desc()).all()
    )
    return render_template(
        "seccion.html",
        seccion=seccion,
        fotos=fotos,
        observaciones=observaciones,
        inventario_id=seccion.inventario_id,
        uploaded_file_url=get_uploaded_file_url,
        is_video_file=is_video_filename,
        video_max_upload_bytes=current_app.config.get("VIDEO_MAX_UPLOAD_BYTES"),
    )


@bp.route(
    "/guardar_descripcion/<int:id>", methods=["POST"], endpoint="guardar_descripcion"
)
@login_required
def guardar_descripcion(id):
    require_edit_permission()
    seccion = get_seccion_for_current_company_or_404(id)
    save_section_description(seccion, request.form.get("descripcion", ""))
    flash("Descripcion guardada.", "success")
    return redirect(url_for("secciones.ver_seccion", id=id))


@bp.route("/subir_foto/<int:id>", methods=["POST"], endpoint="subir_foto")
@login_required
def subir_foto(id):
    require_edit_permission()
    seccion = get_seccion_for_current_company_or_404(id)
    result = upload_section_files(seccion, request.files.getlist("fotos"))

    for error in result.errors:
        flash(error, "error")

    if result.saved_count:
        flash(f"Se subieron {result.saved_count} archivo(s).", "success")
    else:
        flash("No se pudo subir ningun archivo valido.", "error")

    return redirect(url_for("secciones.ver_seccion", id=id))


@bp.route("/seccion/<int:id>/videos/presign", methods=["POST"], endpoint="presign_video_upload")
@login_required
def presign_video_upload(id):
    require_edit_permission()
    seccion = get_seccion_for_current_company_or_404(id)
    payload = request.get_json(silent=True) or {}
    result = prepare_direct_video_upload(
        seccion,
        payload.get("filename", ""),
        payload.get("content_type", ""),
        int(payload.get("size_bytes") or 0),
    )
    if not result.is_valid:
        return jsonify({"error": result.error_message}), 400
    return jsonify(result.payload)


@bp.route("/seccion/<int:id>/videos/complete", methods=["POST"], endpoint="complete_video_upload")
@login_required
def complete_video_upload(id):
    require_edit_permission()
    seccion = get_seccion_for_current_company_or_404(id)
    payload = request.get_json(silent=True) or {}
    result = complete_direct_video_upload(
        seccion,
        payload.get("filename", ""),
        payload.get("size_bytes"),
    )
    if not result.is_valid:
        return jsonify({"error": result.error_message}), 400
    return jsonify({"foto_id": result.foto_id})


@bp.route("/eliminar_foto/<int:id>", methods=["POST"], endpoint="eliminar_foto")
@login_required
def eliminar_foto(id):
    require_edit_permission()
    foto = get_foto_for_current_company_or_404(id)
    seccion_id = delete_section_photo(foto)
    flash("Archivo eliminado.", "success")
    return redirect(url_for("secciones.ver_seccion", id=seccion_id))


@bp.route("/crear_observacion/<int:id>", methods=["POST"], endpoint="crear_observacion")
@login_required
def crear_observacion(id):
    require_edit_permission()
    seccion = get_seccion_for_current_company_or_404(id)

    if not create_section_observation(seccion, request.form.get("comentario", "")):
        flash("La observacion no puede estar vacia.", "error")
        return redirect(url_for("secciones.ver_seccion", id=id))

    flash("Observacion guardada.", "success")
    return redirect(url_for("secciones.ver_seccion", id=id))


@bp.route("/crear_seccion/<int:id>", methods=["POST"], endpoint="crear_seccion")
@login_required
def crear_seccion(id):
    require_edit_permission()
    inventario = get_inventario_for_current_company_or_404(id)

    if not create_inventory_section(inventario.id, request.form.get("nombre", "")):
        flash("Debes indicar el nombre de la seccion.", "error")
        return redirect(url_for("inventarios.ver_inventario", id=id))

    flash("Seccion creada correctamente.", "success")
    return redirect(url_for("inventarios.ver_inventario", id=id))


@bp.route("/eliminar_seccion/<int:id>", methods=["POST"], endpoint="eliminar_seccion")
@login_required
def eliminar_seccion(id):
    require_edit_permission()
    seccion = get_seccion_for_current_company_or_404(id)
    inventario_id = delete_inventory_section(seccion)
    flash("Seccion eliminada.", "success")
    return redirect(url_for("inventarios.ver_inventario", id=inventario_id))


@bp.route(
    "/editar_seccion/<int:id>", methods=["GET", "POST"], endpoint="editar_seccion"
)
@login_required
def editar_seccion(id):
    seccion = get_seccion_for_current_company_or_404(id)

    if request.method == "POST":
        require_edit_permission()
        if not rename_section(seccion, request.form.get("nombre", "")):
            flash("El nombre no puede estar vacio.", "error")
            return redirect(url_for("secciones.editar_seccion", id=id))

        flash("Seccion actualizada.", "success")
        return redirect(url_for("inventarios.ver_inventario", id=seccion.inventario_id))

    return render_template("editar_seccion.html", seccion=seccion)
