"""
The small HTML pages and the script of the sign-in callback.

The session cookie is ``SameSite=Strict``, so the browser does not send
it on the navigation chain that started at the IdP. The callback
therefore answers a same-origin landing page instead of a redirect; its
external script (:data:`LANDING_JS`, served as ``/auth/landing.js``
under CSP ``script-src 'self'``) reads the return path from the
``data-return-to`` attribute and calls ``location.replace``, which
starts a fresh same-site navigation that carries the cookie.

All interpolated values are HTML-escaped.

Public API: :data:`LANDING_JS`, :func:`landing_page`, :func:`error_page`.
"""

from html import escape

__all__ = ["LANDING_JS", "error_page", "landing_page"]

#: ``/auth/landing.js``: continue at the validated return path.
LANDING_JS = """\
"use strict";
(function () {
  var target = document.body.getAttribute("data-return-to") || "/";
  if (target.charAt(0) !== "/" || target.charAt(1) === "/" ||
      target.indexOf("\\\\") !== -1) {
    target = "/";
  }
  window.location.replace(target);
})();
"""


def landing_page(return_to: str) -> str:
    """
    Render the page that continues to the app after sign-in.

    :param return_to: Validated relative return path.
    :returns: The HTML document.
    """
    target = escape(return_to, quote=True)
    return (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        "<title>Signing in - Adriano</title>"
        '<script src="/auth/landing.js" defer></script></head>'
        f'<body data-return-to="{target}">'
        f'<p>Signed in. <a href="{target}">Continue</a></p>'
        "</body></html>\n"
    )


def error_page(message: str) -> str:
    """
    Render the page of a failed sign-in.

    :param message: Readable reason (no secrets).
    :returns: The HTML document.
    """
    return (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        "<title>Sign-in failed - Adriano</title></head><body>"
        "<h1>Sign-in failed</h1>"
        f"<p>{escape(message)}</p>"
        '<p><a href="/">Back to Adriano</a></p>'
        "</body></html>\n"
    )
