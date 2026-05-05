from .auth import bp as auth_bp
from .dashboard import bp as dashboard_bp
from .inmuebles import bp as inmuebles_bp
from .inventarios import bp as inventarios_bp
from .legal import bp as legal_bp
from .media import bp as media_bp
from .public import bp as public_bp
from .secciones import bp as secciones_bp
from .superadmin import bp as superadmin_bp
from .usuarios import bp as usuarios_bp

ALL_BLUEPRINTS = [
    public_bp,
    legal_bp,
    media_bp,
    auth_bp,
    dashboard_bp,
    inmuebles_bp,
    inventarios_bp,
    secciones_bp,
    usuarios_bp,
    superadmin_bp,
]
