"""
Tests for serving the SPA and ``/config.js`` from the API process.

The SPA is a fake ``dist/`` in a temporary directory: ``index.html``,
one hashed asset, ``favicon.svg`` and the Vite dev stub ``config.js``
(which the rendered route must shadow).
"""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.errors import ConfigurationError
from app.main import create_app
from app.web import IMMUTABLE, NO_CACHE, render_config_js
from tests.auth_helpers import https_client

AUTHORITY = "https://idp.example.com:8443/realms/adr"
IDP_ORIGIN = "https://idp.example.com:8443"
CLIENT_ID = "adriano"
INDEX_HTML = "<!doctype html><title>spa</title>"
ASSET = "/assets/index-abc123.js"

#: Keys of ``RuntimeConfig`` in ``frontend/src/config.ts``.
RUNTIME_CONFIG_KEYS = {"apiBaseUrl", "oidcEnabled"}


@pytest.fixture
def spa_dir(tmp_path: Path) -> Path:
    """
    Build a fake SPA build directory.

    :param tmp_path: Pytest temporary directory.
    :returns: The directory.
    """
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(INDEX_HTML)
    (dist / ASSET.removeprefix("/")).write_text("console.log(1);")
    (dist / "favicon.svg").write_text("<svg/>")
    (dist / "config.js").write_text("window.__APP_CONFIG__ = {};")
    (tmp_path / "secret.txt").write_text("outside the SPA")
    return dist


@pytest.fixture
def spa_settings(test_settings: Settings, spa_dir: Path) -> Settings:
    """
    Build test settings that serve the fake SPA with OIDC configured.

    :param test_settings: Settings pointed at the test database.
    :param spa_dir: The fake SPA directory.
    :returns: The settings.
    """
    return test_settings.model_copy(
        update={
            "static_dir": spa_dir,
            "oidc_authority": AUTHORITY,
            "oidc_client_id": CLIENT_ID,
        }
    )


def _client(settings: Settings) -> TestClient:
    """
    Build an un-entered test client for *settings*.

    :param settings: Application settings.
    :returns: The client.
    """
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    return https_client(app)


@pytest.fixture
def spa_client(spa_settings: Settings) -> Iterator[TestClient]:
    """
    Provide a client for the app serving the fake SPA.

    :param spa_settings: Settings with ``static_dir`` set.
    :returns: The client.
    """
    with _client(spa_settings) as client:
        yield client


def _config_object(script: str) -> dict[str, str]:
    """
    Parse the object out of a rendered ``config.js``.

    :param script: The script source.
    :returns: The decoded object.
    """
    prefix = "window.__APP_CONFIG__ = "
    assert script.startswith(prefix)
    assert script.endswith(";\n")
    return json.loads(script.removeprefix(prefix).removesuffix(";\n"))


def _directive(csp: str, name: str) -> list[str]:
    """
    Return the sources of one CSP directive.

    :param csp: The policy.
    :param name: Directive name.
    :returns: Its source list.
    """
    for directive in csp.split(";"):
        parts = directive.split()
        if parts and parts[0] == name:
            return parts[1:]
    raise AssertionError(f"no {name} in {csp}")


def test_config_js_is_rendered_from_the_settings(
    spa_client: TestClient,
) -> None:
    """Ensure /config.js says OIDC is enabled and carries no client keys."""
    response = spa_client.get("/config.js")

    assert response.status_code == 200
    assert _config_object(response.text) == {
        "apiBaseUrl": "",
        "oidcEnabled": True,
    }
    assert AUTHORITY not in response.text
    assert CLIENT_ID not in response.text


def test_config_js_without_oidc(spa_settings: Settings) -> None:
    """Ensure oidcEnabled is false when no authority is configured."""
    settings = spa_settings.model_copy(update={"oidc_authority": None})

    assert _config_object(render_config_js(settings)) == {
        "apiBaseUrl": "",
        "oidcEnabled": False,
    }


def test_config_js_is_javascript_and_never_cached(
    spa_client: TestClient,
) -> None:
    """Ensure /config.js is served as uncached JavaScript."""
    response = spa_client.get("/config.js")

    assert response.headers["content-type"].startswith("application/javascript")
    assert response.headers["cache-control"] == NO_CACHE


def test_config_js_has_exactly_the_runtime_config_keys(
    spa_client: TestClient,
) -> None:
    """Ensure /config.js has no dev-auth (or any other extra) key."""
    script = spa_client.get("/config.js").text

    assert set(_config_object(script)) == RUNTIME_CONFIG_KEYS
    assert "dev" not in script.lower()
    assert "<" not in script


def test_csp_names_no_idp_origin(spa_client: TestClient) -> None:
    """Ensure the browser may only connect to this origin, frame nothing."""
    csp = spa_client.get("/").headers["content-security-policy"]

    assert _directive(csp, "connect-src") == ["'self'"]
    assert _directive(csp, "frame-src") == ["'none'"]
    assert _directive(csp, "frame-ancestors") == ["'none'"]
    assert _directive(csp, "script-src") == ["'self'"]
    assert "idp.example.com" not in csp


def test_auth_routes_win_over_the_spa(spa_client: TestClient) -> None:
    """Ensure /auth/* backend routes are not shadowed by index.html."""
    session = spa_client.get("/auth/session")
    script = spa_client.get("/auth/landing.js")

    assert session.json() == {"authenticated": False}
    assert script.headers["content-type"].startswith("text/javascript")
    assert script.headers["content-security-policy"].startswith(
        "default-src 'self'"
    )


def test_security_headers_are_set_on_api_responses(
    spa_client: TestClient,
) -> None:
    """Ensure API responses also carry the security headers."""
    response = spa_client.get("/healthz")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert (
        response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    )
    assert (
        "frame-ancestors 'none'"
        in (response.headers["content-security-policy"])
    )


def test_api_docs_get_a_csp_allowing_their_cdn(
    spa_client: TestClient,
) -> None:
    """Ensure /api/docs is served with a CSP that admits Swagger UI."""
    response = spa_client.get("/api/docs")

    assert response.status_code == 200
    assert "swagger-ui" in response.text
    csp = response.headers["content-security-policy"]
    assert "https://cdn.jsdelivr.net" in _directive(csp, "script-src")
    assert _directive(csp, "frame-ancestors") == ["'none'"]


@pytest.mark.parametrize("path", ["/", "/records/central/adr-1", "/sources"])
def test_spa_routes_fall_back_to_index_html(
    spa_client: TestClient, path: str
) -> None:
    """Ensure deep links serve index.html."""
    response = spa_client.get(path)

    assert response.status_code == 200
    assert response.text == INDEX_HTML
    assert response.headers["cache-control"] == NO_CACHE


def test_head_on_a_deep_link_serves_index_headers(
    spa_client: TestClient,
) -> None:
    """Ensure HEAD on a deep link answers 200 like GET."""
    response = spa_client.head("/sources")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")


@pytest.mark.parametrize(
    "path",
    [
        "/api",
        "/api/unknown",
        "/api/v1/nope",
        "/auth/dev/nope",
        "/auth/nope",
        "/auth",
        "/healthz/extra",
        "/assets/missing.js",
    ],
)
def test_reserved_paths_never_fall_back_to_the_spa(
    spa_client: TestClient, path: str
) -> None:
    """Ensure unknown API-side paths stay JSON 404s."""
    response = spa_client.get(path)

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_unknown_path_with_post_is_a_json_404(
    spa_client: TestClient,
) -> None:
    """Ensure only GET/HEAD fall back to index.html."""
    response = spa_client.post("/records/x")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_wrong_method_on_an_api_route_stays_405(
    spa_client: TestClient,
) -> None:
    """Ensure the SPA fallback does not mask a 405 on a real route."""
    response = spa_client.post("/healthz")

    assert response.status_code == 405


def test_healthz_is_not_shadowed_by_the_spa(spa_client: TestClient) -> None:
    """Ensure /healthz still answers the JSON health report."""
    response = spa_client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_assets_are_cached_immutably(spa_client: TestClient) -> None:
    """Ensure hashed assets carry a one-year immutable cache."""
    response = spa_client.get(ASSET)

    assert response.status_code == 200
    assert response.text == "console.log(1);"
    assert response.headers["cache-control"] == IMMUTABLE


def test_top_level_files_are_served_as_is(spa_client: TestClient) -> None:
    """Ensure an existing top-level file is served, not index.html."""
    response = spa_client.get("/favicon.svg")

    assert response.status_code == 200
    assert response.text == "<svg/>"


@pytest.mark.parametrize(
    "path", ["/..%2fsecret.txt", "/assets/..%2f..%2fsecret.txt"]
)
def test_path_traversal_never_leaves_the_spa_dir(
    spa_client: TestClient, path: str
) -> None:
    """Ensure encoded ../ paths cannot read files outside the SPA."""
    response = spa_client.get(path)

    assert "outside the SPA" not in response.text


def test_without_static_dir_no_spa_routes_exist(client: TestClient) -> None:
    """Ensure an API-only app has no /config.js and no SPA fallback."""
    assert client.get("/config.js").status_code == 404
    assert client.get("/records/x").status_code == 404
    assert "content-security-policy" not in client.get("/healthz").headers


def test_static_dir_without_index_html_fails_startup(
    spa_settings: Settings, tmp_path: Path
) -> None:
    """Ensure a static dir without index.html stops the app factory."""
    empty = tmp_path / "empty"
    empty.mkdir()
    settings = spa_settings.model_copy(update={"static_dir": empty})

    with pytest.raises(ConfigurationError, match="index.html"):
        create_app(settings)
