from urllib.parse import urlsplit

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash

from ..constants import ROLE_SUPERADMIN, STATUS_ACTIVE, VALID_ROLES
from ..models import Usuario
from ..services.access import user_is_superadmin
from ..services.password_reset_service import (
    get_valid_password_reset_token,
    request_password_reset,
    reset_password_with_token,
)


bp = Blueprint("auth", __name__)


def _is_safe_redirect_target(target: str | None) -> bool:
    if not target:
        return False
    ref_url = urlsplit(request.host_url)
    test_url = urlsplit(target)
    return (
        test_url.scheme in {"", "http", "https"}
        and test_url.netloc in {"", ref_url.netloc}
        and target.startswith("/")
    )


def _redirect_authenticated_user():
    if user_is_superadmin(current_user):
        return redirect(url_for("superadmin.superadmin_empresas"))
    return redirect(url_for("dashboard.index"))


@bp.route("/registro", methods=["GET", "POST"], endpoint="registro")
def registro():
    flash(
        "El registro publico esta deshabilitado. Contacta al administrador de la plataforma.",
        "error",
    )
    return redirect(url_for("auth.login"))


@bp.route("/login", methods=["GET", "POST"], endpoint="login")
def login():
    if current_user.is_authenticated:
        return _redirect_authenticated_user()

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and check_password_hash(usuario.password, password):
            if not usuario.activo:
                flash(
                    "Esta cuenta esta desactivada. Contacta al administrador de tu empresa.",
                    "error",
                )
                return redirect(url_for("auth.login"))

            if usuario.rol == ROLE_SUPERADMIN:
                session.pop("superadmin_company_id", None)
                login_user(usuario)
                current_app.logger.info("superadmin_login email=%s", usuario.email)
                flash("Bienvenido.", "success")
                return redirect(url_for("superadmin.superadmin_empresas"))

            if not usuario.empresa or not usuario.empresa.activo:
                flash("La empresa asociada a esta cuenta no esta activa.", "error")
                return redirect(url_for("auth.login"))

            if usuario.empresa.estado != STATUS_ACTIVE:
                flash("La empresa no tiene acceso habilitado en este momento.", "error")
                return redirect(url_for("auth.login"))

            if usuario.rol not in VALID_ROLES:
                flash("La cuenta no tiene un rol valido configurado.", "error")
                return redirect(url_for("auth.login"))

            login_user(usuario)
            current_app.logger.info(
                "user_login email=%s empresa_id=%s rol=%s",
                usuario.email,
                usuario.empresa_id,
                usuario.rol,
            )
            flash("Bienvenido.", "success")
            next_url = request.args.get("next")
            safe_next_url = (
                next_url if next_url and _is_safe_redirect_target(next_url) else None
            )
            if safe_next_url is not None:
                return redirect(safe_next_url)
            return redirect(url_for("dashboard.index"))

        current_app.logger.warning("failed_login email=%s", email)
        flash("Credenciales invalidas.", "error")

    return render_template("login.html")


@bp.route("/olvide-password", methods=["GET", "POST"], endpoint="forgot_password")
def forgot_password():
    if current_user.is_authenticated:
        return _redirect_authenticated_user()

    if request.method == "POST":
        email = request.form.get("email", "")
        try:
            request_password_reset(email)
        except Exception:
            current_app.logger.exception(
                "password_reset_request_failed email=%s", email.strip().lower()
            )

        flash(
            "Si el correo existe y esta habilitado, te enviaremos instrucciones para restablecer la contrasena.",
            "info",
        )
        return redirect(url_for("auth.login"))

    return render_template("forgot_password.html")


@bp.route(
    "/restablecer-password/<string:token>",
    methods=["GET", "POST"],
    endpoint="reset_password",
)
def reset_password(token):
    if current_user.is_authenticated:
        return _redirect_authenticated_user()

    token_record = get_valid_password_reset_token(token)
    if token_record is None:
        flash("El enlace de restablecimiento no es valido o ya expiro.", "error")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")

        if password != password_confirm:
            flash("Las contrasenas no coinciden.", "error")
            return render_template("reset_password.html", token=token)

        success, message = reset_password_with_token(token, password)
        flash(message, "success" if success else "error")
        if success:
            current_app.logger.info(
                "password_reset_completed user_id=%s", token_record.usuario_id
            )
            return redirect(url_for("auth.login"))

    return render_template("reset_password.html", token=token)


@bp.route("/logout", methods=["POST"], endpoint="logout")
@login_required
def logout():
    current_app.logger.info("user_logout user_id=%s", current_user.get_id())
    session.pop("superadmin_company_id", None)
    logout_user()
    flash("Sesion cerrada.", "success")
    return redirect(url_for("auth.login"))
