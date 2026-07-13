import uuid

from sqlalchemy.sql import func

from ..extensions import db
from ..constants import MEDIA_TYPE_IMAGE, PDF_STATUS_NOT_STARTED, VIDEO_STATUS_READY


class Inmueble(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    direccion = db.Column(db.String(200), nullable=False)
    propietario = db.Column(db.String(200), nullable=False)
    fecha_recepcion = db.Column(db.Date, nullable=False)
    empresa_id = db.Column(
        db.Integer, db.ForeignKey("empresa.id"), nullable=False, index=True
    )
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    inventarios = db.relationship(
        "Inventario",
        backref="inmueble",
        lazy=True,
        cascade="all, delete-orphan",
    )


class Inventario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    inmueble_id = db.Column(
        db.Integer, db.ForeignKey("inmueble.id"), nullable=False, index=True
    )
    created_by_id = db.Column(
        db.Integer, db.ForeignKey("usuario.id"), nullable=True, index=True
    )
    nombre = db.Column(db.String(200), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    token = db.Column(
        db.String(100),
        unique=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    pdf_status = db.Column(
        db.String(20), nullable=False, default=PDF_STATUS_NOT_STARTED, index=True
    )
    pdf_filename = db.Column(db.String(255), nullable=True)
    pdf_error = db.Column(db.Text, nullable=True)
    pdf_requested_at = db.Column(db.DateTime(timezone=True), nullable=True)
    pdf_generated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    pdf_version = db.Column(db.Integer, nullable=False, default=0)
    pdf_job_id = db.Column(db.String(100), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    secciones = db.relationship(
        "Seccion",
        backref="inventario",
        lazy=True,
        cascade="all, delete-orphan",
    )
    firmas = db.relationship(
        "Firma",
        backref="inventario_rel",
        lazy=True,
        cascade="all, delete-orphan",
    )
    creador = db.relationship("Usuario", foreign_keys=[created_by_id])


class Seccion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    inventario_id = db.Column(
        db.Integer, db.ForeignKey("inventario.id"), nullable=False, index=True
    )
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    fotos = db.relationship(
        "Foto",
        backref="seccion",
        lazy=True,
        cascade="all, delete-orphan",
    )
    observaciones = db.relationship(
        "Observacion",
        backref="seccion",
        lazy=True,
        cascade="all, delete-orphan",
    )


class Foto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    seccion_id = db.Column(
        db.Integer, db.ForeignKey("seccion.id"), nullable=False, index=True
    )
    archivo = db.Column(db.String(255), nullable=False)
    tipo = db.Column(db.String(20), nullable=False, default=MEDIA_TYPE_IMAGE, index=True)
    archivo_original = db.Column(db.String(255), nullable=True)
    processing_status = db.Column(
        db.String(30), nullable=False, default=VIDEO_STATUS_READY, index=True
    )
    processing_error = db.Column(db.Text, nullable=True)
    size_bytes = db.Column(db.BigInteger, nullable=True)
    duration_seconds = db.Column(db.Integer, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Observacion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    seccion_id = db.Column(
        db.Integer, db.ForeignKey("seccion.id"), nullable=False, index=True
    )
    comentario = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Firma(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    inventario_id = db.Column(
        db.Integer, db.ForeignKey("inventario.id"), nullable=False, index=True
    )
    nombre = db.Column(db.String(200), nullable=False)
    cedula = db.Column(db.String(80), nullable=True)
    celular = db.Column(db.String(80), nullable=True)
    correo = db.Column(db.String(255), nullable=True)
    imagen = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
