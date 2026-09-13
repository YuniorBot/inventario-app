from inventario_app.extensions import db
from inventario_app.models import Observacion, Seccion
from inventario_app.utils.rich_text import (
    rich_text_has_content,
    rich_text_to_reportlab,
    sanitize_rich_text,
)


def test_sanitizer_keeps_formatting_and_removes_dangerous_markup():
    cleaned = sanitize_rich_text(
        '<p onclick="alert(1)"><strong>Estado</strong> correcto'
        '<script>alert(2)</script><img src=x onerror="alert(3)"></p>'
    )

    assert cleaned == "<p><strong>Estado</strong> correctoalert(2)</p>"
    assert "onclick" not in cleaned
    assert "onerror" not in cleaned
    assert "<script" not in cleaned
    assert "<img" not in cleaned


def test_rich_text_empty_markup_has_no_content():
    assert not rich_text_has_content("<p><br></p>")
    assert not rich_text_has_content("<ul><li>&nbsp;</li></ul>")
    assert rich_text_has_content("<p><strong>Contenido</strong></p>")


def test_reportlab_conversion_preserves_inline_format_and_lists():
    converted = rich_text_to_reportlab(
        "<p><strong>Bueno</strong> y <em>revisado</em>.</p>"
        "<ol><li>Puerta</li><li><u>Ventana</u></li></ol>"
    )

    assert "<b>Bueno</b> y <i>revisado</i>." in converted
    assert "1. Puerta" in converted
    assert "2. <u>Ventana</u>" in converted


def test_description_sanitizes_rich_text_and_renders_on_public_page(
    client, login, seeded_data, app
):
    login(seeded_data["admin_a"].email)

    response = client.post(
        f"/guardar_descripcion/{seeded_data['seccion_a'].id}",
        data={
            "descripcion": (
                '<p><strong>Buen estado</strong></p>'
                '<script>alert("xss")</script>'
            )
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        seccion = db.session.get(Seccion, seeded_data["seccion_a"].id)
        assert seccion.descripcion == '<p><strong>Buen estado</strong></p>alert("xss")'

    public_response = client.get(f"/publico/{seeded_data['inventario_a'].token}")
    body = public_response.get_data(as_text=True)

    assert public_response.status_code == 200
    assert "<strong>Buen estado</strong>" in body
    assert '<script>alert("xss")</script>' not in body


def test_empty_rich_text_description_is_stored_as_null(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)

    response = client.post(
        f"/guardar_descripcion/{seeded_data['seccion_a'].id}",
        data={"descripcion": "<p><br></p>"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        seccion = db.session.get(Seccion, seeded_data["seccion_a"].id)
        assert seccion.descripcion is None


def test_observation_accepts_sanitized_rich_text(client, login, seeded_data, app):
    login(seeded_data["admin_a"].email)

    response = client.post(
        f"/crear_observacion/{seeded_data['seccion_a'].id}",
        data={"comentario": "<ul><li><em>Pintura</em></li></ul>"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        observacion = Observacion.query.filter_by(
            seccion_id=seeded_data["seccion_a"].id
        ).one()
        assert observacion.comentario == "<ul><li><em>Pintura</em></li></ul>"


def test_section_editors_render_as_collapsible_panels(
    client, login, seeded_data, app
):
    with app.app_context():
        observacion = Observacion(
            seccion_id=seeded_data["seccion_a"].id,
            comentario="Detalle editable",
        )
        db.session.add(observacion)
        db.session.commit()
        observacion_id = observacion.id

    login(seeded_data["admin_a"].email)
    response = client.get(f"/seccion/{seeded_data['seccion_a'].id}")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'data-editor-toggle="description-editor-panel"' in body
    assert 'id="description-editor-panel"' in body
    assert 'data-editor-toggle="new-observation-editor-panel"' in body
    assert f'data-editor-toggle="observation-editor-panel-{observacion_id}"' in body
    assert f'data-editor-cancel="observation-editor-panel-{observacion_id}"' in body
    assert "/static/rich-text-editor.js" in body


def test_viewer_does_not_receive_editor_controls(client, login, seeded_data):
    login(seeded_data["viewer_a"].email)
    response = client.get(f"/seccion/{seeded_data['seccion_a'].id}")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "data-editor-toggle" not in body
    assert "data-editor-panel" not in body
    assert "/static/rich-text-editor.js" not in body
