from __future__ import annotations

import threading
from collections import deque
from typing import Any

from asr_studio.chatgpt import ChatGPTError, VerifiedIdentity


class FakeChatGPTAdapter:
    """Deterministic provider boundary for lifecycle and HTTP contract tests."""

    def __init__(self) -> None:
        self.subject = "chatgpt-subject-123"
        self.email = "verified@example.test"
        self.email_verified = True
        self.scopes = (
            "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
        )
        self.exchange_calls: list[dict[str, str]] = []
        self.refresh_calls: list[dict[str, str]] = []
        self.model_calls: list[str] = []
        self.verify_calls: list[dict[str, str]] = []
        self.revoke_calls: list[dict[str, str]] = []
        self.refresh_results: deque[dict[str, Any] | ChatGPTError] = deque()
        self.models_error: ChatGPTError | None = None
        self.verify_error: ChatGPTError | None = None
        self.revoke_results: deque[bool | ChatGPTError] = deque([True])
        self.exchange_error: ChatGPTError | None = None
        self.exchange_started = threading.Event()
        self.exchange_release = threading.Event()
        self.exchange_release.set()
        self.verification_started = threading.Event()
        self.verification_release = threading.Event()
        self.verification_release.set()

    def exchange_code(
        self, *, code: str, verifier: str, redirect_uri: str, client_id: str
    ) -> dict[str, Any]:
        self.exchange_calls.append(
            {
                "code": code,
                "verifier": verifier,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
            }
        )
        self.exchange_started.set()
        if not self.exchange_release.is_set():
            self.exchange_release.wait(timeout=5)
        if self.exchange_error is not None:
            raise self.exchange_error
        return {
            "access_token": "access-secret-for-tests",
            "refresh_token": "refresh-secret-for-tests",
            "id_token": "signed-id-token-for-tests",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": self.scopes,
        }

    def validate_identity(self, id_token: str, *, client_id: str, nonce: str) -> VerifiedIdentity:
        assert id_token == "signed-id-token-for-tests"
        assert client_id != "dynamic_agent_client"
        assert nonce
        return VerifiedIdentity(self.subject, self.email, self.email_verified)

    def refresh(self, *, client_id: str, refresh_token: str) -> dict[str, Any]:
        self.refresh_calls.append({"client_id": client_id, "refresh_token": refresh_token})
        if self.refresh_results:
            result = self.refresh_results.popleft()
            if isinstance(result, ChatGPTError):
                raise result
            return result
        return {
            "access_token": "rotated-access-secret",
            "refresh_token": "rotated-refresh-secret",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": self.scopes,
        }

    def list_models(self, *, access_token: str) -> list[dict[str, Any]]:
        self.model_calls.append(access_token)
        if self.models_error is not None:
            raise self.models_error
        return [
            {"slug": "gpt-6.1-sol", "display_name": "GPT 6.1 Sol", "visibility": "list"},
            {"slug": "gpt-hidden", "display_name": "Hidden", "visibility": "private"},
            {"slug": "gpt-6-luna", "display_name": "GPT 6 Luna", "visibility": "list"},
            {"slug": "gpt-5.6-luna", "display_name": "GPT-5.6 Luna", "visibility": "list"},
        ]

    def verify(self, *, access_token: str, model: str, reasoning_effort: str = "default") -> None:
        self.verify_calls.append(
            {"access_token": access_token, "model": model, "reasoning_effort": reasoning_effort}
        )
        self.verification_started.set()
        if not self.verification_release.is_set():
            self.verification_release.wait(timeout=5)
        if self.verify_error is not None:
            raise self.verify_error

    def revoke(self, *, client_id: str, refresh_token: str) -> bool:
        self.revoke_calls.append({"client_id": client_id, "refresh_token": refresh_token})
        if self.revoke_results:
            result = self.revoke_results.popleft()
            if isinstance(result, ChatGPTError):
                raise result
            return result
        return True
