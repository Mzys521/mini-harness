import re
from types import SimpleNamespace

from fastapi.testclient import TestClient

from harness.platform.api import create_app


def test_workspace_is_served_with_local_assets() -> None:
    """The built Vue workspace must be served same-origin with its own assets.

    Asset filenames are content-hashed by Vite, so the test discovers them from
    the served HTML instead of hard-coding names.
    """
    runtime = SimpleNamespace(service=object())
    app = create_app(runtime, start_background_workers=False)
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")

        # The shell is a mount point; markup now lives in the Vue app.
        assert 'id="app"' in response.text

        scripts = re.findall(r'src="(/ui/assets/[^"]+\.js)"', response.text)
        styles = re.findall(r'href="(/ui/assets/[^"]+\.css)"', response.text)
        assert scripts, "the workspace entry bundle is missing from index.html"
        assert styles, "the workspace stylesheet is missing from index.html"

        for asset in (*scripts, *styles):
            asset_response = client.get(asset)
            assert asset_response.status_code == 200
            assert len(asset_response.content) > 0

        icon = client.get("/ui/icon.svg")
        assert icon.status_code == 200
        assert "image/svg+xml" in icon.headers["content-type"]

        # Superseded hand-written assets must no longer be published.
        assert client.get("/ui/app.js").status_code == 404
        assert client.get("/ui/styles.css").status_code == 404

        assert client.get("/healthz").json()["status"] == "ok"
        assert "/v1/runs" in client.get("/openapi.json").json()["paths"]


def test_workspace_does_not_expose_project_files() -> None:
    app = create_app(SimpleNamespace(service=object()), start_background_workers=False)
    with TestClient(app) as client:
        for path in (
            "/ui/.env",
            "/ui/main.py",
            "/ui/%2e%2e/%2e%2e/%2e%2e/.env",
            "/ui/missing.js",
            "/ui/assets/missing.js",
        ):
            assert client.get(path).status_code == 404
