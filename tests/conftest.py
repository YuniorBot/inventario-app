import sys
from io import BytesIO
from datetime import date
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from inventario_app import create_app
from inventario_app.constants import ROLE_ADMIN, ROLE_EDITOR, ROLE_VIEWER, STATUS_ACTIVE
from inventario_app.extensions import db
from inventario_app.models import Empresa, Inmueble, Inventario, Seccion, Usuario


class FakeS3Client:
    def __init__(self):
        self.objects = {}

    def upload_fileobj(self, fileobj, bucket, key, ExtraArgs=None):
        fileobj.seek(0)
        self.objects[(bucket, key)] = {
            "Body": fileobj.read(),
            "ContentType": (ExtraArgs or {}).get("ContentType", "application/octet-stream"),
        }

    def put_object(self, Bucket, Key, Body, ContentType=None):
        payload = Body if isinstance(Body, bytes) else Body.read()
        self.objects[(Bucket, Key)] = {
            "Body": payload,
            "ContentType": ContentType or "application/octet-stream",
        }

    def get_object(self, Bucket, Key):
        item = self.objects[(Bucket, Key)]
        return {"Body": BytesIO(item["Body"]), "ContentType": item["ContentType"]}

    def delete_object(self, Bucket, Key):
        self.objects.pop((Bucket, Key), None)

    def head_object(self, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            raise KeyError(Key)
        return {"ContentLength": len(self.objects[(Bucket, Key)]["Body"])}

    def generate_presigned_url(self, _operation_name, Params, ExpiresIn):
        return (
            f"https://fake-s3.local/{Params['Bucket']}/{Params['Key']}"
            f"?expires={ExpiresIn}"
        )

    def generate_presigned_post(self, Bucket, Key, Fields, Conditions, ExpiresIn):
        return {
            "url": f"https://fake-s3.local/{Bucket}",
            "fields": {"key": Key, **Fields},
            "conditions": Conditions,
            "expires": ExpiresIn,
        }


class FakeSESClient:
    def __init__(self):
        self.messages = []

    def send_email(self, Source, Destination, Message):
        payload = {
            "Source": Source,
            "Destination": Destination,
            "Message": Message,
        }
        self.messages.append(payload)
        return {"MessageId": f"fake-message-{len(self.messages)}"}


@pytest.fixture()
def app(tmp_path):
    database_path = tmp_path / "test.db"
    upload_dir = tmp_path / "uploads"
    pdf_dir = tmp_path / "pdfs"
    upload_dir.mkdir()
    pdf_dir.mkdir()

    app = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SKIP_DATA_SEED": True,
            "STORAGE_BACKEND": "s3",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path}",
            "UPLOAD_FOLDER": str(upload_dir),
            "PDF_FOLDER": str(pdf_dir),
            "S3_BUCKET_NAME": "test-bucket",
            "AWS_REGION": "us-east-2",
            "APP_BASE_URL": "https://intoryx.test",
            "AWS_SES_FROM_EMAIL": "no-reply@intoryx.com",
            "AWS_SES_FROM_NAME": "Intoryx",
            "S3_UPLOAD_PREFIX": "uploads",
            "S3_PDF_PREFIX": "pdfs",
            "S3_SIGNED_URL_EXPIRES": 300,
            "PASSWORD_RESET_TOKEN_TTL_SECONDS": 300,
        }
    )
    app.extensions["s3_client"] = FakeS3Client()
    app.extensions["ses_client"] = FakeSESClient()

    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def make_company(app):
    def factory(
        nombre: str, slug: str, estado: str = STATUS_ACTIVE, activo: bool = True
    ):
        empresa = Empresa(nombre=nombre, slug=slug, estado=estado, activo=activo)
        db.session.add(empresa)
        db.session.commit()
        return empresa

    return factory


@pytest.fixture()
def make_user(app):
    def factory(
        empresa_id: int,
        nombre: str,
        email: str,
        password: str = "secret123",
        rol: str = ROLE_ADMIN,
        activo: bool = True,
    ):
        usuario = Usuario(
            nombre=nombre,
            email=email,
            password=generate_password_hash(password),
            empresa_id=empresa_id,
            rol=rol,
            activo=activo,
        )
        db.session.add(usuario)
        db.session.commit()
        return usuario

    return factory


@pytest.fixture()
def make_inmueble(app):
    def factory(
        empresa_id: int, direccion: str = "Calle 1", propietario: str = "Owner"
    ):
        inmueble = Inmueble(
            direccion=direccion,
            propietario=propietario,
            fecha_recepcion=date(2026, 4, 1),
            empresa_id=empresa_id,
        )
        db.session.add(inmueble)
        db.session.commit()
        return inmueble

    return factory


@pytest.fixture()
def make_inventario(app):
    def factory(
        inmueble_id: int, nombre: str = "Entrega inicial", token: str = "public-token"
    ):
        inventario = Inventario(
            inmueble_id=inmueble_id,
            nombre=nombre,
            fecha=date(2026, 4, 2),
            token=token,
        )
        db.session.add(inventario)
        db.session.commit()
        return inventario

    return factory


@pytest.fixture()
def make_seccion(app):
    def factory(inventario_id: int, nombre: str = "Sala"):
        seccion = Seccion(inventario_id=inventario_id, nombre=nombre)
        db.session.add(seccion)
        db.session.commit()
        return seccion

    return factory


@pytest.fixture()
def seeded_data(
    app, make_company, make_user, make_inmueble, make_inventario, make_seccion
):
    empresa_a = make_company("Empresa A", "empresa-a")
    empresa_b = make_company("Empresa B", "empresa-b")

    admin_a = make_user(empresa_a.id, "Admin A", "admin-a@test.com", rol=ROLE_ADMIN)
    editor_a = make_user(empresa_a.id, "Editor A", "editor-a@test.com", rol=ROLE_EDITOR)
    viewer_a = make_user(empresa_a.id, "Viewer A", "viewer-a@test.com", rol=ROLE_VIEWER)
    admin_b = make_user(empresa_b.id, "Admin B", "admin-b@test.com", rol=ROLE_ADMIN)
    inactive_a = make_user(
        empresa_a.id,
        "Inactive A",
        "inactive-a@test.com",
        rol=ROLE_VIEWER,
        activo=False,
    )

    inmueble_a = make_inmueble(empresa_a.id, direccion="Calle A")
    inmueble_b = make_inmueble(empresa_b.id, direccion="Calle B")
    inventario_a = make_inventario(inmueble_a.id, token="token-a")
    inventario_b = make_inventario(inmueble_b.id, token="token-b")
    seccion_a = make_seccion(inventario_a.id, nombre="Sala A")

    return {
        "empresa_a": empresa_a,
        "empresa_b": empresa_b,
        "admin_a": admin_a,
        "editor_a": editor_a,
        "viewer_a": viewer_a,
        "admin_b": admin_b,
        "inactive_a": inactive_a,
        "inmueble_a": inmueble_a,
        "inmueble_b": inmueble_b,
        "inventario_a": inventario_a,
        "inventario_b": inventario_b,
        "seccion_a": seccion_a,
    }


@pytest.fixture()
def login(client):
    def do_login(
        email: str,
        password: str = "secret123",
        follow_redirects: bool = False,
        next_url: str | None = None,
    ):
        login_url = "/login"
        if next_url:
            login_url = f"{login_url}?next={next_url}"
        return client.post(
            login_url,
            data={"email": email, "password": password},
            follow_redirects=follow_redirects,
        )

    return do_login
