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
    "michel_albert_sphinx",
    "sphinx_immaterial.mermaid_diagrams",
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

# -- HTML output (michel-albert-design) -------------------------------

html_title = "Adriano"
html_logo = "_static/identity/adriano-mark.png"
html_favicon = "_static/identity/adriano-mark.png"
html_static_path = ["_static"]

# Non-visual theme options only; the design system owns the looks.
html_theme_options = {
    "repo_url": "https://github.com/exhuma/adriano",
    "repo_name": "exhuma/adriano",
    "edit_uri": "blob/master/docs",
    "features": [
        "content.code.copy",
        "navigation.top",
        "toc.follow",
    ],
}

# Backdrop style: "facets" (architecture viewpoints, structure) suits a
# catalog of architecture decisions.
michel_albert_backdrop_style = "facets"

# -- Mermaid ----------------------------------------------------------

# sphinx_immaterial.mermaid_diagrams ships mermaid with the site (no CDN)
# and colours diagrams from the theme, so they follow light and dark mode.
