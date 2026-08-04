"""Every failure path must answer with the same envelope, including framework errors."""

from fastapi.testclient import TestClient


def test_unknown_route_uses_the_error_envelope(client: TestClient) -> None:
    response = client.get("/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_wrong_method_reports_method_not_allowed(client: TestClient) -> None:
    response = client.get("/documents")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"


def test_missing_file_part_reports_a_validation_error(client: TestClient) -> None:
    response = client.post("/documents")

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert "file" in body["error"]["message"]
