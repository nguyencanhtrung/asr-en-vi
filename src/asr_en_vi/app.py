"""FastAPI application factory and protected-by-default request policy."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse, Response

from asr_en_vi.auth import AuthStateError, AuthStore, session_is_valid
from asr_en_vi.config import Settings
from asr_en_vi.routes import SESSION_COOKIE, install_routes
from asr_en_vi.storage import initialize

PUBLIC_ROUTES = frozenset(
    {
        ("GET", "/access"),
        ("GET", "/assets/access.css"),
        ("GET", "/assets/access.js"),
        ("GET", "/healthz"),
        ("HEAD", "/healthz"),
        ("POST", "/api/access/session"),
    }
)
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _normalized_origin(scheme: str, authority: str) -> tuple[str, str, int] | None:
    parsed = urlsplit(f"{scheme}://{authority}")
    if parsed.hostname is None or parsed.username or parsed.password:
        return None
    try:
        port = parsed.port
    except ValueError:
        return None
    if parsed.path or parsed.query or parsed.fragment:
        return None
    return (
        parsed.scheme.lower(),
        parsed.hostname.lower(),
        port or (443 if scheme == "https" else 80),
    )


def _host_is_expected(request: Request, settings: Settings) -> bool:
    host_header = request.headers.get("host", "")
    actual = _normalized_origin(urlsplit(settings.public_url).scheme, host_header)
    return actual == settings.origin


def _origin_is_expected(origin: str | None, settings: Settings) -> bool:
    if origin is None:
        return False
    parsed = urlsplit(origin)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        return False
    return _normalized_origin(parsed.scheme, parsed.netloc) == settings.origin


def _with_security_headers(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; img-src 'self' data:; style-src 'self'; "
        "script-src 'self'; connect-src 'self'; font-src 'self'; "
        "base-uri 'none'; form-action 'self'; frame-ancestors 'none'; object-src 'none'"
    )
    return response


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or Settings.from_env()
    auth_store = AuthStore(runtime_settings.auth_dir)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        previous_umask = os.umask(0o077)
        try:
            runtime_settings.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            runtime_settings.auth_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            auth_store.ensure()
            initialize(runtime_settings.data_dir)
            yield
        finally:
            os.umask(previous_umask)

    app = FastAPI(
        title="ASR EN VI",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.auth_store = auth_store
    app.state.settings = runtime_settings

    @app.middleware("http")
    async def protect_requests(request: Request, call_next) -> Response:
        method = request.method.upper()
        path = request.url.path
        if not _host_is_expected(request, runtime_settings):
            return _with_security_headers(PlainTextResponse("Invalid host", status_code=400))

        is_public = (method, path) in PUBLIC_ROUTES
        if method in UNSAFE_METHODS:
            if not _origin_is_expected(request.headers.get("origin"), runtime_settings):
                return _with_security_headers(
                    JSONResponse({"detail": "Same-origin request required"}, status_code=403)
                )
            if request.headers.get("sec-fetch-site", "").lower() == "cross-site":
                return _with_security_headers(
                    JSONResponse({"detail": "Same-origin request required"}, status_code=403)
                )

        if not is_public:
            try:
                state = auth_store.load()
            except AuthStateError:
                return _with_security_headers(
                    JSONResponse({"detail": "Authentication unavailable"}, status_code=503)
                )
            cookie_value = request.cookies.get(SESSION_COOKIE)
            if not session_is_valid(cookie_value, state):
                if method in {"GET", "HEAD"} and not path.startswith("/api/"):
                    return _with_security_headers(RedirectResponse("/access", status_code=303))
                return _with_security_headers(
                    JSONResponse({"detail": "Authentication required"}, status_code=401)
                )

        if is_public and path == "/api/access/session":
            content_type = request.headers.get("content-type", "").split(";", maxsplit=1)[0]
            if content_type.strip().lower() != "application/json":
                return _with_security_headers(
                    JSONResponse({"detail": "JSON body required"}, status_code=415)
                )

        response = await call_next(request)
        return _with_security_headers(response)

    install_routes(app, runtime_settings)
    return app


app = create_app()
