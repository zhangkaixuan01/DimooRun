from dimoo_run.server import create_app
from fastapi.testclient import TestClient


def test_healthz_returns_service_status() -> None:
    client = TestClient(create_app())

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "dimoorun-server",
        "version": "0.1.0",
    }


def test_openapi_title_is_dimoorun_api() -> None:
    client = TestClient(create_app())

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "DimooRun API"
