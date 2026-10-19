from __future__ import annotations

import base64
import json
import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from asr_en_vi.chatgpt import (
    API_BASE_URL,
    AUTHORIZATION_URL,
    DISCOVERY_URL,
    ISSUER,
    TOKEN_URL,
    ChatGPTError,
    ChatGPTHTTPAdapter,
)

CLIENT_ID = "oaiapp_test-123456"


class SlowByteStream(httpx.SyncByteStream):
    def __init__(self, chunks: list[bytes], *, delay: float) -> None:
        self.chunks = chunks
        self.delay = delay

    def __iter__(self):
        for chunk in self.chunks:
            time.sleep(self.delay)
            yield chunk


class TerminalThenExtraStream(httpx.SyncByteStream):
    def __init__(self, terminal_event: bytes) -> None:
        self.terminal_event = terminal_event
        self.read_after_terminal = False

    def __iter__(self):
        yield self.terminal_event
        self.read_after_terminal = True
        yield b": keep-alive after terminal event\n\n"


def _base64url_integer(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _identity_transport():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private_key.public_key().public_numbers()
    jwks = {
        "keys": [
            {
                "kty": "RSA",
                "kid": "unit-test-key",
                "use": "sig",
                "alg": "RS256",
                "n": _base64url_integer(numbers.n),
                "e": _base64url_integer(numbers.e),
            }
        ]
    }
    discovery = {
        "issuer": ISSUER,
        "authorization_endpoint": AUTHORIZATION_URL,
        "token_endpoint": TOKEN_URL,
        "jwks_uri": "https://auth.openai.com/.well-known/jwks.json",
        "revocation_endpoint": "https://auth.openai.com/api/accounts/oauth/revoke",
        "id_token_signing_alg_values_supported": ["RS256"],
    }
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if str(request.url) == DISCOVERY_URL:
            return httpx.Response(200, json=discovery)
        if str(request.url) == discovery["jwks_uri"]:
            return httpx.Response(200, json=jwks)
        raise AssertionError(f"Unexpected provider URL: {request.url}")

    return private_key, requests, httpx.MockTransport(handler)


def _signed_id_token(private_key, *, audience=CLIENT_ID, nonce="expected-nonce", headers=None):
    now = int(time.time())
    return jwt.encode(
        {
            "iss": ISSUER,
            "aud": audience,
            "sub": "verified-subject",
            "iat": now,
            "exp": now + 300,
            "nonce": nonce,
            "email": "verified@example.test",
            "email_verified": True,
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "unit-test-key", **(headers or {})},
    )


def test_identity_token_requires_trusted_signature_issuer_audience_and_nonce():
    private_key, requests, transport = _identity_transport()
    adapter = ChatGPTHTTPAdapter(transport=transport)

    identity = adapter.validate_identity(
        _signed_id_token(private_key), client_id=CLIENT_ID, nonce="expected-nonce"
    )

    assert identity.subject == "verified-subject"
    assert identity.email == "verified@example.test"
    assert identity.email_verified
    assert [str(request.url) for request in requests] == [
        DISCOVERY_URL,
        "https://auth.openai.com/.well-known/jwks.json",
    ]

    with pytest.raises(ChatGPTError) as wrong_nonce:
        adapter.validate_identity(
            _signed_id_token(private_key), client_id=CLIENT_ID, nonce="different-nonce"
        )
    assert wrong_nonce.value.code == "invalid_identity_token"
    with pytest.raises(ChatGPTError) as wrong_audience:
        adapter.validate_identity(
            _signed_id_token(private_key, audience="another-client"),
            client_id=CLIENT_ID,
            nonce="expected-nonce",
        )
    assert wrong_audience.value.code == "invalid_identity_token"


def test_identity_token_rejects_untrusted_jku_without_fetching_it():
    private_key, requests, transport = _identity_transport()
    adapter = ChatGPTHTTPAdapter(transport=transport)

    with pytest.raises(ChatGPTError) as untrusted_key_url:
        adapter.validate_identity(
            _signed_id_token(private_key, headers={"jku": "https://attacker.example/jwks"}),
            client_id=CLIENT_ID,
            nonce="expected-nonce",
        )

    assert untrusted_key_url.value.code == "invalid_identity_token"
    assert requests == []


def test_verification_sends_one_synthetic_strict_sse_request_and_requires_completion():
    requests: list[httpx.Request] = []
    stream = (
        b'event: response.output_text.delta\ndata: {"type":"response.output_text.delta",'
        b'"delta":"{\\"ok\\":true}"}\n\n'
        b'event: response.completed\ndata: {"type":"response.completed",'
        b'"response":{"output":[]}}\n\n'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=stream,
        )

    adapter = ChatGPTHTTPAdapter(transport=httpx.MockTransport(handler))
    adapter.verify(access_token="access-secret", model="gpt-6.1-sol")

    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == f"{API_BASE_URL}/responses"
    assert request.headers["authorization"] == "Bearer access-secret"
    body = json.loads(request.content)
    assert set(body) == {"model", "input", "text", "store", "stream"}
    assert body["model"] == "gpt-6.1-sol"
    assert body["store"] is False and body["stream"] is True
    assert body["input"] == [
        {
            "role": "user",
            "content": [{"type": "input_text", "text": 'Return exactly {"ok":true}.'}],
        }
    ]
    assert body["text"]["format"]["strict"] is True
    assert body["text"]["format"]["schema"] == {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
        "additionalProperties": False,
    }


def test_verification_sends_selected_reasoning_effort():
    requests: list[httpx.Request] = []
    stream = (
        b'data: {"type":"response.output_text.delta","delta":"{\\"ok\\":true}"}\n\n'
        b'data: {"type":"response.completed","response":{"output":[]}}\n\n'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=stream)

    adapter = ChatGPTHTTPAdapter(transport=httpx.MockTransport(handler))
    adapter.verify(access_token="test-token", model="gpt-5.6-luna", reasoning_effort="max")

    assert len(requests) == 1
    body = json.loads(requests[0].content)
    assert body["reasoning"] == {"effort": "max"}
    assert body["store"] is False and body["stream"] is True


def test_verification_accepts_valid_sse_without_content_type():
    stream = (
        b"data: "
        + json.dumps({"type": "response.output_text.delta", "delta": '{"ok":true}'}).encode("utf-8")
        + b"\n\n"
        + b"data: "
        + json.dumps({"type": "response.completed", "response": {"output": []}}).encode("utf-8")
        + b"\n\n"
    )
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        response = httpx.Response(200, content=stream)
        assert "content-type" not in response.headers
        return response

    adapter = ChatGPTHTTPAdapter(transport=httpx.MockTransport(handler))
    adapter.verify(access_token="access-secret", model="gpt-6.1-sol")

    assert calls == 1


@pytest.mark.parametrize("content_type", ["application/json", "text/plain", ""])
def test_verification_rejects_explicit_non_sse_content_type(content_type):
    stream = (
        b'data: {"type":"response.completed","response":{"output":[{"type":"message",'
        b'"content":[{"type":"output_text","text":"{\\"ok\\":true}"}]}]}}\n\n'
    )
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        response = httpx.Response(
            200,
            headers={"content-type": content_type},
            content=stream,
        )
        assert "content-type" in response.headers
        return response

    adapter = ChatGPTHTTPAdapter(transport=httpx.MockTransport(handler))
    with pytest.raises(ChatGPTError) as rejected:
        adapter.verify(access_token="access-secret", model="gpt-6.1-sol")

    assert rejected.value.code == "provider_invalid_stream"
    assert calls == 1


@pytest.mark.parametrize(
    "body,expected_code",
    [
        (b"", "verification_incomplete"),
        (b'{"ok":true}', "verification_incomplete"),
        (b"<!doctype html><html><body>error</body></html>", "verification_incomplete"),
        (b"data: {invalid-json}\n\n", "provider_invalid_stream"),
        (
            b'data: {"type":"response.output_text.delta","delta":"{\\"ok\\":true}"}\n\n',
            "verification_incomplete",
        ),
        (
            (
                "data: "
                + json.dumps(
                    {
                        "type": "response.completed",
                        "response": {
                            "output": [
                                {
                                    "type": "message",
                                    "content": [
                                        {
                                            "type": "output_text",
                                            "text": '{"ok":true,"extra":false}',
                                        }
                                    ],
                                }
                            ]
                        },
                    }
                )
                + "\n\n"
            ).encode("utf-8"),
            "verification_invalid_output",
        ),
    ],
)
def test_headerless_verification_requires_valid_complete_exact_output(body, expected_code):
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        response = httpx.Response(200, content=body)
        assert "content-type" not in response.headers
        return response

    adapter = ChatGPTHTTPAdapter(transport=httpx.MockTransport(handler))
    with pytest.raises(ChatGPTError) as rejected:
        adapter.verify(access_token="access-secret", model="gpt-6.1-sol")

    assert rejected.value.code == expected_code
    assert calls == 1


def test_json_body_has_a_monotonic_total_deadline(monkeypatch):
    total_timeout = 0.05
    read_timeout = 0.04
    monkeypatch.setattr(
        "asr_en_vi.chatgpt.HTTP_TOTAL_TIMEOUT_SECONDS", total_timeout, raising=False
    )
    monkeypatch.setattr("asr_en_vi.chatgpt.HTTP_READ_TIMEOUT_SECONDS", read_timeout, raising=False)
    slow_stream = SlowByteStream([b" "] * 8, delay=read_timeout)
    adapter = ChatGPTHTTPAdapter(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=slow_stream))
    )

    started = time.monotonic()
    with adapter._client() as client, pytest.raises(ChatGPTError) as timed_out:
        adapter._json_request(client, "GET", f"{API_BASE_URL}/models")
    elapsed = time.monotonic() - started

    assert timed_out.value.code == "provider_timeout"
    assert total_timeout <= elapsed <= total_timeout + read_timeout + 0.05


def test_verification_sse_has_a_monotonic_total_deadline(monkeypatch):
    total_timeout = 0.05
    read_timeout = 0.04
    monkeypatch.setattr(
        "asr_en_vi.chatgpt.HTTP_TOTAL_TIMEOUT_SECONDS", total_timeout, raising=False
    )
    monkeypatch.setattr("asr_en_vi.chatgpt.HTTP_READ_TIMEOUT_SECONDS", read_timeout, raising=False)
    slow_stream = SlowByteStream([b": keep-alive\n\n"] * 8, delay=read_timeout)
    adapter = ChatGPTHTTPAdapter(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                stream=slow_stream,
            )
        )
    )

    started = time.monotonic()
    with pytest.raises(ChatGPTError) as timed_out:
        adapter.verify(access_token="access-secret", model="gpt-6.1-sol")
    elapsed = time.monotonic() - started

    assert timed_out.value.code == "provider_timeout"
    assert total_timeout <= elapsed <= total_timeout + read_timeout + 0.05


def test_verification_stops_reading_at_response_completed():
    terminal = (
        b'data: {"type":"response.completed","response":{"output":[{"type":"message",'
        b'"content":[{"type":"output_text","text":"{\\"ok\\":true}"}]}]}}\n\n'
    )
    stream = TerminalThenExtraStream(terminal)
    adapter = ChatGPTHTTPAdapter(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                stream=stream,
            )
        )
    )

    adapter.verify(access_token="access-secret", model="gpt-6.1-sol")

    assert stream.read_after_terminal is False


@pytest.mark.parametrize(
    "events,expected_code,expected_status",
    [
        (
            'data: {"type":"response.failed","response":{"error":'
            '{"code":"subscription_sharing_usage_limit_exceeded"}}}\n\n',
            "subscription_sharing_usage_limit_exceeded",
            429,
        ),
        (
            'data: {"type":"response.completed","response":{"output":[]}}\n\n',
            "verification_invalid_output",
            502,
        ),
        ('data: {"type":"response.incomplete"}\n\n', "verification_incomplete", 502),
        (
            'data: {"type":"response.output_text.delta","delta":"{\\"ok\\":true}"}\n\n',
            "verification_incomplete",
            502,
        ),
    ],
)
def test_verification_errors_are_provider_specific_and_never_retried(
    events, expected_code, expected_status
):
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=events.encode("utf-8"),
        )

    adapter = ChatGPTHTTPAdapter(transport=httpx.MockTransport(handler))
    with pytest.raises(ChatGPTError) as failed:
        adapter.verify(access_token="access-secret", model="gpt-6.1-sol")

    assert failed.value.code == expected_code
    assert failed.value.status_code == expected_status
    assert calls == 1


def test_provider_401_is_mapped_to_non_401_with_its_code():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"error": {"code": "subscription_sharing_invalid_user"}},
        )

    adapter = ChatGPTHTTPAdapter(transport=httpx.MockTransport(handler))
    with adapter._client() as client, pytest.raises(ChatGPTError) as rejected:
        adapter._json_request(
            client,
            "GET",
            f"{API_BASE_URL}/models",
            headers={"Authorization": "Bearer access-secret"},
        )

    assert rejected.value.status_code == 409
    assert rejected.value.code == "subscription_sharing_invalid_user"
    assert "access-secret" not in rejected.value.message


def test_failed_stream_retains_safe_request_and_parameter_diagnostics():
    event = {
        "type": "response.failed",
        "response": {
            "error": {
                "code": "subscription_sharing_unsupported_capability",
                "param": "text.format",
                "message": "private raw provider detail",
            }
        },
    }
    adapter = ChatGPTHTTPAdapter(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                content="data: " + json.dumps(event) + "\n\n",
                headers={"Content-Type": "text/event-stream", "x-request-id": "req_stream123"},
            )
        )
    )
    with pytest.raises(ChatGPTError) as failure:
        adapter.verify(access_token="test-token", model="test-model")
    assert failure.value.diagnostics == {
        "body_shape": "error",
        "http_status": 200,
        "request_id": "req_stream123",
        "param": "text.format",
    }
    assert "private" not in str(failure.value)
    assert "private" not in json.dumps(failure.value.diagnostics)


@pytest.mark.parametrize(
    "override",
    [
        {"id_token_signing_alg_values_supported": None},
        {"revocation_endpoint": "https://auth.openai.com:invalid/revoke"},
        {"jwks_uri": "https://[invalid"},
    ],
)
def test_malformed_discovery_is_a_safe_provider_error(override):
    document = {
        "issuer": ISSUER,
        "authorization_endpoint": AUTHORIZATION_URL,
        "token_endpoint": TOKEN_URL,
        "jwks_uri": "https://auth.openai.com/jwks",
        "revocation_endpoint": "https://auth.openai.com/revoke",
        "id_token_signing_alg_values_supported": ["RS256"],
        **override,
    }
    adapter = ChatGPTHTTPAdapter(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=document))
    )
    with pytest.raises(ChatGPTError) as failure:
        adapter.revoke(client_id=CLIENT_ID, refresh_token="test-refresh")
    assert failure.value.code == "provider_discovery_invalid"
