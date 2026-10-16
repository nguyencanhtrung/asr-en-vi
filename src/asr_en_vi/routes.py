"""HTTP routes for access, liveness, and the authenticated empty workspace."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse

from asr_en_vi.auth import AuthStateError, create_session_cookie, token_matches
from asr_en_vi.config import Settings

SESSION_COOKIE = "asr_en_vi_session"
WEB_DIR = Path(__file__).parent / "web"


def _asset_response(filename: str, media_type: str) -> FileResponse:
    return FileResponse(WEB_DIR / filename, media_type=media_type)


def install_routes(app: FastAPI, settings: Settings) -> None:
    @app.api_route("/healthz", methods=["GET", "HEAD"], include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/access", include_in_schema=False)
    async def access_page() -> FileResponse:
        return _asset_response("access.html", "text/html")

    @app.get("/assets/access.css", include_in_schema=False)
    async def access_css() -> FileResponse:
        return _asset_response("access.css", "text/css")

    @app.get("/assets/access.js", include_in_schema=False)
    async def access_js() -> FileResponse:
        return _asset_response("access.js", "text/javascript")

    @app.get("/", include_in_schema=False)
    async def workspace() -> FileResponse:
        return _asset_response("shell.html", "text/html")

    @app.get("/assets/shell.css", include_in_schema=False)
    async def shell_css() -> FileResponse:
        return _asset_response("shell.css", "text/css")

    @app.post("/api/access/session", status_code=204, include_in_schema=False)
    async def create_access_session(
        request: Request,
        response: Response,
    ) -> Response:
        try:
            payload = await request.json()
        except (UnicodeDecodeError, ValueError):
            raise HTTPException(status_code=400, detail="Invalid access request") from None
        if (
            not isinstance(payload, dict)
            or set(payload) != {"token"}
            or not isinstance(payload["token"], str)
            or not 40 <= len(payload["token"]) <= 512
        ):
            raise HTTPException(status_code=400, detail="Invalid access request")

        try:
            state = request.app.state.auth_store.load()
        except AuthStateError:
            raise HTTPException(status_code=503, detail="Authentication unavailable") from None
        if not token_matches(payload["token"], state.token):
            raise HTTPException(status_code=401, detail="Token không hợp lệ")

        response.set_cookie(
            key=SESSION_COOKIE,
            value=create_session_cookie(state),
            httponly=True,
            secure=settings.cookie_secure,
            samesite="strict",
            path="/",
        )
        response.status_code = 204
        return response
