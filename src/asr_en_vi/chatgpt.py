"""Direct Sign in with ChatGPT, protected credentials and controlled verification."""

from __future__ import annotations

import base64
import fcntl
import hashlib
import hmac
import json
import os
import re
import secrets
import stat
import tempfile
import threading
import time
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlencode, urlsplit

import httpx
import jwt

ISSUER = "https://auth.openai.com"
DISCOVERY_URL = f"{ISSUER}/.well-known/openid-configuration"
AUTHORIZATION_URL = f"{ISSUER}/api/accounts/authorize"
TOKEN_URL = f"{ISSUER}/api/accounts/oauth/token"
API_BASE_URL = "https://api.openai.com/v1"
RESOURCE = API_BASE_URL
DIRECT_SCOPE = "chatgpt.tokens.use.direct"
REQUESTED_SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
DYNAMIC_CLIENT_ID = "dynamic_agent_client"
SESSION_TTL_SECONDS = 10 * 60
ACCESS_REFRESH_MARGIN_SECONDS = 60
MAX_PROVIDER_STATE_BYTES = 1024 * 1024
MAX_HTTP_BODY_BYTES = 1024 * 1024
MAX_SSE_BODY_BYTES = 512 * 1024
MAX_SSE_LINE_BYTES = 64 * 1024
HTTP_CONNECT_TIMEOUT_SECONDS = 5.0
HTTP_READ_TIMEOUT_SECONDS = 15.0
HTTP_WRITE_TIMEOUT_SECONDS = 5.0
HTTP_POOL_TIMEOUT_SECONDS = 5.0
HTTP_TOTAL_TIMEOUT_SECONDS = 30.0
OPERATION_LOCK_TIMEOUT_SECONDS = 5.0
_RECONNECT_ERROR_CODES = frozenset(
    {
        "provider_auth_error",
        "subscription_sharing_invalid_user",
        "chatpass_v2_scope_not_authorized",
        "chatpass_v2_invalid_authorization_context",
    }
)
_CLIENT_ID_RE = re.compile(r"[A-Za-z0-9._-]{5,256}\Z")
_SAFE_ERROR_CODE_RE = re.compile(r"[A-Za-z0-9_.-]{1,100}\Z")
_ALL_REASONING_EFFORTS = ("none", "low", "medium", "high", "xhigh", "max")
_POSITIVE_REASONING_EFFORTS = _ALL_REASONING_EFFORTS[1:]


def reasoning_efforts_for_model(model: str) -> tuple[str, ...]:
    """Expose only effort values documented for known reasoning model families."""
    if model == "gpt-5.6" or model.startswith("gpt-5.6-"):
        return _ALL_REASONING_EFFORTS
    if model in {"gpt-6-luna", "gpt-6-sol"} or model.startswith(("gpt-6-luna-", "gpt-6-sol-")):
        return _ALL_REASONING_EFFORTS
    if model in {"gpt-6.1-sol", "gpt-6-astra"} or model.startswith(
        ("gpt-6.1-sol-", "gpt-6-astra-")
    ):
        return _POSITIVE_REASONING_EFFORTS
    return ()


def validate_reasoning_effort(model: str, effort: str) -> None:
    if effort != "default" and effort not in reasoning_efforts_for_model(model):
        raise ChatGPTError(
            400, "invalid_reasoning_effort", "Choose an effort supported by this model."
        )


_TERMINAL_REFRESH_CODES = frozenset(
    {
        "invalid_grant",
        "invalid_refresh_token",
        "token_expired",
        "refresh_token_expired",
        "refresh_token_invalidated",
        "refresh_token_reused",
    }
)


class ChatGPTError(RuntimeError):
    """A safe provider failure that can be returned to the local UI."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = 409 if status_code == 401 else status_code
        self.code = code if _SAFE_ERROR_CODE_RE.fullmatch(code) else "provider_error"
        self.message = message
        self.diagnostics: dict[str, Any] = {}

    @property
    def public_message(self) -> str:
        return ChatGPTHTTPAdapter._message_for(self.status_code, self.code)


class ProviderStateError(ChatGPTError):
    """The dedicated provider credential store cannot be used safely."""

    def __init__(self, diagnostic: str = "Provider credential storage is unavailable") -> None:
        self.diagnostic = diagnostic
        super().__init__(
            503, "provider_storage_unavailable", "ChatGPT connection storage is unavailable."
        )


@dataclass(frozen=True, slots=True)
class VerifiedIdentity:
    subject: str
    email: str | None
    email_verified: bool


class ChatGPTAdapter(Protocol):
    """Network boundary for the provider service; tests inject a deterministic adapter."""

    def exchange_code(
        self, *, code: str, verifier: str, redirect_uri: str, client_id: str
    ) -> dict[str, Any]: ...

    def validate_identity(
        self, id_token: str, *, client_id: str, nonce: str
    ) -> VerifiedIdentity: ...

    def refresh(self, *, client_id: str, refresh_token: str) -> dict[str, Any]: ...

    def list_models(self, *, access_token: str) -> list[dict[str, Any]]: ...

    def verify(
        self, *, access_token: str, model: str, reasoning_effort: str = "default"
    ) -> None: ...

    def revoke(self, *, client_id: str, refresh_token: str) -> bool: ...


class ProviderStore:
    """Owner-only atomic state, with separate state and cross-process use locks."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self.state_path = self.directory / "chatgpt.json"
        self.state_lock_path = self.directory / ".chatgpt-state.lock"
        self.operation_lock_path = self.directory / ".chatgpt-operation.lock"

    def _prepare_directory(self) -> None:
        try:
            self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            if self.directory.is_symlink():
                raise ProviderStateError("Provider storage directory must not be a symbolic link")
            os.chmod(self.directory, 0o700)
        except (OSError, ProviderStateError) as exc:
            raise ProviderStateError("Provider credential storage is unavailable") from exc

    @contextmanager
    def _file_lock(self, path: Path, *, timeout: float | None = None) -> Iterator[None]:
        self._prepare_directory()
        flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags, 0o600)
        except OSError as exc:
            raise ProviderStateError("Provider credential lock is unavailable") from exc
        acquired = False
        try:
            try:
                os.fchmod(descriptor, 0o600)
                if timeout is None:
                    fcntl.flock(descriptor, fcntl.LOCK_EX)
                else:
                    deadline = time.monotonic() + max(0.0, timeout)
                    while True:
                        try:
                            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                            break
                        except BlockingIOError:
                            remaining = deadline - time.monotonic()
                            if remaining <= 0:
                                raise ChatGPTError(
                                    503,
                                    "provider_busy",
                                    "Another ChatGPT operation is still running. "
                                    "Try again shortly.",
                                ) from None
                            time.sleep(min(0.01, remaining))
                acquired = True
            except OSError as exc:
                raise ProviderStateError("Provider credential lock is unavailable") from exc
            yield
        finally:
            if acquired:
                with suppress(OSError):
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    @staticmethod
    def _empty_state() -> dict[str, Any]:
        return {
            "version": 1,
            "host_id": f"urn:uuid:{uuid.uuid4()}",
            "connection_status": "disconnected",
            "connection_version": 0,
            "active_client_id": None,
            "registrations": {},
            "sessions": {},
            "notes_provider": None,
            "selected_model": None,
            "selected_reasoning_effort": "default",
            "verification": None,
        }

    def _read(self) -> dict[str, Any]:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(self.state_path, flags)
        except OSError as exc:
            raise ProviderStateError("Provider credential state is unavailable") from exc
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise ProviderStateError("Provider credential state is not a regular file")
            if metadata.st_mode & 0o077:
                raise ProviderStateError("Provider credential state permissions are too broad")
            if metadata.st_size > MAX_PROVIDER_STATE_BYTES:
                raise ProviderStateError("Provider credential state is too large")
            chunks: list[bytes] = []
            total = 0
            while chunk := os.read(descriptor, 64 * 1024):
                total += len(chunk)
                if total > MAX_PROVIDER_STATE_BYTES:
                    raise ProviderStateError("Provider credential state is too large")
                chunks.append(chunk)
            document = json.loads(b"".join(chunks))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderStateError("Provider credential state is invalid") from exc
        finally:
            os.close(descriptor)
        if (
            not isinstance(document, dict)
            or document.get("version") != 1
            or not isinstance(document.get("host_id"), str)
            or not document["host_id"].startswith("urn:uuid:")
            or document.get("connection_status")
            not in {"disconnected", "connected", "reconnect_required"}
            or not isinstance(document.get("connection_version"), int)
            or not isinstance(document.get("registrations"), dict)
            or not isinstance(document.get("sessions"), dict)
        ):
            raise ProviderStateError("Provider credential state is invalid")
        return document

    def _write(self, state: dict[str, Any]) -> None:
        try:
            payload = json.dumps(state, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            if len(payload) > MAX_PROVIDER_STATE_BYTES:
                raise ProviderStateError("Provider credential state is too large")
            descriptor, temporary_name = tempfile.mkstemp(prefix=".chatgpt-", dir=self.directory)
            temporary_path = Path(temporary_name)
            try:
                os.fchmod(descriptor, 0o600)
                with os.fdopen(descriptor, "wb") as file_handle:
                    file_handle.write(payload)
                    file_handle.flush()
                    os.fsync(file_handle.fileno())
                os.replace(temporary_path, self.state_path)
                directory_descriptor = os.open(self.directory, os.O_RDONLY)
                try:
                    os.fsync(directory_descriptor)
                finally:
                    os.close(directory_descriptor)
            except BaseException:
                with suppress(OSError):
                    os.close(descriptor)
                temporary_path.unlink(missing_ok=True)
                raise
        except (OSError, TypeError, ValueError) as exc:
            raise ProviderStateError("Provider credential state could not be saved") from exc

    @contextmanager
    def locked(self, *, write: bool = False) -> Iterator[dict[str, Any]]:
        with self._file_lock(self.state_lock_path):
            state = self._read()
            yield state
            if write:
                self._write(state)

    @contextmanager
    def operation(self, *, timeout: float | None = None) -> Iterator[None]:
        wait_seconds = OPERATION_LOCK_TIMEOUT_SECONDS if timeout is None else timeout
        with self._file_lock(self.operation_lock_path, timeout=wait_seconds):
            yield

    def ensure(self) -> None:
        with self._file_lock(self.state_lock_path):
            if self.state_path.exists() or self.state_path.is_symlink():
                self._read()
                return
            self._write(self._empty_state())


class ChatGPTHTTPAdapter:
    """Fixed-endpoint HTTP implementation for Sign in with ChatGPT."""

    def __init__(self, *, transport: httpx.BaseTransport | None = None) -> None:
        self._transport = transport
        self._discovery_document: dict[str, Any] | None = None
        self._discovery_lock = threading.Lock()

    @contextmanager
    def _client(self) -> Iterator[httpx.Client]:
        timeout = httpx.Timeout(
            connect=HTTP_CONNECT_TIMEOUT_SECONDS,
            read=HTTP_READ_TIMEOUT_SECONDS,
            write=HTTP_WRITE_TIMEOUT_SECONDS,
            pool=HTTP_POOL_TIMEOUT_SECONDS,
        )
        with httpx.Client(
            transport=self._transport,
            timeout=timeout,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            yield client

    @staticmethod
    def _read_limited(
        response: httpx.Response,
        *,
        limit: int = MAX_HTTP_BODY_BYTES,
        deadline: float | None = None,
    ) -> bytes:
        ChatGPTHTTPAdapter._check_deadline(deadline)
        raw_length = response.headers.get("content-length")
        if raw_length is not None:
            try:
                if int(raw_length) > limit:
                    raise ChatGPTError(
                        502,
                        "provider_response_too_large",
                        "ChatGPT returned an oversized response.",
                    )
            except ValueError:
                pass
        body = bytearray()
        for chunk in response.iter_bytes():
            ChatGPTHTTPAdapter._check_deadline(deadline)
            if len(body) + len(chunk) > limit:
                raise ChatGPTError(
                    502, "provider_response_too_large", "ChatGPT returned an oversized response."
                )
            body.extend(chunk)
        ChatGPTHTTPAdapter._check_deadline(deadline)
        return bytes(body)

    @staticmethod
    def _check_deadline(deadline: float | None) -> None:
        if deadline is not None and time.monotonic() >= deadline:
            raise ChatGPTError(503, "provider_timeout", "ChatGPT did not respond in time.")

    @staticmethod
    def _json_document(raw: bytes) -> dict[str, Any]:
        try:
            value = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ChatGPTError(
                502, "provider_invalid_response", "ChatGPT returned an invalid response."
            ) from None
        if not isinstance(value, dict):
            raise ChatGPTError(
                502, "provider_invalid_response", "ChatGPT returned an invalid response."
            )
        return value

    @staticmethod
    def _message_for(status_code: int, code: str) -> str:
        if code in {"subscription_sharing_usage_limit_exceeded"} or status_code == 429:
            return "ChatGPT plan usage is limited. Review ChatGPT Settings → Usage."
        if code in {
            "subscription_sharing_user_not_eligible",
            "subscription_sharing_route_not_supported",
        }:
            return "ChatGPT plan use is unavailable for this account, workspace, or request."
        if code in {
            "chatpass_v2_scope_not_authorized",
            "chatpass_v2_invalid_authorization_context",
        }:
            return "ChatGPT did not grant permission for plan use. Sign in again to review access."
        if code == "provider_busy":
            return "Another ChatGPT operation is still running. Try again shortly."
        if code == "subscription_sharing_unsupported_capability":
            return "ChatGPT does not support this request for the selected model."
        if status_code in {400, 422}:
            return "ChatGPT rejected this request. Check the selected model or permission."
        if status_code == 403:
            return "ChatGPT denied this request. Check account or workspace permissions."
        if status_code == 503:
            return "ChatGPT plan use is temporarily unavailable."
        if status_code >= 500:
            return "ChatGPT is temporarily unavailable."
        if status_code == 409:
            return (
                "ChatGPT could not complete this request. Sign in again if the problem continues."
            )
        return "ChatGPT could not complete this request."

    @classmethod
    def _http_error(cls, response: httpx.Response, body: bytes) -> ChatGPTError:
        code = "provider_http_error"
        document: object = None
        try:
            document = json.loads(body)
            if isinstance(document, dict):
                error = document.get("error")
                if isinstance(error, dict) and isinstance(error.get("code"), str):
                    code = error["code"]
                elif isinstance(error, str):
                    code = error
                elif isinstance(document.get("detail"), str):
                    code = "provider_admission_denied"
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
        if not _SAFE_ERROR_CODE_RE.fullmatch(code):
            code = "provider_http_error"
        if response.status_code == 401 and code not in _TERMINAL_REFRESH_CODES | {
            "invalid_client",
            "subscription_sharing_invalid_user",
        }:
            code = "provider_auth_error"
        status = 409 if response.status_code == 401 else response.status_code
        if not 400 <= status <= 599:
            status = 502
        failure = ChatGPTError(status, code, cls._message_for(response.status_code, code))
        failure.diagnostics = cls._diagnostics(response, document)
        return failure

    @staticmethod
    def _diagnostics(response: httpx.Response | None, document: object) -> dict[str, Any]:
        # Preserve correlation and field names, never provider prose or raw payloads.
        result: dict[str, Any] = {"body_shape": "non_json"}
        if isinstance(document, dict):
            result["body_shape"] = "detail" if "detail" in document else "error"
            error = document.get("error", document)
            param = error.get("param") if isinstance(error, dict) else None
            if isinstance(param, str) and re.fullmatch(r"[A-Za-z0-9_.\[\]-]{1,200}", param):
                result["param"] = param
        if response is not None:
            result["http_status"] = response.status_code
            request_id = response.headers.get("x-request-id", "")
            if re.fullmatch(r"[A-Za-z0-9_-]{1,200}", request_id):
                result["request_id"] = request_id
        return result

    @classmethod
    def _json_request(
        cls,
        client: httpx.Client,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        data: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + HTTP_TOTAL_TIMEOUT_SECONDS
        try:
            with client.stream(method, url, headers=headers, data=data, json=json_body) as response:
                body = cls._read_limited(response, deadline=deadline)
        except httpx.TimeoutException:
            raise ChatGPTError(
                503, "provider_timeout", "ChatGPT did not respond in time."
            ) from None
        except httpx.HTTPError:
            raise ChatGPTError(
                503, "provider_unavailable", "ChatGPT could not be reached."
            ) from None
        if not 200 <= response.status_code < 300:
            raise cls._http_error(response, body)
        return cls._json_document(body)

    def _discovery(self, client: httpx.Client) -> dict[str, Any]:
        with self._discovery_lock:
            if self._discovery_document is not None:
                return self._discovery_document
            document = self._json_request(client, "GET", DISCOVERY_URL)
            if (
                document.get("issuer") != ISSUER
                or document.get("authorization_endpoint") != AUTHORIZATION_URL
                or document.get("token_endpoint") != TOKEN_URL
                or not isinstance(document.get("id_token_signing_alg_values_supported"), list)
                or "RS256" not in document["id_token_signing_alg_values_supported"]
            ):
                raise ChatGPTError(
                    502, "provider_discovery_invalid", "ChatGPT sign-in configuration is invalid."
                )
            for name in ("jwks_uri", "revocation_endpoint"):
                endpoint = document.get(name)
                try:
                    parsed = urlsplit(endpoint) if isinstance(endpoint, str) else None
                    port = parsed.port if parsed else None
                except ValueError:
                    parsed = None
                    port = None
                if (
                    parsed is None
                    or parsed.scheme != "https"
                    or parsed.hostname != "auth.openai.com"
                    or parsed.username is not None
                    or parsed.password is not None
                    or port not in {None, 443}
                    or parsed.fragment
                ):
                    raise ChatGPTError(
                        502,
                        "provider_discovery_invalid",
                        "ChatGPT sign-in configuration is invalid.",
                    )
            self._discovery_document = document
            return document

    def exchange_code(
        self, *, code: str, verifier: str, redirect_uri: str, client_id: str
    ) -> dict[str, Any]:
        with self._client() as client:
            return self._json_request(
                client,
                "POST",
                TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "grant_type": "authorization_code",
                    "client_id": client_id,
                    "code": code,
                    "code_verifier": verifier,
                    "redirect_uri": redirect_uri,
                    "resource": RESOURCE,
                },
            )

    def validate_identity(self, id_token: str, *, client_id: str, nonce: str) -> VerifiedIdentity:
        if len(id_token) > 64 * 1024:
            raise ChatGPTError(
                502, "invalid_identity_token", "ChatGPT returned an invalid identity token."
            )
        try:
            header = jwt.get_unverified_header(id_token)
            if (
                header.get("alg") != "RS256"
                or "jku" in header
                or "x5u" in header
                or "crit" in header
                or not isinstance(header.get("kid"), str)
                or len(header["kid"]) > 256
            ):
                raise jwt.InvalidTokenError("Unsupported identity token header")
            with self._client() as client:
                discovery = self._discovery(client)
                jwks = self._json_request(client, "GET", discovery["jwks_uri"])
            keys = jwks.get("keys")
            if not isinstance(keys, list):
                raise jwt.InvalidTokenError("Invalid JWKS")
            jwk_document = next(
                (
                    item
                    for item in keys
                    if isinstance(item, dict)
                    and item.get("kid") == header["kid"]
                    and item.get("kty") == "RSA"
                    and item.get("use", "sig") == "sig"
                    and item.get("alg", "RS256") == "RS256"
                ),
                None,
            )
            if jwk_document is None:
                raise jwt.InvalidTokenError("Signing key is unavailable")
            signing_key = jwt.PyJWK.from_dict(jwk_document, algorithm="RS256").key
            claims = jwt.decode(
                id_token,
                signing_key,
                algorithms=["RS256"],
                audience=client_id,
                issuer=ISSUER,
                options={"require": ["exp", "iat", "sub", "nonce"]},
            )
            if not isinstance(claims.get("nonce"), str) or not hmac.compare_digest(
                claims["nonce"], nonce
            ):
                raise jwt.InvalidTokenError("Nonce mismatch")
            subject = claims.get("sub")
            email = claims.get("email")
            if not isinstance(subject, str) or not subject or len(subject) > 2048:
                raise jwt.InvalidTokenError("Subject is invalid")
            if email is not None and (not isinstance(email, str) or len(email) > 320):
                email = None
            return VerifiedIdentity(subject, email, claims.get("email_verified") is True)
        except ChatGPTError:
            raise
        except (jwt.PyJWTError, KeyError, TypeError, ValueError):
            raise ChatGPTError(
                502, "invalid_identity_token", "ChatGPT returned an invalid identity token."
            ) from None

    def refresh(self, *, client_id: str, refresh_token: str) -> dict[str, Any]:
        with self._client() as client:
            return self._json_request(
                client,
                "POST",
                TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                    "refresh_token": refresh_token,
                    "resource": RESOURCE,
                },
            )

    def list_models(self, *, access_token: str) -> list[dict[str, Any]]:
        with self._client() as client:
            document = self._json_request(
                client,
                "GET",
                f"{API_BASE_URL}/models",
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            )
        models = document.get("models")
        if not isinstance(models, list):
            raise ChatGPTError(
                502, "provider_invalid_model_catalog", "ChatGPT returned an invalid model catalog."
            )
        return models

    def verify(self, *, access_token: str, model: str, reasoning_effort: str = "default") -> None:
        body: dict[str, Any] = {
            "model": model,
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": 'Return exactly {"ok":true}.'}],
                }
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "connection_check",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {"ok": {"type": "boolean"}},
                        "required": ["ok"],
                        "additionalProperties": False,
                    },
                }
            },
            "store": False,
            "stream": True,
        }
        if reasoning_effort != "default":
            body["reasoning"] = {"effort": reasoning_effort}
        completed = False
        delta_text: list[str] = []
        total_text = 0
        with self._client() as client:
            deadline = time.monotonic() + HTTP_TOTAL_TIMEOUT_SECONDS
            try:
                with client.stream(
                    "POST",
                    f"{API_BASE_URL}/responses",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "text/event-stream",
                        "Content-Type": "application/json",
                    },
                    json=body,
                ) as response:
                    if not 200 <= response.status_code < 300:
                        error_body = self._read_limited(response, deadline=deadline)
                        raise self._http_error(response, error_body)
                    content_type = (
                        response.headers.get("content-type", "")
                        .split(";", maxsplit=1)[0]
                        .strip()
                        .lower()
                    )
                    if "content-type" in response.headers and content_type != "text/event-stream":
                        raise ChatGPTError(
                            502,
                            "provider_invalid_stream",
                            "ChatGPT returned an invalid verification stream.",
                        )
                    for event in self._sse_events(response, deadline=deadline):
                        event_type = event.get("type")
                        if event_type == "response.output_text.delta":
                            delta = event.get("delta")
                            if not isinstance(delta, str):
                                raise ChatGPTError(
                                    502,
                                    "provider_invalid_stream",
                                    "ChatGPT returned an invalid verification stream.",
                                )
                            total_text += len(delta.encode("utf-8"))
                            if total_text > 16 * 1024:
                                raise ChatGPTError(
                                    502,
                                    "provider_output_too_large",
                                    "ChatGPT returned an oversized verification result.",
                                )
                            delta_text.append(delta)
                        elif event_type == "response.failed":
                            error = (
                                event.get("response", {}).get("error")
                                if isinstance(event.get("response"), dict)
                                else None
                            )
                            raise self._sse_error(error)
                        elif event_type == "error":
                            raise self._sse_error(event.get("error", event))
                        elif event_type == "response.incomplete":
                            raise ChatGPTError(
                                502,
                                "verification_incomplete",
                                "ChatGPT did not complete the verification request.",
                            )
                        elif event_type == "response.completed":
                            if completed:
                                raise ChatGPTError(
                                    502,
                                    "provider_invalid_stream",
                                    "ChatGPT returned an invalid verification stream.",
                                )
                            completed = True
                            if not delta_text:
                                output_text = self._completed_output_text(event)
                                delta_text.extend(output_text)
                            break
            except ChatGPTError as error:
                if "response" in locals():
                    correlation = self._diagnostics(response, None)
                    correlation.update(error.diagnostics)
                    error.diagnostics = correlation
                raise
            except httpx.TimeoutException:
                raise ChatGPTError(
                    503, "provider_timeout", "ChatGPT did not complete the verification request."
                ) from None
            except httpx.HTTPError:
                raise ChatGPTError(
                    503,
                    "provider_unavailable",
                    "ChatGPT could not complete the verification request.",
                ) from None
        if not completed:
            raise ChatGPTError(
                502, "verification_incomplete", "ChatGPT did not complete the verification request."
            )
        try:
            result = json.loads("".join(delta_text))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ChatGPTError(
                502,
                "verification_invalid_output",
                "ChatGPT returned an invalid verification result.",
            ) from None
        if not isinstance(result, dict) or set(result) != {"ok"} or result["ok"] is not True:
            raise ChatGPTError(
                502,
                "verification_invalid_output",
                "ChatGPT returned an invalid verification result.",
            )

    @staticmethod
    def _completed_output_text(event: dict[str, Any]) -> list[str]:
        response = event.get("response")
        if not isinstance(response, dict) or not isinstance(response.get("output"), list):
            return []
        text_parts = []
        for item in response["output"]:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if (
                    isinstance(part, dict)
                    and part.get("type") == "output_text"
                    and isinstance(part.get("text"), str)
                ):
                    text_parts.append(part["text"])
        return text_parts

    @staticmethod
    def _sse_error(error: object) -> ChatGPTError:
        code = "provider_inference_error"
        status = 502
        if isinstance(error, dict):
            if isinstance(error.get("code"), str) and _SAFE_ERROR_CODE_RE.fullmatch(error["code"]):
                code = error["code"]
            candidate_status = error.get("status")
            if isinstance(candidate_status, int) and 400 <= candidate_status <= 599:
                status = candidate_status
        status = {
            "subscription_sharing_user_not_eligible": 403,
            "subscription_sharing_usage_limit_exceeded": 429,
            "subscription_sharing_usage_unavailable": 503,
            "subscription_sharing_unsupported_capability": 400,
            "subscription_sharing_route_not_supported": 403,
            "subscription_sharing_invalid_user": 409,
            "chatpass_v2_scope_not_authorized": 403,
            "chatpass_v2_invalid_authorization_context": 403,
            "subscription_sharing_user_unavailable": 503,
        }.get(code, status)
        if status == 401:
            code = "provider_auth_error"
        failure = ChatGPTError(status, code, ChatGPTHTTPAdapter._message_for(status, code))
        failure.diagnostics = ChatGPTHTTPAdapter._diagnostics(None, error)
        return failure

    @classmethod
    def _sse_events(
        cls, response: httpx.Response, *, deadline: float | None = None
    ) -> Iterator[dict[str, Any]]:
        buffer = bytearray()
        data_lines: list[bytes] = []
        total = 0

        def parse_event() -> dict[str, Any] | None:
            if not data_lines:
                return None
            payload = b"\n".join(data_lines)
            data_lines.clear()
            if payload == b"[DONE]":
                return None
            try:
                event = json.loads(payload)
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise ChatGPTError(
                    502,
                    "provider_invalid_stream",
                    "ChatGPT returned an invalid verification stream.",
                ) from None
            if not isinstance(event, dict):
                raise ChatGPTError(
                    502,
                    "provider_invalid_stream",
                    "ChatGPT returned an invalid verification stream.",
                )
            return event

        try:
            cls._check_deadline(deadline)
            for chunk in response.iter_bytes():
                cls._check_deadline(deadline)
                total += len(chunk)
                if total > MAX_SSE_BODY_BYTES:
                    raise ChatGPTError(
                        502,
                        "provider_stream_too_large",
                        "ChatGPT returned an oversized verification stream.",
                    )
                buffer.extend(chunk)
                while True:
                    newline = buffer.find(b"\n")
                    if newline < 0:
                        if len(buffer) > MAX_SSE_LINE_BYTES:
                            raise ChatGPTError(
                                502,
                                "provider_stream_line_too_large",
                                "ChatGPT returned an oversized verification stream.",
                            )
                        break
                    line = bytes(buffer[:newline]).rstrip(b"\r")
                    del buffer[: newline + 1]
                    if not line:
                        event = parse_event()
                        if event is not None:
                            yield event
                    elif not line.startswith(b":"):
                        field, separator, value = line.partition(b":")
                        if field == b"data":
                            if separator and value.startswith(b" "):
                                value = value[1:]
                            data_lines.append(value)
            cls._check_deadline(deadline)
            if buffer:
                line = bytes(buffer).rstrip(b"\r")
                if line.startswith(b"data:"):
                    data_lines.append(line[5:].lstrip(b" "))
            event = parse_event()
            if event is not None:
                yield event
        except httpx.HTTPError:
            raise

    def revoke(self, *, client_id: str, refresh_token: str) -> bool:
        with self._client() as client:
            discovery = self._discovery(client)
            deadline = time.monotonic() + HTTP_TOTAL_TIMEOUT_SECONDS
            try:
                with client.stream(
                    "POST",
                    discovery["revocation_endpoint"],
                    headers={"Accept": "application/json"},
                    data={
                        "token": refresh_token,
                        "token_type_hint": "refresh_token",
                        "client_id": client_id,
                    },
                ) as response:
                    self._read_limited(response, deadline=deadline)
            except httpx.TimeoutException:
                raise ChatGPTError(
                    503, "provider_timeout", "ChatGPT session revocation was not confirmed."
                ) from None
            except httpx.HTTPError:
                raise ChatGPTError(
                    503, "provider_unavailable", "ChatGPT session revocation was not confirmed."
                ) from None
        if response.status_code == 200:
            return True
        if response.status_code >= 500:
            raise ChatGPTError(
                response.status_code,
                "provider_revocation_unavailable",
                "ChatGPT session revocation was not confirmed.",
            )
        return False


class ChatGPTProvider:
    """Provider lifecycle and preferences, independent from HTTP route definitions."""

    def __init__(
        self,
        directory: Path,
        *,
        callback_url: str,
        adapter: ChatGPTAdapter | None = None,
        clock=time.time,
        sleeper=time.sleep,
    ) -> None:
        self.store = ProviderStore(directory)
        self.callback_url = callback_url
        self.adapter: ChatGPTAdapter = adapter or ChatGPTHTTPAdapter()
        self._clock = clock
        self._sleep = sleeper

    def ensure(self) -> None:
        self.store.ensure()

    def _now(self) -> float:
        return float(self._clock())

    @staticmethod
    def _iso_timestamp(value: float) -> str:
        return (
            datetime.fromtimestamp(value, UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        )

    @staticmethod
    def _clear_session_secrets(session: dict[str, Any]) -> None:
        for key in ("state", "nonce", "verifier"):
            session.pop(key, None)
        session["claimed"] = False

    @staticmethod
    def _expire_sessions(state: dict[str, Any], now: float) -> None:
        for session in state["sessions"].values():
            if session.get("status") == "pending" and session.get("expires_at", 0) <= now:
                session["status"] = "expired"
                ChatGPTProvider._clear_session_secrets(session)
        cutoff = now - 24 * 60 * 60
        for session_id in list(state["sessions"]):
            session = state["sessions"][session_id]
            if session.get("status") != "pending" and session.get("expires_at", now) < cutoff:
                del state["sessions"][session_id]

    @staticmethod
    def _session_view(session: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": session["id"],
            "status": session["status"],
            "expires_at": ChatGPTProvider._iso_timestamp(session["expires_at"]),
            "error": session.get("error"),
        }

    @staticmethod
    def _callback_error(code: str, message: str, status_code: int = 400) -> ChatGPTError:
        return ChatGPTError(status_code, code, message)

    @staticmethod
    def _issued_client_id(value: object) -> bool:
        return (
            isinstance(value, str)
            and value != DYNAMIC_CLIENT_ID
            and bool(_CLIENT_ID_RE.fullmatch(value))
        )

    def start_login(self) -> dict[str, Any]:
        with self.store.operation():
            self._revoke_invalid_subscriber()
            return self._start_login()

    def _revoke_invalid_subscriber(self) -> None:
        with self.store.locked() as state:
            if (
                state["connection_status"] != "reconnect_required"
                or state.get("last_provider_error") != "subscription_sharing_invalid_user"
            ):
                return
            client_id = state.get("active_client_id")
            registration = state["registrations"].get(client_id, {})
            refresh_token = registration.get("refresh_token")
        if not isinstance(refresh_token, str):
            return
        try:
            confirmed = self.adapter.revoke(client_id=client_id, refresh_token=refresh_token)
        except Exception:
            confirmed = False
        if not confirmed:
            raise ChatGPTError(
                503, "revocation_unconfirmed", "Confirm revocation before signing in again."
            )
        with self.store.locked(write=True) as state:
            self._clear_tokens(state["registrations"][client_id])

    def _start_login(self) -> dict[str, Any]:
        if not self.callback_url:
            raise ChatGPTError(
                409,
                "callback_not_configured",
                "Configure an HTTP loopback callback before signing in to ChatGPT.",
            )
        now = self._now()
        with self.store.locked(write=True) as state:
            self._expire_sessions(state, now)
            pending_sessions = [
                session
                for session in state["sessions"].values()
                if session.get("status") == "pending"
            ]
            for session in pending_sessions:
                session["status"] = "cancelled"
                session["error"] = None
                self._clear_session_secrets(session)
            client_id = state.get("active_client_id")
            registration = state["registrations"].get(client_id) if client_id else None
            if registration is None and state.get("provisional_client_id"):
                client_id = state["provisional_client_id"]
                registration = {}
            if registration is not None and not self._issued_client_id(client_id):
                raise ProviderStateError("Provider registration mapping is invalid")

            session_id = secrets.token_urlsafe(24)
            oauth_state = secrets.token_urlsafe(32)
            nonce = secrets.token_urlsafe(32)
            verifier = secrets.token_urlsafe(64)
            challenge = (
                base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
                .rstrip(b"=")
                .decode("ascii")
            )
            expires_at = now + SESSION_TTL_SECONDS
            session: dict[str, Any] = {
                "id": session_id,
                "status": "pending",
                "created_at": now,
                "expires_at": expires_at,
                "state": oauth_state,
                "nonce": nonce,
                "verifier": verifier,
                "expected_client_id": client_id if registration is not None else None,
                "expected_subject": registration.get("subject")
                if registration is not None
                else None,
                "claimed": False,
                "error": None,
            }
            state["sessions"][session_id] = session
            parameters = {
                "client_id": client_id if registration is not None else DYNAMIC_CLIENT_ID,
                "ext_agent_host_id": state["host_id"],
                "response_type": "code",
                "redirect_uri": self.callback_url,
                "scope": REQUESTED_SCOPES,
                "resource": RESOURCE,
                "state": oauth_state,
                "nonce": nonce,
                "code_challenge_method": "S256",
                "code_challenge": challenge,
            }
            if registration is None:
                parameters["agent_name_hint"] = "ASR EN VI"
            elif registration.get("email"):
                parameters["login_hint"] = registration["email"]
            if state.get("last_provider_error") in {
                "scope_not_authorized",
                "scope_down",
                "chatpass_v2_scope_not_authorized",
            }:
                parameters["prompt"] = "consent"
            authorization_url = f"{AUTHORIZATION_URL}?{urlencode(parameters)}"
            response: dict[str, Any] = {
                "id": session_id,
                "status": "pending",
                "authorization_url": authorization_url,
                "expires_at": self._iso_timestamp(expires_at),
            }
            if pending_sessions:
                response["replaced_previous"] = True
            return response

    def login_session(self, session_id: str) -> dict[str, Any]:
        if not re.fullmatch(r"[A-Za-z0-9_-]{20,64}", session_id):
            raise ChatGPTError(404, "login_session_not_found", "ChatGPT sign-in session not found.")
        now = self._now()
        with self.store.locked(write=True) as state:
            self._expire_sessions(state, now)
            session = state["sessions"].get(session_id)
            if session is None:
                raise ChatGPTError(
                    404, "login_session_not_found", "ChatGPT sign-in session not found."
                )
            return self._session_view(session)

    def cancel_login(self, session_id: str) -> dict[str, Any]:
        if not re.fullmatch(r"[A-Za-z0-9_-]{20,64}", session_id):
            raise ChatGPTError(404, "login_session_not_found", "ChatGPT sign-in session not found.")
        now = self._now()
        with self.store.locked(write=True) as state:
            self._expire_sessions(state, now)
            session = state["sessions"].get(session_id)
            if session is None:
                raise ChatGPTError(
                    404, "login_session_not_found", "ChatGPT sign-in session not found."
                )
            if session["status"] == "pending":
                session["status"] = "cancelled"
                self._clear_session_secrets(session)
                session["error"] = None
                return self._session_view(session)
            if session["status"] in {"cancelled", "expired"}:
                return self._session_view(session)
            raise ChatGPTError(
                409,
                "login_session_completed",
                "This ChatGPT sign-in session has already completed.",
            )

    @staticmethod
    def _query_values(pairs: Sequence[tuple[str, str]]) -> dict[str, str]:
        if len(pairs) > 20:
            raise ChatGPTError(400, "invalid_callback", "The ChatGPT sign-in response is invalid.")
        values: dict[str, str] = {}
        for key, value in pairs:
            if key not in {"state", "code", "client_id", "error", "scope"}:
                continue
            if key in values or len(value) > 4096:
                raise ChatGPTError(
                    400, "invalid_callback", "The ChatGPT sign-in response is invalid."
                )
            values[key] = value
        return values

    def _claim_callback(self, oauth_state: str) -> tuple[str, dict[str, Any]]:
        now = self._now()
        with self.store.locked(write=True) as state:
            self._expire_sessions(state, now)
            matches = [
                (session_id, session)
                for session_id, session in state["sessions"].items()
                if session.get("status") == "pending"
                and isinstance(session.get("state"), str)
                and hmac.compare_digest(session["state"], oauth_state)
            ]
            if len(matches) != 1:
                raise ChatGPTError(
                    400,
                    "invalid_or_replayed_state",
                    "The ChatGPT sign-in response could not be matched to an active attempt.",
                )
            session_id, session = matches[0]
            if session.get("claimed"):
                raise ChatGPTError(
                    409, "callback_replayed", "This ChatGPT sign-in response was already received."
                )
            session["claimed"] = True
            return session_id, dict(session)

    def _finish_session(
        self,
        session_id: str,
        *,
        status: str,
        error: dict[str, str] | None = None,
    ) -> None:
        with self.store.locked(write=True) as state:
            session = state["sessions"].get(session_id)
            if session is None or session.get("status") != "pending":
                return
            session["status"] = status
            session["error"] = error
            self._clear_session_secrets(session)

    def _fail_session(self, session_id: str, error: ChatGPTError) -> None:
        self._finish_session(
            session_id,
            status="failed",
            error={"code": error.code, "message": error.public_message},
        )

    @staticmethod
    def _token_fields(
        tokens: dict[str, Any], *, previous_scopes: set[str] | None = None
    ) -> dict[str, Any]:
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")
        token_type = tokens.get("token_type", "Bearer")
        expires_in = tokens.get("expires_in")
        if (
            not isinstance(access_token, str)
            or not access_token
            or len(access_token) > 64 * 1024
            or not isinstance(refresh_token, str)
            or not refresh_token
            or len(refresh_token) > 64 * 1024
            or not isinstance(token_type, str)
            or token_type.lower() != "bearer"
            or isinstance(expires_in, bool)
            or not isinstance(expires_in, int)
            or not 1 <= expires_in <= 7 * 24 * 60 * 60
        ):
            raise ChatGPTError(
                502, "invalid_token_response", "ChatGPT returned an invalid token response."
            )
        raw_scope = tokens.get("scope")
        if raw_scope is None and previous_scopes is not None:
            scopes = set(previous_scopes)
        elif isinstance(raw_scope, str) and len(raw_scope) <= 4096:
            scopes = set(raw_scope.split())
        else:
            raise ChatGPTError(
                502, "invalid_token_response", "ChatGPT returned an invalid token response."
            )
        id_token = tokens.get("id_token")
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "id_token": id_token
            if isinstance(id_token, str) and len(id_token) <= 64 * 1024
            else None,
            "token_type": "Bearer",
            "expires_at": time.time() + expires_in,
            "scopes": sorted(scopes),
        }

    def handle_callback(self, pairs: Sequence[tuple[str, str]]) -> None:
        # Never consume a one-time OAuth result before acquiring the commit lock.
        with self.store.operation():
            self._handle_callback(pairs)

    def _revoke_rejected_exchange(self, client_id: str, tokens: object) -> None:
        # Best-effort cleanup mirrors explicit logout: discarded credentials are never usable.
        refresh_token = tokens.get("refresh_token") if isinstance(tokens, dict) else None
        if not isinstance(refresh_token, str) or not 1 <= len(refresh_token) <= 64 * 1024:
            return
        with suppress(Exception):
            self.adapter.revoke(client_id=client_id, refresh_token=refresh_token)

    def _handle_callback(self, pairs: Sequence[tuple[str, str]]) -> None:
        values = self._query_values(pairs)
        oauth_state = values.get("state")
        if oauth_state is None or not 20 <= len(oauth_state) <= 256:
            raise ChatGPTError(400, "invalid_callback", "The ChatGPT sign-in response is invalid.")
        session_id, session = self._claim_callback(oauth_state)

        oauth_error = values.get("error")
        if oauth_error:
            error = ChatGPTError(
                400, "access_denied", "ChatGPT sign-in was declined or could not be completed."
            )
            self._fail_session(session_id, error)
            raise error

        code = values.get("code")
        expected_client_id = session.get("expected_client_id")
        returned_client_id = values.get("client_id")
        if (
            not isinstance(code, str)
            or not code
            or len(code) > 2048
            or (expected_client_id is None and not self._issued_client_id(returned_client_id))
            or (
                expected_client_id is not None
                and returned_client_id is not None
                and returned_client_id != expected_client_id
            )
        ):
            error = ChatGPTError(
                400, "invalid_callback", "The ChatGPT sign-in response is incomplete or mismatched."
            )
            self._fail_session(session_id, error)
            raise error
        client_id = expected_client_id or returned_client_id
        if not self._issued_client_id(client_id):
            error = ChatGPTError(
                400,
                "invalid_client_registration",
                "ChatGPT did not return a valid app registration.",
            )
            self._fail_session(session_id, error)
            raise error

        code_exchanged = False
        tokens: dict[str, Any] | None = None
        try:
            tokens = self.adapter.exchange_code(
                code=code,
                verifier=session["verifier"],
                redirect_uri=self.callback_url,
                client_id=client_id,
            )
            code_exchanged = True
            token_fields = self._token_fields(tokens)
            id_token = token_fields["id_token"]
            if not isinstance(id_token, str):
                raise ChatGPTError(
                    502, "invalid_identity_token", "ChatGPT returned an invalid identity token."
                )
            identity = self.adapter.validate_identity(
                id_token, client_id=client_id, nonce=session["nonce"]
            )
            if session.get("expected_subject") and identity.subject != session["expected_subject"]:
                raise ChatGPTError(
                    409,
                    "account_identity_mismatch",
                    "The selected ChatGPT account did not match the saved registration.",
                )
            token_fields["expires_at"] = self._now() + int(tokens["expires_in"])
            token_fields.update(
                {
                    "subject": identity.subject,
                    "email": identity.email if identity.email_verified else None,
                    "label": identity.email
                    if identity.email_verified
                    else f"ChatGPT account · {client_id[-6:]}",
                    "client_id": client_id,
                }
            )
        except ChatGPTError as error:
            if code_exchanged:
                self._revoke_rejected_exchange(client_id, tokens)
            if not code_exchanged and error.code == "invalid_grant" and expected_client_id is None:
                with self.store.locked(write=True) as state:
                    current = state["sessions"].get(session_id)
                    if current and current.get("status") == "pending":
                        # Retain routing metadata only; identity remains unverified.
                        state["provisional_client_id"] = client_id
            self._fail_session(session_id, error)
            raise
        except (KeyError, TypeError, ValueError):
            if code_exchanged:
                self._revoke_rejected_exchange(client_id, tokens)
            error = ChatGPTError(
                502, "provider_invalid_response", "ChatGPT returned an invalid sign-in response."
            )
            self._fail_session(session_id, error)
            raise error from None

        commit_error: ChatGPTError | None = None
        now = self._now()
        with self.store.locked(write=True) as state:
            current = state["sessions"].get(session_id)
            if current is None or current.get("status") != "pending" or not current.get("claimed"):
                commit_error = ChatGPTError(
                    409,
                    "login_cancelled",
                    "This ChatGPT sign-in was cancelled before it completed.",
                )
            elif current.get("expires_at", 0) <= now:
                current["status"] = "expired"
                current["error"] = None
                self._clear_session_secrets(current)
                commit_error = ChatGPTError(
                    410, "login_session_expired", "This ChatGPT sign-in session expired."
                )
            else:
                prior = state["registrations"].get(client_id)
                if prior is not None and prior.get("subject") != identity.subject:
                    current["status"] = "failed"
                    current["error"] = {
                        "code": "account_identity_mismatch",
                        "message": (
                            "The selected ChatGPT account did not match the saved registration."
                        ),
                    }
                    self._clear_session_secrets(current)
                    commit_error = ChatGPTError(
                        409,
                        "account_identity_mismatch",
                        "The selected ChatGPT account did not match the saved registration.",
                    )
                else:
                    state["registrations"][client_id] = token_fields
                    state["active_client_id"] = client_id
                    state.pop("provisional_client_id", None)
                    state["connection_status"] = (
                        "connected"
                        if DIRECT_SCOPE in token_fields["scopes"]
                        else "reconnect_required"
                    )
                    if DIRECT_SCOPE in token_fields["scopes"]:
                        state.pop("last_provider_error", None)
                    else:
                        state["last_provider_error"] = "scope_not_authorized"
                    state.pop("last_diagnostic", None)
                    state["connection_version"] += 1
                    state["verification"] = None
                    current["status"] = "connected"
                    current["error"] = None
                    self._clear_session_secrets(current)
        if commit_error is not None:
            self._revoke_rejected_exchange(client_id, tokens)
            raise commit_error

    def get_providers(self) -> dict[str, Any]:
        with self.store.locked() as state:
            client_id = state.get("active_client_id")
            registration = state["registrations"].get(client_id) if client_id else None
            account = None
            if state["connection_status"] != "disconnected" and registration is not None:
                account = {"label": registration.get("label", "ChatGPT account")}
            return {
                "providers": [
                    {
                        "id": "chatgpt",
                        "status": state["connection_status"],
                        "account": account,
                        "connection_version": state["connection_version"],
                        "verification": state.get("verification"),
                    }
                ]
            }

    def notes_preferences(self) -> dict[str, Any]:
        with self.store.locked() as state:
            provider = (
                "chatgpt"
                if state.get("notes_provider") == "chatgpt"
                and state["connection_status"] == "connected"
                else None
            )
            models: dict[str, str] = {}
            if isinstance(state.get("selected_model"), str):
                models["chatgpt"] = state["selected_model"]
            return {
                "provider": provider,
                "models": models,
                "reasoning_effort": state.get("selected_reasoning_effort", "default"),
            }

    def _active_registration(self) -> tuple[str, dict[str, Any]]:
        with self.store.locked() as state:
            if state["connection_status"] != "connected":
                if state["connection_status"] == "reconnect_required":
                    raise ChatGPTError(
                        409, "reconnect_required", "Reconnect ChatGPT before using its plan."
                    )
                raise ChatGPTError(
                    409, "provider_disconnected", "Connect ChatGPT before using its plan."
                )
            client_id = state.get("active_client_id")
            registration = state["registrations"].get(client_id) if client_id else None
            if not isinstance(registration, dict) or not isinstance(
                registration.get("access_token"), str
            ):
                raise ProviderStateError("Provider registration credentials are unavailable")
            if DIRECT_SCOPE not in registration.get("scopes", []):
                raise ChatGPTError(
                    409, "scope_not_authorized", "Sign in again and allow ChatGPT plan use."
                )
            return client_id, dict(registration)

    @staticmethod
    def _clear_tokens(registration: dict[str, Any]) -> None:
        for key in (
            "access_token",
            "refresh_token",
            "id_token",
            "token_type",
            "expires_at",
            "scopes",
        ):
            registration.pop(key, None)

    def _record_failure(self, error: ChatGPTError) -> None:
        with self.store.locked(write=True) as state:
            state["last_diagnostic"] = {
                "code": error.code,
                "at": self._iso_timestamp(self._now()),
                **error.diagnostics,
            }

    def _mark_reconnect_required(self, code: str, *, refresh_token: str | None = None) -> None:
        with self.store.locked(write=True) as state:
            client_id = state.get("active_client_id")
            registration = state["registrations"].get(client_id) if client_id else None
            if registration is not None:
                revocation_token = refresh_token or registration.get("refresh_token")
                self._clear_tokens(registration)
                if code not in _TERMINAL_REFRESH_CODES and isinstance(revocation_token, str):
                    # Block inference, but retain the renewable session for explicit revocation.
                    registration["refresh_token"] = revocation_token
            state["connection_status"] = "reconnect_required"
            state["connection_version"] += 1
            state["verification"] = None
            state["last_provider_error"] = code

    def _access_token(self) -> str:
        client_id, registration = self._active_registration()
        expires_at = registration.get("expires_at")
        refresh_token = registration.get("refresh_token")
        if not isinstance(expires_at, (float, int)) or not isinstance(refresh_token, str):
            raise ProviderStateError("Provider token state is invalid")
        if expires_at > self._now() + ACCESS_REFRESH_MARGIN_SECONDS:
            return registration["access_token"]
        try:
            refreshed = self.adapter.refresh(client_id=client_id, refresh_token=refresh_token)
            fields = self._token_fields(
                refreshed, previous_scopes=set(registration.get("scopes", []))
            )
        except ChatGPTError as error:
            self._record_failure(error)
            if error.code in _TERMINAL_REFRESH_CODES:
                self._mark_reconnect_required(error.code)
                raise ChatGPTError(
                    409, "reconnect_required", "Reconnect ChatGPT to renew plan access."
                ) from None
            if error.code in _RECONNECT_ERROR_CODES:
                self._mark_reconnect_required(error.code, refresh_token=refresh_token)
            raise
        old_scopes = set(registration.get("scopes", []))
        new_scopes = set(fields["scopes"])
        if not old_scopes.issubset(new_scopes) or DIRECT_SCOPE not in new_scopes:
            self._mark_reconnect_required("scope_down", refresh_token=fields["refresh_token"])
            raise ChatGPTError(
                409, "reconnect_required", "Reconnect ChatGPT to restore the required plan access."
            )
        fields["subject"] = registration["subject"]
        fields["email"] = registration.get("email")
        fields["label"] = registration.get("label", "ChatGPT account")
        fields["client_id"] = client_id
        fields["id_token"] = registration.get("id_token")
        fields["expires_at"] = self._now() + int(refreshed["expires_in"])
        with self.store.locked(write=True) as state:
            current = state["registrations"].get(client_id)
            if (
                current is None
                or current.get("refresh_token") != refresh_token
                or state.get("connection_status") != "connected"
            ):
                raise ChatGPTError(
                    409, "connection_changed", "The ChatGPT connection changed. Try again."
                )
            state["registrations"][client_id] = fields
        return fields["access_token"]

    def _models(self) -> list[dict[str, Any]]:
        access_token = self._access_token()
        try:
            raw_models = self.adapter.list_models(access_token=access_token)
        except ChatGPTError as error:
            self._record_failure(error)
            if error.code in _RECONNECT_ERROR_CODES:
                self._mark_reconnect_required(error.code)
            raise
        models: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in raw_models:
            if not isinstance(item, dict) or item.get("visibility") != "list":
                continue
            slug = item.get("slug")
            display_name = item.get("display_name")
            if (
                not isinstance(slug, str)
                or not slug
                or len(slug) > 200
                or not isinstance(display_name, str)
                or not display_name
                or len(display_name) > 200
                or slug in seen
            ):
                continue
            seen.add(slug)
            models.append(
                {
                    "id": slug,
                    "display_name": display_name,
                    "reasoning_efforts": list(reasoning_efforts_for_model(slug)),
                }
            )
        return models

    def list_models(self) -> dict[str, Any]:
        with self.store.operation():
            models = self._models()
            with self.store.locked() as state:
                return {"models": models, "selected_model": state.get("selected_model")}

    def set_notes_preference(
        self, *, provider: str, model: str, reasoning_effort: str = "default"
    ) -> dict[str, Any]:
        if provider != "chatgpt" or not isinstance(model, str) or not 1 <= len(model) <= 200:
            raise ChatGPTError(400, "invalid_preference", "Choose an available ChatGPT model.")
        validate_reasoning_effort(model, reasoning_effort)
        with self.store.operation():
            models = self._models()
            if not any(item["id"] == model for item in models):
                raise ChatGPTError(
                    422,
                    "model_unavailable",
                    "The selected model is not available to this ChatGPT account.",
                )
            with self.store.locked(write=True) as state:
                state["notes_provider"] = "chatgpt"
                state["selected_model"] = model
                state["selected_reasoning_effort"] = reasoning_effort
        return self.notes_preferences()

    def verify(self, *, model: str, reasoning_effort: str | None = None) -> dict[str, Any]:
        if not isinstance(model, str) or not 1 <= len(model) <= 200:
            raise ChatGPTError(400, "invalid_model", "Choose an available ChatGPT model to verify.")
        if reasoning_effort is None:
            with self.store.locked() as state:
                reasoning_effort = (
                    state.get("selected_reasoning_effort", "default")
                    if state.get("selected_model") == model
                    else "default"
                )
        validate_reasoning_effort(model, reasoning_effort)
        with self.store.operation():
            models = self._models()
            if not any(item["id"] == model for item in models):
                raise ChatGPTError(
                    422,
                    "model_unavailable",
                    "The selected model is not available to this ChatGPT account.",
                )
            access_token = self._access_token()
            try:
                self.adapter.verify(
                    access_token=access_token, model=model, reasoning_effort=reasoning_effort
                )
            except ChatGPTError as error:
                self._record_failure(error)
                if error.code in _RECONNECT_ERROR_CODES:
                    self._mark_reconnect_required(error.code)
                raise
            verified_at = self._iso_timestamp(self._now())
            with self.store.locked(write=True) as state:
                state["verification"] = {
                    "model": model,
                    "reasoning_effort": reasoning_effort,
                    "verified_at": verified_at,
                }
            return {
                "model": model,
                "reasoning_effort": reasoning_effort,
                "verified_at": verified_at,
                "output": {"ok": True},
            }

    def disconnect(self) -> dict[str, Any]:
        confirmed = False
        with self.store.operation():
            try:
                with self.store.locked() as state:
                    client_id = state.get("active_client_id")
                    registration = state["registrations"].get(client_id) if client_id else None
                    refresh_token = registration.get("refresh_token") if registration else None
            except ProviderStateError:
                raise

            if isinstance(refresh_token, str) and self._issued_client_id(client_id):
                for attempt in range(3):
                    try:
                        confirmed = self.adapter.revoke(
                            client_id=client_id,
                            refresh_token=refresh_token,
                        )
                        break
                    except ChatGPTError as error:
                        if error.status_code < 500 or attempt == 2:
                            break
                        self._sleep(0.1 * (2**attempt))
                    except Exception:
                        # An adapter failure must not prevent local logout.
                        break

            with self.store.locked(write=True) as state:
                client_id = state.get("active_client_id")
                registration = state["registrations"].get(client_id) if client_id else None
                if registration is not None:
                    self._clear_tokens(registration)
                state["connection_status"] = "disconnected"
                state["connection_version"] += 1
                state["notes_provider"] = None
                state["verification"] = None
                state.pop("last_provider_error", None)
                for session in state["sessions"].values():
                    if session.get("status") == "pending":
                        session["status"] = "cancelled"
                        session["error"] = None
                        self._clear_session_secrets(session)
        return {"status": "disconnected", "remote_revocation_confirmed": confirmed}
