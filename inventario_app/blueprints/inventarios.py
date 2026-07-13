from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from ..constants import PDF_STATUS_FAILED, PDF_STATUS_READY
from ..models import Inventario
from ..services.access import (
    get_inmueble_for_current_company_or_404,
    get_inventario_for_current_company_or_404,
    require_edit_permission,
)
from ..services.media_service import get_pdf_file_url
from ..services.inventory_service import (
    create_inventory,
    duplicate_inventory_structure,
    list_inventory_sections,
    rename_inventory,
    save_inventory_signature,
)
from ..services.pdf_queue_service import enqueue_inventory_pdf, get_pdf_status_payload


bp = Blueprint("inventarios", __name__)


@bp.route("/crear_inventario/<int:id>", methods=["POST"], endpoint="crear_inventario")
@login_required
def crear_inventario(id):
    require_edit_permission()
    inmueble = get_inmueble_for_current_company_or_404(id)
    result = create_inventory(
        inmueble.id,
        request.form.get("nombre", ""),
        request.form.get("fecha", ""),
        current_user.id,
    )

    if not result.is_valid:
        flash("Debes indicar nombre y fecha del inventario.", "error")
        return redirect(url_for("inmuebles.ver_inmueble", id=id))

    flash("Inventario creado correctamente.", "success")
    return redirect(url_for("inmuebles.ver_inmueble", id=id))


@bp.route(
    "/editar_nombre_inventario/<int:id>",
    methods=["POST"],
    endpoint="editar_nombre_inventario",
)
@login_required
def editar_nombre_inventario(id):
    require_edit_permission()
    inventario = get_inventario_for_current_company_or_404(id)
    inmueble_id = inventario.inmueble_id

    if not rename_inventory(inventario, request.form.get("nombre", "")):
        flash("El nombre del inventario no puede estar vacio.", "error")
        return redirect(
            url_for("inmuebles.ver_inmueble", id=inmueble_id)
            + "#inventarios-registrados"
        )

    flash("Nombre del inventario actualizado.", "success")
    return redirect(
        url_for("inmuebles.ver_inmueble", id=inmueble_id) + "#inventarios-registrados"
    )


@bp.route(
    "/duplicar_inventario/<int:id>", methods=["POST"], endpoint="duplicar_inventario"
)
@login_required
def duplicar_inventario(id):
    require_edit_permission()
    inventario = get_inventario_for_current_company_or_404(id)
    nuevo = duplicate_inventory_structure(inventario, current_user.id)

    flash("Inventario duplicado correctamente.", "success")
    return redirect(url_for("inventarios.ver_inventario", id=nuevo.id))


@bp.route("/inventario/<int:id>", endpoint="ver_inventario")
@login_required
def ver_inventario(id):
    inventario = get_inventario_for_current_company_or_404(id)
    secciones = list_inventory_sections(id)
    return render_template(
        "inventario.html", inventario=inventario, secciones=secciones
    )


@bp.route("/guardar_firma/<int:id>", methods=["POST"], endpoint="guardar_firma")
@login_required
def guardar_firma(id):
    require_edit_permission()
    inventario = get_inventario_for_current_company_or_404(id)
    result = save_inventory_signature(
        inventario.id,
        request.form.get("nombre", ""),
        request.form.get("cedula", ""),
        request.form.get("celular", ""),
        request.form.get("correo", ""),
        request.form.get("firma", ""),
    )

    if not result.is_valid:
        flash(result.error_message, "error")
        return redirect(url_for("inventarios.ver_inventario", id=id))

    flash("Firma guardada.", "success")
    return redirect(url_for("inventarios.ver_inventario", id=id))


@bp.route("/inventario_pdf/<int:id>", endpoint="inventario_pdf")
@login_required
def inventario_pdf(id):
    inventario = get_inventario_for_current_company_or_404(id)
    inventario = enqueue_inventory_pdf(inventario)
    if inventario.pdf_status == PDF_STATUS_FAILED:
        flash("No se pudo generar el PDF en este momento.", "error")
        return redirect(url_for("inventarios.ver_inventario", id=id))

    if inventario.pdf_status == PDF_STATUS_READY:
        return redirect(get_pdf_file_url(inventario.id))

    flash(
        "Estamos generando el PDF. La descarga estara disponible en unos momentos.",
        "success",
    )
    return redirect(url_for("inventarios.ver_inventario", id=id))


@bp.route("/inventario_pdf_estado/<int:id>", endpoint="inventario_pdf_estado")
@login_required
def inventario_pdf_estado(id):
    inventario = get_inventario_for_current_company_or_404(id)
    return jsonify(get_pdf_status_payload(inventario))
