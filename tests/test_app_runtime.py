from fastapi.testclient import TestClient

from app.main import app, mcp_app


def test_health_endpoint_starts_application():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_frontend_is_served_from_root():
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_mcp_endpoint_uses_sdk_default_path():
    # FastMCP's Streamable HTTP app exposes /mcp by default. The host app
    # mounts that sub-application at / so that the public path is exactly /mcp.
    assert any(getattr(route, "path", None) == "/mcp" for route in mcp_app.routes)


def test_api_routes_are_not_shadowed_by_mcp_catch_all_mount():
    paths = [getattr(route, "path", None) for route in app.routes]
    assert paths.index("/health") < paths.index("/")
