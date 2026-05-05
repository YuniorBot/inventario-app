def test_privacy_policy_is_public(client):
    response = client.get("/privacy-policy")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Política de Privacidad" in body
    assert "Intoryx" in body


def test_terms_are_public(client):
    response = client.get("/terms")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Términos y Condiciones" in body
    assert "Intoryx" in body


def test_login_links_to_legal_pages(client):
    response = client.get("/login")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'href="/privacy-policy"' in body
    assert 'href="/terms"' in body
