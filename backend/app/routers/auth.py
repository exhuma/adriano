"""
Sign-in, session check and sign-out (Backend-for-Frontend).

Routes (outside ``/api``; they take precedence over the SPA fallback):

- ``GET /auth/login?return_to=<path>`` -- start an OIDC sign-in: 302
  to the IdP's authorization endpoint. ``return_to`` must be a
  same-site relative path, otherwise ``/``. 404 without OIDC.
- ``GET /auth/callback?code&state`` -- complete it: on success an HTML
  landing page that sets the session cookie and continues (through
  ``/auth/landing.js``) at the return path; on any failure an HTML
  error page with status 400 and no session.
- ``GET /auth/landing.js`` -- the landing page's script.
- ``GET /auth/session`` -- always 200: ``{"authenticated": true,
  "expires_at": ...}`` or ``{"authenticated": false}``. Never refreshes
  tokens; needs no CSRF header.
- ``POST /auth/logout`` -- CSRF header required. Deletes the session,
  clears the cookie, revokes the refresh token (best effort) and
  returns ``{"end_session_url": <IdP logout URL or null>}``.

The redirect and post-logout URIs are built from the request's own
origin (:func:`app.auth.csrf.request_origin`): ``<origin>/auth/callback``
and ``<origin>/``.

Public API: :data:`router`.
"""

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth.cookies import (
    LOGIN_COOKIE,
    SESSION_COOKIE,
    clear_login_cookie,
    clear_session_cookie,
    read_cookie,
    set_login_cookie,
    set_session_cookie,
)
from app.auth.csrf import request_origin, require_csrf
from app.auth.deps import get_idp_client, get_login_service, get_session_service
from app.auth.idp import IdpClient
from app.auth.pages import LANDING_JS, error_page, landing_page
from app.schemas.auth import LogoutOut, SessionOut
from app.services.auth_sessions import SessionService
from app.services.oidc_login import (
    LoginFailedError,
    LoginService,
    end_session,
    safe_return_to,
)

router = APIRouter(prefix="/auth", tags=["auth"])

#: Callback pages hold a one-time result; never cache or leak them.
_PRIVATE = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}


@router.get(
    "/login",
    response_class=RedirectResponse,
    status_code=302,
    responses={404: {"description": "OIDC is not configured"}},
)
def login(
    request: Request,
    return_to: str | None = Query(default=None),
    service: LoginService = Depends(get_login_service),
) -> Response:
    """
    Start an OIDC sign-in.

    :param request: The request (its origin builds the redirect URI).
    :param return_to: Relative path to continue at after sign-in.
    :param service: The sign-in flow.
    :returns: A 302 to the IdP that sets the sign-in binding cookie.
    """
    start = service.begin(
        return_to=safe_return_to(return_to),
        redirect_uri=f"{request_origin(request)}/auth/callback",
    )
    response = RedirectResponse(start.authorize_url, status_code=302)
    response.headers["Cache-Control"] = "no-store"
    set_login_cookie(response, start.state)
    return response


@router.get(
    "/callback",
    response_class=HTMLResponse,
    responses={400: {"description": "The sign-in failed (HTML page)"}},
)
def callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    service: LoginService = Depends(get_login_service),
) -> Response:
    """
    Complete an OIDC sign-in.

    :param request: The request (sign-in binding cookie).
    :param code: Authorization code.
    :param state: Sign-in state.
    :param error: Error code of a refused authorization.
    :param service: The sign-in flow.
    :returns: The landing page with the session cookie, or the error
        page (status 400).
    """
    try:
        done = service.complete(
            code=code,
            state=state,
            bound_state=read_cookie(request, LOGIN_COOKIE),
            error=error,
        )
    except LoginFailedError as exc:
        response = HTMLResponse(
            error_page(exc.message), status_code=400, headers=_PRIVATE
        )
    else:
        response = HTMLResponse(landing_page(done.return_to), headers=_PRIVATE)
        set_session_cookie(response, done.cookie)
    clear_login_cookie(response)
    return response


@router.get("/landing.js", response_class=Response)
def landing_script() -> Response:
    """
    Serve the landing page's script.

    :returns: The script.
    """
    return Response(
        LANDING_JS,
        media_type="text/javascript; charset=utf-8",
        headers={"Cache-Control": "no-cache"},
    )


@router.get(
    "/session", response_model=SessionOut, response_model_exclude_none=True
)
def session_status(
    request: Request,
    sessions: SessionService | None = Depends(get_session_service),
) -> SessionOut:
    """
    Tell the SPA whether it has a usable session.

    :param request: The request (session cookie).
    :param sessions: The session service.
    :returns: The session state.
    """
    cookie = read_cookie(request, SESSION_COOKIE)
    active = None
    if cookie is not None and sessions is not None:
        active = sessions.peek(cookie)
    if active is None:
        return SessionOut(authenticated=False)
    return SessionOut(authenticated=True, expires_at=active.expires_at)


@router.post(
    "/logout",
    response_model=LogoutOut,
    dependencies=[Depends(require_csrf)],
    responses={403: {"description": "CSRF check failed (csrf_failed)"}},
)
def logout(
    request: Request,
    response: Response,
    sessions: SessionService | None = Depends(get_session_service),
    idp: IdpClient | None = Depends(get_idp_client),
) -> LogoutOut:
    """
    Sign out.

    :param request: The request (session cookie, origin).
    :param response: The response (clears the cookie).
    :param sessions: The session service.
    :param idp: The OIDC client, if configured.
    :returns: The IdP's end-session URL, or ``null``.
    """
    url = end_session(
        sessions,
        idp,
        read_cookie(request, SESSION_COOKIE),
        post_logout_redirect_uri=f"{request_origin(request)}/",
    )
    clear_session_cookie(response)
    response.headers["Cache-Control"] = "no-store"
    return LogoutOut(end_session_url=url)
