from __future__ import annotations

import json

import pytest

from asr_en_vi.auth import AuthStore

pytestmark = pytest.mark.anyio


async def test_access_page_is_minimal_and_security_headers_are_set(client):
    response = await client.get("/access")

    assert response.status_code == 200
    assert "ASR EN VI" in response.text
    assert "demo-local" not in response.text
    assert "Cache-Control" in response.headers
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert "media-src 'self'" in response.headers["Content-Security-Policy"]


async def test_fragment_token_exchange_sets_generation_bound_cookie(client, settings):
    state = AuthStore(settings.auth_dir).load()
    response = await client.post(
        "/api/access/session",
        headers={"Origin": settings.public_url},
        json={"token": state.token},
    )

    assert response.status_code == 204
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/" in cookie
    assert "Secure" not in cookie
    assert "Max-Age" not in cookie
    assert "Expires" not in cookie
    assert "Domain" not in cookie
    assert (await client.get("/")).status_code == 200
    assert (await client.get("/assets/shell.css")).status_code == 200


async def test_invalid_token_and_invalid_request_never_echo_submitted_value(client):
    invalid_token = "definitely-not-a-token-" + "x" * 43
    response = await client.post(
        "/api/access/session",
        headers={"Origin": "http://127.0.0.1:8765"},
        json={"token": invalid_token},
    )
    too_long = "secret-value-" * 100
    invalid_shape = await client.post(
        "/api/access/session",
        headers={"Origin": "http://127.0.0.1:8765"},
        json={"token": too_long},
    )

    assert response.status_code == 401
    assert invalid_token not in response.text
    assert response.headers.get("set-cookie") is None
    assert invalid_shape.status_code == 400
    assert too_long not in invalid_shape.text


async def test_same_origin_and_host_checks_reject_cross_site_requests(client):
    cross_origin = await client.post(
        "/api/access/session",
        headers={"Origin": "http://evil.example"},
        json={"token": "x" * 43},
    )
    pathful_origin = await client.post(
        "/api/access/session",
        headers={"Origin": "http://127.0.0.1:8765/other"},
        json={"token": "x" * 43},
    )
    wrong_host = await client.get("/access", headers={"Host": "evil.example"})

    assert cross_origin.status_code == 403
    assert pathful_origin.status_code == 403
    assert wrong_host.status_code == 400


async def test_unsafe_requests_require_origin_fetch_metadata_and_auth(client, settings):
    no_origin = await client.post("/api/meetings")
    null_origin = await client.post("/api/meetings", headers={"Origin": "null"})
    cross_site = await client.post(
        "/api/meetings",
        headers={"Origin": settings.public_url, "Sec-Fetch-Site": "cross-site"},
    )
    unauthenticated = await client.post(
        "/api/meetings",
        headers={"Origin": settings.public_url, "Sec-Fetch-Site": "same-origin"},
    )

    assert no_origin.status_code == 403
    assert null_origin.status_code == 403
    assert cross_site.status_code == 403
    assert unauthenticated.status_code == 401


async def test_protected_by_default_paths_deny_missing_and_invalid_auth(client):
    protected_paths = [
        "/api/meetings",
        "/api/meetings/meeting-1/audio",
        "/api/uploads/policy",
        "/api/uploads/upload-1",
        "/api/uploads/upload-1/content",
        "/meetings/meeting-1",
        "/api/notes/note-1/export",
        "/recordings/private.wav",
        "/assets/shell.css",
        "/assets/shell.js",
        "/assets/history.css",
        "/assets/history.js",
    ]

    for path in protected_paths:
        response = await client.get(path)
        assert response.status_code in {401, 303}, (path, response.status_code)
        assert "meeting" not in response.text.lower()

    client.cookies.set("asr_en_vi_session", "not-a-session")
    bad_cookie = await client.get("/api/meetings")
    assert bad_cookie.status_code == 401
    assert "meeting" not in bad_cookie.text.lower()


async def test_liveness_is_public_and_does_not_reveal_auth_state(client, settings):
    response = await client.get("/healthz")
    head_response = await client.head("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert head_response.status_code == 200
    assert head_response.content == b""
    assert AuthStore(settings.auth_dir).load().token not in response.text


async def test_missing_auth_state_fails_closed_without_issuing_a_replacement(client, settings):
    store = AuthStore(settings.auth_dir)
    original = store.load()
    exchange = await client.post(
        "/api/access/session",
        headers={"Origin": settings.public_url},
        json={"token": original.token},
    )
    assert exchange.status_code == 204

    store.state_path.unlink()
    response = await client.get("/")
    exchange_after_loss = await client.post(
        "/api/access/session",
        headers={"Origin": settings.public_url},
        json={"token": original.token},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication unavailable"}
    assert exchange_after_loss.status_code == 503
    assert exchange_after_loss.json() == {"detail": "Authentication unavailable"}
    assert not store.state_path.exists()


async def test_exchange_does_not_log_token_or_include_it_in_errors(client, settings, caplog):
    token = AuthStore(settings.auth_dir).load().token
    response = await client.post(
        "/api/access/session",
        headers={"Origin": settings.public_url, "Content-Type": "application/json"},
        content=json.dumps({"token": "bad-" + token}),
    )

    assert response.status_code == 401
    assert token not in caplog.text
