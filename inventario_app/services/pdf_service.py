import base64
from html import escape
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)
from ..constants import PDF_LAYOUT_VERSION
from .media_service import upload_pdf_file
from ..utils.rich_text import rich_text_to_reportlab_blocks


def build_inventory_pdf(inventario, secciones, firmas) -> str:
    inmueble = inventario.inmueble
    empresa_nombre = inmueble.empresa.nombre
    nombre_pdf = f"inventario_{inventario.id}_v{PDF_LAYOUT_VERSION}.pdf"

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
        fontName="Helvetica",
        fontSize=11,
        leading=16,
        textColor=colors.black,
        spaceAfter=7,
    )
    rich_label_style = ParagraphStyle(
        "InventarioRichLabel",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=19.8,
        textColor=colors.black,
        spaceAfter=5,
        keepWithNext=True,
    )
    rich_body_style = ParagraphStyle(
        "InventarioRichBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=12,
        leading=19.8,
        textColor=colors.black,
        spaceAfter=0,
    )
    rich_list_style = ParagraphStyle(
        "InventarioRichList",
        parent=rich_body_style,
        leftIndent=18,
        firstLineIndent=-18,
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

        inventory_label = f"Inventario #{inventario.id}"
        right_edge = letter[0] - doc.rightMargin
        inventory_width = stringWidth(inventory_label, "Helvetica", 9)
        company_width = right_edge - doc.leftMargin - inventory_width - 18

        canvas.setFillColor(colors.HexColor("#153385"))
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(
            doc.leftMargin,
            764,
            _fit_text(empresa_nombre, "Helvetica-Bold", 11, company_width),
        )

        canvas.setFillColor(colors.HexColor("#5b6472"))
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(right_edge, 764, inventory_label)

        canvas.line(doc.leftMargin, 30, letter[0] - doc.rightMargin, 30)
        canvas.drawString(doc.leftMargin, 18, empresa_nombre)
        canvas.drawRightString(
            letter[0] - doc.rightMargin,
            18,
            f"Página {canvas.getPageNumber()}",
        )
        canvas.restoreState()

    with TemporaryDirectory(prefix=f"inventario_pdf_{inventario.id}_") as temp_dir:
        temp_path = Path(temp_dir)
        elementos = [
            Paragraph("Inventario de Entrega de Inmueble", title_style),
            Paragraph("Resumen general del recorrido documentado.", note_style),
            Spacer(1, 12),
            Paragraph(_label_value("Empresa", empresa_nombre), meta_style),
            Paragraph(_label_value("Dirección", inmueble.direccion), meta_style),
            Paragraph(_label_value("Fecha de recepción", inmueble.fecha_recepcion), meta_style),
            Paragraph(_label_value("Inventario", inventario.nombre), meta_style),
            Paragraph(_label_value("Fecha inventario", inventario.fecha), meta_style),
            Spacer(1, 18),
        ]

        for seccion in secciones:
            elementos.append(Paragraph(f"Sección: {_safe_text(seccion.nombre)}", section_style))
            elementos.append(
                Paragraph(
                    f"<b>Archivos:</b> {len(seccion.fotos)} | <b>Observaciones:</b> {len(seccion.observaciones)}",
                    note_style,
                )
            )

            if seccion.fotos:
                elementos.append(
                    Paragraph(
                        f"Evidencia multimedia registrada: {len(seccion.fotos)} archivo(s). No incluida en el PDF.",
                        note_style,
                    )
                )
                elementos.append(Spacer(1, 4))
            else:
                elementos.append(Paragraph("Sin evidencia multimedia cargada.", note_style))
                elementos.append(Spacer(1, 6))

            descripcion = (seccion.descripcion or "").strip()
            if descripcion:
                elementos.extend(
                    _rich_text_flowables(
                        "Descripción",
                        descripcion,
                        rich_label_style,
                        rich_body_style,
                        rich_list_style,
                    )
                )
                elementos.append(Spacer(1, 10))

            tiene_observaciones = False
            for observacion in seccion.observaciones:
                tiene_observaciones = True
                elementos.extend(
                    _rich_text_flowables(
                        "Observación",
                        observacion.comentario,
                        rich_label_style,
                        rich_body_style,
                        rich_list_style,
                    )
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


def _safe_text(value) -> str:
    return escape("" if value is None else str(value))


def _label_value(label: str, value) -> str:
    return f"<b>{escape(label)}:</b> {_safe_text(value)}"


def _rich_text_flowables(
    label: str,
    value,
    label_style: ParagraphStyle,
    body_style: ParagraphStyle,
    list_style: ParagraphStyle,
) -> list:
    flowables = [Paragraph(f"{escape(label)}:", label_style)]
    blocks = rich_text_to_reportlab_blocks(value)

    for block_index, block in enumerate(blocks):
        if block_index:
            flowables.append(Spacer(1, 8))

        if block.kind == "paragraph":
            flowables.append(Paragraph(block.content, body_style))
        elif block.kind == "spacer":
            flowables.append(Spacer(1, body_style.leading))
        else:
            marker = "&#8226;" if block.kind == "unordered_list" else None
            for item_index, item in enumerate(block.items, start=1):
                if item_index > 1:
                    flowables.append(Spacer(1, 2.4))
                bullet = marker or f"{item_index}."
                flowables.append(Paragraph(f"{bullet} {item}", list_style))

    return flowables


def _fit_text(value, font_name: str, font_size: float, max_width: float) -> str:
    text = "" if value is None else str(value)
    if stringWidth(text, font_name, font_size) <= max_width:
        return text

    suffix = "..."
    while text and stringWidth(f"{text}{suffix}", font_name, font_size) > max_width:
        text = text[:-1]
    return f"{text.rstrip()}{suffix}"
