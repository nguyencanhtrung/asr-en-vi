from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from asr_en_vi.app import create_app
from asr_en_vi.config import Settings


@pytest.fixture
def settings(tmp_path):
    return Settings(
        data_dir=tmp_path / "data",
        auth_dir=tmp_path / "auth",
        public_url="http://127.0.0.1:8765",
    )


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client(settings):
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url=settings.public_url) as test_client:
            yield test_client
