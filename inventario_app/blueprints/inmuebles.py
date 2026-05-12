from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from ..extensions import db
from ..models import Inventario
from ..services.access import (
    get_inmueble_for_current_company_or_404,
    require_edit_permission,
)
from ..services.pdf_queue_service import mark_inventory_pdf_dirty


bp = Blueprint("inmuebles", __name__)


@bp.route("/inmueble/<int:id>", endpoint="ver_inmueble")
@login_required
def ver_inmueble(id):
    inmueble = get_inmueble_for_current_company_or_404(id)
    inventarios = (
        Inventario.query.filter_by(inmueble_id=id).order_by(Inventario.id.desc()).all()
    )
    return render_template("inmueble.html", inmueble=inmueble, inventarios=inventarios)


@bp.route(
    "/editar_direccion_inmueble/<int:id>",
    methods=["POST"],
    endpoint="editar_direccion_inmueble",
)
@login_required
def editar_direccion_inmueble(id):
    require_edit_permission()
    inmueble = get_inmueble_for_current_company_or_404(id)
    direccion = request.form.get("direccion", "").strip()

    if not direccion:
        flash("La direccion no puede estar vacia.", "error")
        return redirect(url_for("inmuebles.ver_inmueble", id=id))

    inmueble.direccion = direccion
    for inventario in inmueble.inventarios:
        mark_inventory_pdf_dirty(inventario)
    db.session.commit()
    flash("Direccion actualizada.", "success")
    return redirect(url_for("inmuebles.ver_inmueble", id=id))


@bp.route(
    "/editar_propietario_inmueble/<int:id>",
    methods=["POST"],
    endpoint="editar_propietario_inmueble",
)
@login_required
def editar_propietario_inmueble(id):
    require_edit_permission()
    inmueble = get_inmueble_for_current_company_or_404(id)
    propietario = request.form.get("propietario", "").strip()

    if not propietario:
        flash("El propietario no puede estar vacio.", "error")
        return redirect(url_for("inmuebles.ver_inmueble", id=id))

    inmueble.propietario = propietario
    for inventario in inmueble.inventarios:
        mark_inventory_pdf_dirty(inventario)
    db.session.commit()
    flash("Propietario actualizado.", "success")
    return redirect(url_for("inmuebles.ver_inmueble", id=id))
