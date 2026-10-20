from __future__ import annotations

import threading
import time

import pytest
from fake_chatgpt import FakeChatGPTAdapter
from httpx import ASGITransport, AsyncClient

from asr_en_vi.antigravity import ANTIGRAVITY_PROVIDER_ID, LoginInteraction
from asr_en_vi.app import create_app

pytestmark = pytest.mark.anyio


class RouteAntigravityAdapter:
    def __init__(self) -> None:
        self.release = threading.Event()
        self.verify_calls: list[str] = []

    def login(self, interaction: LoginInteraction) -> None:
        interaction.publish(
            {
                "authorization_url": "https://accounts.google.com/o/oauth2/auth?state=route",
                "instructions": "Continue with Google.",
            }
        )
        while not self.release.wait(0.01):
            if interaction.cancel_event.is_set():
                return

    def list_models(self):
        return [
            {
                "provider": ANTIGRAVITY_PROVIDER_ID,
                "id": "gemini-3-pro-high",
                "name": "Gemini 3 Pro High",
            }
        ]

    def verify(self, model: str):
        self.verify_calls.append(model)
        return {"ok": True}

    def logout(self):
        return True


async def authenticate(client, settings, app):
    state = app.state.auth_store.load()
    return await client.post(
        "/api/access/session",
        headers={"Origin": settings.public_url},
        json={"token": state.token},
    )


async def test_antigravity_connection_routes_cover_login_catalog_verify_and_disconnect(settings):
    adapter = RouteAntigravityAdapter()
    app = create_app(
        settings,
        chatgpt_adapter=FakeChatGPTAdapter(),
        antigravity_adapter=adapter,
    )
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url=settings.public_url) as client,
    ):
        assert (await client.get("/api/providers/antigravity/models")).status_code == 401
        await authenticate(client, settings, app)
        started = await client.post(
            "/api/providers/antigravity/login-sessions",
            headers={"Origin": settings.public_url},
            json={},
        )
        assert started.status_code == 201
        assert started.json()["authorization_url"].startswith("https://accounts.google.com/")
        session_id = started.json()["id"]
        adapter.release.set()
        deadline = time.monotonic() + 2
        while True:
            login = await client.get(f"/api/providers/antigravity/login-sessions/{session_id}")
            if login.json()["status"] == "connected":
                break
            assert time.monotonic() < deadline
            await __import__("asyncio").sleep(0.01)

        providers = (await client.get("/api/providers")).json()["providers"]
        antigravity = next(item for item in providers if item["id"] == "antigravity")
        assert antigravity["status"] == "connected"
        assert antigravity["account"] == {"label": "Google Antigravity"}

        catalog = await client.get("/api/providers/antigravity/models")
        assert catalog.json()["models"] == [
            {"id": "gemini-3-pro-high", "display_name": "Gemini 3 Pro High"}
        ]
        preference = await client.put(
            "/api/providers/antigravity/preference",
            headers={"Origin": settings.public_url},
            json={"model": "gemini-3-pro-high"},
        )
        assert preference.json() == {
            "provider": "antigravity",
            "model": "gemini-3-pro-high",
        }
        verified = await client.post(
            "/api/providers/antigravity/verify",
            headers={"Origin": settings.public_url},
            json={"model": "gemini-3-pro-high"},
        )
        assert verified.status_code == 200
        assert verified.json()["output"] == {"ok": True}
        assert adapter.verify_calls == ["gemini-3-pro-high"]

        disconnected = await client.delete(
            "/api/providers/antigravity/connection",
            headers={"Origin": settings.public_url},
        )
        assert disconnected.json()["status"] == "disconnected"
