from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import login_required

from ..constants import (
    STATUS_ACTIVE,
)
from ..extensions import db
from ..models import Empresa
from ..services.access import require_superadmin_permission
from ..services.superadmin_service import (
    create_company_with_primary_admin,
    list_managed_companies,
    reset_company_admin_password,
    update_company_status,
)


bp = Blueprint("superadmin", __name__)


@bp.route(
    "/superadmin/empresas", methods=["GET", "POST"], endpoint="superadmin_empresas"
)
@login_required
def superadmin_empresas():
    require_superadmin_permission()

    if request.method == "POST":
        result = create_company_with_primary_admin(
            request.form.get("empresa", ""),
            request.form.get("nombre", ""),
            request.form.get("email", ""),
            request.form.get("password", ""),
            request.form.get("estado", STATUS_ACTIVE),
        )
        if not result.is_valid:
            flash(result.error_message, "error")
            return redirect(url_for("superadmin.superadmin_empresas"))

        flash("Empresa creada correctamente con su admin principal.", "success")
        return redirect(url_for("superadmin.superadmin_empresas"))

    empresas = list_managed_companies()
    return render_template("superadmin_empresas.html", empresas=empresas)


@bp.route(
    "/superadmin/empresas/<int:id>/estado",
    methods=["POST"],
    endpoint="superadmin_actualizar_estado_empresa",
)
@login_required
def superadmin_actualizar_estado_empresa(id):
    require_superadmin_permission()
    empresa = db.session.get(Empresa, id)
    if not empresa:
        abort(404)

    result = update_company_status(empresa, request.form.get("estado", ""))
    if not result.is_valid:
        flash(result.error_message, "error")
        return redirect(url_for("superadmin.superadmin_empresas"))

    if (
        empresa.estado != STATUS_ACTIVE
        and session.get("superadmin_company_id") == empresa.id
    ):
        session.pop("superadmin_company_id", None)

    flash("Estado de la empresa actualizado correctamente.", "success")
    return redirect(url_for("superadmin.superadmin_empresas"))


@bp.route(
    "/superadmin/empresas/<int:id>/admin-password",
    methods=["POST"],
    endpoint="superadmin_actualizar_password_admin",
)
@login_required
def superadmin_actualizar_password_admin(id):
    require_superadmin_permission()
    empresa = db.session.get(Empresa, id)
    if not empresa:
        abort(404)

    result = reset_company_admin_password(empresa, request.form.get("password", ""))
    if not result.is_valid:
        flash(result.error_message, "error")
        return redirect(url_for("superadmin.superadmin_empresas"))

    flash("Contrasena del admin restablecida correctamente.", "success")
    return redirect(url_for("superadmin.superadmin_empresas"))


@bp.route(
    "/superadmin/empresas/<int:id>/entrar",
    methods=["POST"],
    endpoint="superadmin_entrar_empresa",
)
@login_required
def superadmin_entrar_empresa(id):
    require_superadmin_permission()
    empresa = db.session.get(Empresa, id)
    if not empresa:
        abort(404)

    session["superadmin_company_id"] = empresa.id
    flash(f"Modo superadmin activo sobre {empresa.nombre}.", "success")
    return redirect(url_for("dashboard.index"))


@bp.route(
    "/superadmin/salir-empresa",
    methods=["POST"],
    endpoint="superadmin_salir_empresa",
)
@login_required
def superadmin_salir_empresa():
    require_superadmin_permission()
    session.pop("superadmin_company_id", None)
    flash("Saliste del modo empresa.", "success")
    return redirect(url_for("superadmin.superadmin_empresas"))
