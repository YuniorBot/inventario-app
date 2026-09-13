import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
import logging

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import current_user
from flask_wtf.csrf import CSRFError

from .blueprints import ALL_BLUEPRINTS
from .cli import register_cli_commands
from .config import BASE_DIR, Config
from .constants import (
    ROLE_ADMIN,
    ROLE_EDITOR,
    ROLE_SUPERADMIN,
    ROLE_VIEWER,
    STATUS_ACTIVE,
    STATUS_CANCELLED,
    STATUS_SUSPENDED,
)
from .extensions import csrf, db, login_manager, migrate
from .models import Usuario
from .services.access import (
    get_effective_company,
    user_can_edit,
    user_is_admin,
    user_is_superadmin,
)
from .services.bootstrap_service import seed_initial_data
from .services.media_service import ensure_storage_dirs, validate_storage_config
from .utils.rich_text import rich_text_markup


def create_app(config_overrides: dict | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
        static_url_path="/static",
    )
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)

    _configure_logging(app)
    validate_storage_config(app)

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Debes iniciar sesion para continuar."
    app.jinja_env.filters["rich_text"] = rich_text_markup

    def versioned_static(filename: str) -> str:
        static_path = Path(app.static_folder) / filename
        try:
            version = static_path.stat().st_mtime_ns
        except OSError:
            return url_for("static", filename=filename)
        return url_for("static", filename=filename, v=version)

    app.jinja_env.globals["versioned_static"] = versioned_static

    if not os.environ.get("SECRET_KEY"):
        app.logger.warning(
            "Usando SECRET_KEY de desarrollo. Configura SECRET_KEY para entornos compartidos o produccion."
        )

    if not os.environ.get("SUPERADMIN_EMAIL") or not os.environ.get(
        "SUPERADMIN_PASSWORD"
    ):
        app.logger.warning(
            "Usando credenciales locales por defecto para superadmin. Configura SUPERADMIN_EMAIL y SUPERADMIN_PASSWORD fuera de desarrollo."
        )

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(Usuario, int(user_id))

    @app.errorhandler(CSRFError)
    def handle_csrf_error(_error):
        flash("La sesion del formulario expiro. Intenta enviar nuevamente.", "error")
        destino = request.referrer or url_for("auth.login")
        return redirect(destino)

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("403.html"), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("404.html"), 404

    @app.context_processor
    def inject_access_context():
        empresa = get_effective_company()
        return {
            "current_company": empresa,
            "can_edit": user_can_edit(current_user),
            "is_superadmin": user_is_superadmin(current_user),
            "is_company_admin": user_is_admin(current_user),
            "ROLE_ADMIN": ROLE_ADMIN,
            "ROLE_EDITOR": ROLE_EDITOR,
            "ROLE_VIEWER": ROLE_VIEWER,
            "ROLE_SUPERADMIN": ROLE_SUPERADMIN,
            "STATUS_ACTIVE": STATUS_ACTIVE,
            "STATUS_SUSPENDED": STATUS_SUSPENDED,
            "STATUS_CANCELLED": STATUS_CANCELLED,
            "superadmin_company_mode": user_is_superadmin(current_user)
            and empresa is not None,
        }

    for blueprint in ALL_BLUEPRINTS:
        app.register_blueprint(blueprint)

    register_cli_commands(app)

    with app.app_context():
        ensure_storage_dirs()
        if not app.config.get("SKIP_DATA_SEED", False) and os.environ.get(
            "SKIP_DATA_SEED", "0"
        ) not in {"1", "true", "TRUE"}:
            seed_initial_data()

    return app


def _configure_logging(app: Flask) -> None:
    if app.config.get("TESTING"):
        return

    log_dir = Path(app.instance_path)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "app.log"

    if any(
        isinstance(handler, RotatingFileHandler)
        and getattr(handler, "baseFilename", None) == str(log_path)
        for handler in app.logger.handlers
    ):
        return

    handler = RotatingFileHandler(log_path, maxBytes=1_048_576, backupCount=3)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)
