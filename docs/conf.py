"""Sphinx configuration for the Adriano documentation site."""

import os
import sys
import tomllib
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = DOCS_DIR.parent / "backend"

# Make ``app`` importable for autodoc.
sys.path.insert(0, str(BACKEND_DIR))

# Importing app modules must not need a database or real secrets, but
# ``app.main`` builds the application at import time and the settings
# require ADRIANO_DATABASE_URL. This placeholder DSN is never connected
# to: building the app and its OpenAPI document opens no connection.
os.environ.setdefault("ADRIANO_DEV_AUTH_ENABLED", "false")
os.environ.setdefault(
    "ADRIANO_DATABASE_URL", "postgresql://docs:docs@localhost/docs"
)

# -- OpenAPI spec -----------------------------------------------------

GENERATED_DIR = DOCS_DIR / "_generated"


def _write_openapi(_app):
    """Write the FastAPI app's OpenAPI document for ``http-api.rst``.

    The spec is rendered from the application at build time, so the
    HTTP reference can never drift from the code. (``frontend/openapi.json``
    is only refreshed when a developer runs ``npm run gen:types`` against
    a live backend, so it can lag behind.)
    """
    import json

    from app.main import app as fastapi_app

    GENERATED_DIR.mkdir(exist_ok=True)
    target = GENERATED_DIR / "openapi.json"
    target.write_text(
        json.dumps(fastapi_app.openapi(), indent=2) + "\n",
        encoding="utf-8",
    )


def setup(app):
    """Register the build-time hooks."""
    app.connect("builder-inited", _write_openapi)


# -- Project information ---------------------------------------------

with open(BACKEND_DIR / "pyproject.toml", "rb") as _f:
    _meta = tomllib.load(_f)

project = "Adriano"
author = "Michel Albert"
copyright = "Michel Albert"  # noqa: A001
release = _meta["project"]["version"]
version = ".".join(release.split(".")[:2])

# -- General ----------------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.intersphinx",
    "sphinx_autodoc_typehints",
    "sphinxcontrib.mermaid",
    "sphinxcontrib.openapi",
]

# _static/screenshots/INVENTORY.rst is a working list of screenshots for
# authors, not a page of the site.
exclude_patterns = [
    "_build",
    "_generated",
    "Thumbs.db",
    ".DS_Store",
    "_static/**/*.rst",
]

# Prefix section labels with the document path so identical headings on
# different pages do not collide: ``:ref:`user/searching:Filtering```.
autosectionlabel_prefix_document = True

autodoc_member_order = "bysource"
autodoc_default_options = {"show-inheritance": True}

# sphinx-autodoc-typehints cannot resolve guarded (TYPE_CHECKING-only)
# imports inside third-party packages (pydantic, SQLAlchemy, starlette)
# that surface when it inspects re-used names. Those are not ours.
suppress_warnings = [
    "sphinx_autodoc_typehints.forward_reference",
    "sphinx_autodoc_typehints.guarded_import",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# -- HTML output (furo) -----------------------------------------------

html_theme = "furo"
html_title = "Adriano"
html_logo = "_static/identity/adriano-mark.png"
html_favicon = "_static/identity/adriano-mark.png"
html_static_path = ["_static"]
html_css_files = ["custom.css"]

# Brand colours taken from the identity image (dark navy shield and
# lettering, warm grey inner shield line). Contrast against the furo
# page background (WCAG, text needs >= 4.5:1):
#   light: brand #1f3149 / links #2b4a73 on #ffffff -> 13.2 / 9.0
#   dark:  brand #8fb0dc / links #a9c3e6 on #131416 -> 8.3 / 10.2
html_theme_options = {
    "light_css_variables": {
        "color-brand-primary": "#1f3149",
        "color-brand-content": "#2b4a73",
        "color-foreground-secondary": "#5f5a52",
    },
    "dark_css_variables": {
        "color-brand-primary": "#8fb0dc",
        "color-brand-content": "#a9c3e6",
        "color-foreground-secondary": "#b3aca0",
    },
}

# -- Mermaid ----------------------------------------------------------

# Okabe-Ito colour-blind-safe palette as one site-wide mermaid theme.
# Node fills are light tints of the palette with near-black text and
# dark lines. Diagrams are drawn on a white panel (see custom.css), so
# the same theme is readable in furo's light and dark modes; both
# mermaid theme names therefore map to "base".
mermaid_version = "11"
mermaid_light_theme = "base"
mermaid_dark_theme = "base"
mermaid_init_config = {
    "startOnLoad": False,
    "themeVariables": {
        "primaryColor": "#cfe8f7",
        "primaryBorderColor": "#0072B2",
        "primaryTextColor": "#111111",
        "secondaryColor": "#fbe3b0",
        "secondaryBorderColor": "#E69F00",
        "secondaryTextColor": "#111111",
        "tertiaryColor": "#b5e6d6",
        "tertiaryBorderColor": "#009E73",
        "tertiaryTextColor": "#111111",
        "noteBkgColor": "#f7f3b5",
        "noteBorderColor": "#8a7f00",
        "noteTextColor": "#111111",
        "lineColor": "#333333",
        "textColor": "#111111",
        "edgeLabelBackground": "#ffffff",
        "clusterBkg": "#f4f4f4",
        "clusterBorder": "#333333",
        "titleColor": "#111111",
    },
}
