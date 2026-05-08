import base64
from html import escape
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from flask import current_app
from PIL import Image as PILImage, ImageOps, UnidentifiedImageError
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from .media_service import get_uploaded_file_bytes, upload_pdf_file

PDF_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}


def build_inventory_pdf(inventario, secciones, firmas) -> str:
    inmueble = inventario.inmueble
    nombre_pdf = f"inventario_{inventario.id}.pdf"

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "InventarioTitle",
        parent=styles["Title"],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#153385"),
        spaceAfter=10,
    )
    section_style = ParagraphStyle(
        "InventarioSection",
        parent=styles["Heading2"],
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#153385"),
        spaceBefore=8,
        spaceAfter=8,
    )
    meta_style = ParagraphStyle(
        "InventarioMeta",
        parent=styles["BodyText"],
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#243041"),
        spaceAfter=6,
    )
    note_style = ParagraphStyle(
        "InventarioNote",
        parent=styles["BodyText"],
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#5b6472"),
        spaceAfter=8,
    )

    def dibujar_encabezado_y_pie(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#d7e1f5"))
        canvas.setLineWidth(1)
        canvas.line(doc.leftMargin, 752, letter[0] - doc.rightMargin, 752)

        canvas.setFillColor(colors.HexColor("#153385"))
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(doc.leftMargin, 764, "Inventario App")

        canvas.setFillColor(colors.HexColor("#5b6472"))
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(
            letter[0] - doc.rightMargin,
            764,
            f"Inventario #{inventario.id}",
        )

        canvas.line(doc.leftMargin, 30, letter[0] - doc.rightMargin, 30)
        canvas.drawString(doc.leftMargin, 18, inmueble.empresa.nombre)
        canvas.drawRightString(
            letter[0] - doc.rightMargin,
            18,
            f"Pagina {canvas.getPageNumber()}",
        )
        canvas.restoreState()

    with TemporaryDirectory(prefix=f"inventario_pdf_{inventario.id}_") as temp_dir:
        temp_path = Path(temp_dir)
        image_index = 0
        elementos = [
            Paragraph("Inventario de Entrega de Inmueble", title_style),
            Paragraph("Resumen general del recorrido documentado.", note_style),
            Spacer(1, 12),
            Paragraph(_label_value("Empresa", inmueble.empresa.nombre), meta_style),
            Paragraph(_label_value("Direccion", inmueble.direccion), meta_style),
            Paragraph(_label_value("Fecha de recepcion", inmueble.fecha_recepcion), meta_style),
            Paragraph(_label_value("Inventario", inventario.nombre), meta_style),
            Paragraph(_label_value("Fecha inventario", inventario.fecha), meta_style),
            Spacer(1, 18),
        ]

        for seccion in secciones:
            elementos.append(Paragraph(f"Seccion: {_safe_text(seccion.nombre)}", section_style))
            elementos.append(
                Paragraph(
                    f"<b>Archivos:</b> {len(seccion.fotos)} | <b>Observaciones:</b> {len(seccion.observaciones)}",
                    note_style,
                )
            )

            tiene_evidencia = False
            fila_galeria = []
            for foto in seccion.fotos:
                ext = foto.archivo.rsplit(".", 1)[-1].lower()
                if ext not in PDF_IMAGE_EXTENSIONS:
                    continue

                archivo_bytes = get_uploaded_file_bytes(foto.archivo)
                if not archivo_bytes:
                    continue

                image_index += 1
                imagen_path = temp_path / f"pdf_image_{image_index}.jpg"
                if not _prepare_pdf_image_file(archivo_bytes, imagen_path):
                    current_app.logger.warning(
                        "pdf_image_skipped inventario_id=%s archivo=%s",
                        inventario.id,
                        foto.archivo,
                    )
                    continue

                tiene_evidencia = True
                imagen = Image(str(imagen_path))
                imagen._restrictSize(2.6 * inch, 2.1 * inch)
                fila_galeria.append(imagen)

                if len(fila_galeria) == 2:
                    _append_gallery(elementos, fila_galeria)
                    fila_galeria = []

            if fila_galeria:
                _append_gallery(elementos, fila_galeria)

            if tiene_evidencia:
                elementos.append(Spacer(1, 4))
            else:
                elementos.append(Paragraph("Sin evidencia multimedia cargada.", note_style))
                elementos.append(Spacer(1, 6))

            descripcion = (seccion.descripcion or "").strip()
            if descripcion:
                elementos.append(Paragraph(_label_value("Descripcion", descripcion), meta_style))
                elementos.append(Spacer(1, 10))

            tiene_observaciones = False
            for observacion in seccion.observaciones:
                tiene_observaciones = True
                elementos.append(
                    Paragraph(_label_value("Observacion", observacion.comentario), meta_style)
                )
                elementos.append(Spacer(1, 10))

            if not tiene_observaciones:
                elementos.append(Paragraph("Sin observaciones registradas.", note_style))

            elementos.append(Spacer(1, 20))

        if firmas:
            elementos.append(PageBreak())
            elementos.append(Paragraph("Firmas del inventario", title_style))
            elementos.append(Spacer(1, 18))

            for firma in firmas:
                elementos.append(Paragraph(_label_value("Firmado por", firma.nombre), meta_style))
                if firma.cedula:
                    elementos.append(Paragraph(_label_value("Cédula", firma.cedula), meta_style))
                if firma.celular:
                    elementos.append(Paragraph(_label_value("Celular", firma.celular), meta_style))
                if firma.correo:
                    elementos.append(
                        Paragraph(_label_value("Correo electrónico", firma.correo), meta_style)
                    )
                elementos.append(Spacer(1, 10))

                try:
                    imagen_base64 = firma.imagen.split(",", 1)[1]
                    imagen_bytes = base64.b64decode(imagen_base64)
                    imagen_firma = Image(BytesIO(imagen_bytes))
                    imagen_firma._restrictSize(3.2 * inch, 1.6 * inch)
                    elementos.append(imagen_firma)
                    elementos.append(Spacer(1, 20))
                except Exception:
                    elementos.append(
                        Paragraph("No se pudo renderizar una firma.", note_style)
                    )
                    elementos.append(Spacer(1, 20))

        pdf_path = temp_path / nombre_pdf
        pdf = SimpleDocTemplate(
            str(pdf_path),
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=78,
            bottomMargin=46,
        )
        pdf.build(
            elementos,
            onFirstPage=dibujar_encabezado_y_pie,
            onLaterPages=dibujar_encabezado_y_pie,
        )
        upload_pdf_file(nombre_pdf, pdf_path)
    return nombre_pdf


def _append_gallery(elementos, galeria) -> None:
    filas = [galeria[index : index + 2] for index in range(0, len(galeria), 2)]
    for fila in filas:
        if len(fila) == 1:
            fila.append(Spacer(1, 1))
    tabla_galeria = Table(filas, colWidths=[2.75 * inch, 2.75 * inch], hAlign="LEFT")
    tabla_galeria.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elementos.append(tabla_galeria)


def _prepare_pdf_image(payload: bytes) -> BytesIO | None:
    try:
        with PILImage.open(BytesIO(payload)) as source:
            image = ImageOps.exif_transpose(source)
            image.thumbnail(
                (
                    current_app.config.get("PDF_IMAGE_MAX_WIDTH", 1200),
                    current_app.config.get("PDF_IMAGE_MAX_HEIGHT", 900),
                )
            )
            if image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")

            output = BytesIO()
            image.save(
                output,
                format="JPEG",
                optimize=True,
                quality=current_app.config.get("PDF_IMAGE_JPEG_QUALITY", 78),
            )
            output.seek(0)
            return output
    except (UnidentifiedImageError, OSError, ValueError):
        return None


def _prepare_pdf_image_file(payload: bytes, output_path: Path) -> bool:
    try:
        with PILImage.open(BytesIO(payload)) as source:
            image = ImageOps.exif_transpose(source)
            image.thumbnail(
                (
                    current_app.config.get("PDF_IMAGE_MAX_WIDTH", 1200),
                    current_app.config.get("PDF_IMAGE_MAX_HEIGHT", 900),
                )
            )
            if image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")

            image.save(
                output_path,
                format="JPEG",
                optimize=True,
                quality=current_app.config.get("PDF_IMAGE_JPEG_QUALITY", 78),
            )
            return True
    except (UnidentifiedImageError, OSError, ValueError):
        return False


def _safe_text(value) -> str:
    return escape("" if value is None else str(value))


def _label_value(label: str, value) -> str:
    return f"<b>{escape(label)}:</b> {_safe_text(value)}"
