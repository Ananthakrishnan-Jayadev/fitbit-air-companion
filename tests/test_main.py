from pathlib import Path

from fastapi.testclient import TestClient

from fitbit_app.config import Settings

INDEX_HTML = "<!doctype html><title>app</title><div id=root></div>"


def _build_ui(settings: Settings) -> None:
    (settings.static_dir / "index.html").write_text(INDEX_HTML)
    assets = settings.static_dir / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log('app')")


def test_ui_not_built_page(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 503
    assert "fitbit build-ui" in response.text


def test_serves_index_at_root(client: TestClient, settings: Settings) -> None:
    _build_ui(settings)
    response = client.get("/")
    assert response.status_code == 200
    assert response.text == INDEX_HTML


def test_client_routes_fall_back_to_index(client: TestClient, settings: Settings) -> None:
    _build_ui(settings)
    assert client.get("/sleep").text == INDEX_HTML
    assert client.get("/trends/hrv").text == INDEX_HTML


def test_serves_static_assets(client: TestClient, settings: Settings) -> None:
    _build_ui(settings)
    response = client.get("/assets/app.js")
    assert response.status_code == 200
    assert response.text == "console.log('app')"


def test_unknown_api_route_is_json_404(client: TestClient, settings: Settings) -> None:
    _build_ui(settings)
    for path in ("/api", "/api/does-not-exist"):
        response = client.get(path)
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found"}


def test_path_traversal_does_not_escape_static_dir(
    client: TestClient, settings: Settings, tmp_path: Path
) -> None:
    _build_ui(settings)
    (tmp_path / "secret.txt").write_text("TOP SECRET")
    for path in ("/%2e%2e/secret.txt", "/..%2fsecret.txt", "/assets/%2e%2e/%2e%2e/secret.txt"):
        response = client.get(path)
        assert "TOP SECRET" not in response.text
