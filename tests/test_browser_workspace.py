from __future__ import annotations

import json
import os
import shutil
import socket
import threading
import time
import wave

import pytest
import uvicorn
from playwright.sync_api import expect, sync_playwright

from asr_en_vi.app import create_app
from asr_en_vi.auth import AuthStore
from asr_en_vi.config import Settings


@pytest.mark.browser
def test_managed_recording_upload_saves_and_restores_meeting(tmp_path):
    if os.environ.get("ASR_RUN_BROWSER_TESTS") != "1":
        pytest.skip("set ASR_RUN_BROWSER_TESTS=1 to run the real-browser workspace test")
    chrome_path = os.environ.get("CHROME_BIN") or shutil.which("google-chrome")

    recording_path = tmp_path / "short-meeting.wav"
    with wave.open(str(recording_path), "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(16_000)
        recording.writeframes(b"\x00\x00" * 16_000)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("127.0.0.1", 0))
    server_socket.listen()
    port = server_socket.getsockname()[1]
    public_url = f"http://127.0.0.1:{port}"
    settings = Settings(
        data_dir=tmp_path / "data",
        auth_dir=tmp_path / "auth",
        public_url=public_url,
    )
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(settings),
            log_config=None,
            log_level="warning",
            access_log=False,
        )
    )
    server_thread = threading.Thread(
        target=server.run,
        kwargs={"sockets": [server_socket]},
        daemon=True,
    )
    server_thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.025)
        assert server.started, "test server did not start"

        state = AuthStore(settings.auth_dir).load()
        link = f"{public_url}/access#{state.token}"
        api_requests: list[dict[str, object]] = []
        workspace_states: list[dict[str, object]] = []
        with sync_playwright() as playwright:
            launch_options = {"executable_path": chrome_path} if chrome_path else {}
            browser = playwright.chromium.launch(headless=True, **launch_options)
            context = browser.new_context()
            page = context.new_page()
            page.add_init_script(
                """
                window.__workspaceStates = [];
                const stateObserver = new MutationObserver(() => {
                  const dialog = document.querySelector("#meeting-dialog");
                  const createButton = document.querySelector("#create-meeting");
                  if (dialog && createButton) {
                    window.__workspaceStates.push({
                      state: dialog.dataset.state,
                      createDisabled: createButton.disabled,
                    });
                  }
                });
                stateObserver.observe(document, {
                  attributes: true,
                  attributeFilter: ["data-state", "disabled"],
                  childList: true,
                  subtree: true,
                });
                """
            )
            page.goto(link, wait_until="domcontentloaded")
            page.wait_for_url(f"{public_url}/", timeout=10_000)
            assert page.evaluate("window.location.hash") == ""
            cookie = next(
                cookie for cookie in context.cookies() if cookie["name"] == "asr_en_vi_session"
            )
            assert cookie["httpOnly"] is True
            assert cookie["sameSite"] == "Strict"

            def capture_request(request) -> None:
                if "/api/uploads" not in request.url and "/api/meetings" not in request.url:
                    return
                try:
                    headers = request.all_headers()
                except Exception:
                    headers = request.headers
                api_requests.append(
                    {
                        "method": request.method,
                        "url": request.url,
                        "post_data": request.post_data,
                        "headers": headers,
                    }
                )

            page.on("request", capture_request)
            page.get_by_role("button", name="Cuộc họp mới").first.click()
            dialog = page.get_by_role("dialog", name="Cuộc họp mới")
            expect(dialog).to_be_visible()
            file_input = page.locator("#recording-file")
            expect(file_input).to_be_enabled(timeout=10_000)
            accept = file_input.get_attribute("accept")
            assert accept and ".wav" in accept.lower(), "upload policy must publish WAV support"
            limits = page.locator("#file-limits").inner_text()
            assert "Tối đa" in limits and "Định dạng" in limits

            file_input.set_input_files(str(recording_path))
            expect(page.locator("#selected-file-name")).to_have_text(recording_path.name)
            page.locator("#meeting-name").fill("Điều phối sản phẩm — tuần 42")
            page.locator("#meeting-date-input").fill("2026-10-15")
            page.locator('input[name="language_hint"][value="en"]').check()
            create_button = page.get_by_role("button", name="Tạo cuộc họp")
            expect(create_button).to_be_disabled()

            page.route("**/api/uploads/*/content", lambda route: route.abort("connectionfailed"))
            page.get_by_role("button", name="Tải lên và kiểm tra").click()
            expect(dialog).to_have_attribute("data-state", "error", timeout=10_000)
            expect(page.locator("#form-error")).to_contain_text("Không tạo cuộc họp")
            retry_button = page.get_by_role("button", name="Tải lại từ đầu")
            expect(retry_button).to_be_visible()
            page.unroute("**/api/uploads/*/content")
            retry_button.click()
            expect(dialog).to_have_attribute("data-state", "ready", timeout=20_000)
            expect(create_button).to_be_enabled()

            state_snapshots = page.evaluate("window.__workspaceStates")
            workspace_states.extend(state_snapshots)
            states = {snapshot["state"] for snapshot in workspace_states}
            assert "uploading" in states
            assert "checking" in states
            for state_name in ("uploading", "checking"):
                assert any(
                    snapshot["state"] == state_name and snapshot["createDisabled"]
                    for snapshot in workspace_states
                ), f"Create must stay disabled during {state_name}"
            assert any(
                snapshot["state"] == "ready" and not snapshot["createDisabled"]
                for snapshot in workspace_states
            ), "Create should unlock only after the upload is ready and fields are valid"
            pre_restart_content_paths = [
                request["url"].removeprefix(public_url)
                for request in api_requests
                if request["method"] == "PUT" and request["url"].endswith("/content")
            ]
            assert len(pre_restart_content_paths) == 2
            interrupted_upload_id = pre_restart_content_paths[0].split("/")[3]
            interrupted_state = context.request.get(
                f"{public_url}/api/uploads/{interrupted_upload_id}"
            )
            assert interrupted_state.status == 200
            assert interrupted_state.json()["status"] == "failed"
            assert not (settings.data_dir / "uploads" / f"{interrupted_upload_id}.part").exists()

            def commit_meeting_then_drop_response(route) -> None:
                response = route.fetch()
                assert response.status == 201
                route.abort("connectionfailed")

            page.route("**/api/meetings", commit_meeting_then_drop_response)
            create_button.click()
            expect(dialog).to_have_attribute("data-state", "error", timeout=10_000)
            retry_create = page.get_by_role("button", name="Xác minh và thử lại")
            expect(retry_create).to_be_enabled()
            expect(page.locator("#close-dialog")).to_be_enabled()
            expect(page.locator("#meeting-name")).to_be_disabled()
            page.unroute("**/api/meetings")
            retry_create.click()
            page.wait_for_url(f"{public_url}/meetings/*", timeout=10_000)
            meeting_id = page.url.rstrip("/").rsplit("/", maxsplit=1)[-1]
            expect(page.locator("#meeting-title")).to_have_text("Điều phối sản phẩm — tuần 42")
            expect(page.locator("#meeting-date")).to_have_attribute("datetime", "2026-10-15")
            expect(page.locator("#meeting-language")).to_have_text("English")
            expect(page.get_by_text("Đã lưu, chưa xử lý", exact=True)).to_be_visible()
            audio = page.locator("#meeting-audio")
            expect(audio).to_be_visible()
            assert audio.evaluate("element => element.controls") is True
            assert audio.get_attribute("src") == f"/api/meetings/{meeting_id}/audio"
            media_deadline = time.monotonic() + 10
            ready_state = audio.evaluate("element => element.readyState")
            while ready_state < 1 and time.monotonic() < media_deadline:
                time.sleep(0.1)
                ready_state = audio.evaluate("element => element.readyState")
            media_error = audio.evaluate(
                "element => element.error ? element.error.message || element.error.code : null"
            )
            assert ready_state >= 1, (
                f"native audio did not load metadata; media error: {media_error}"
            )
            seek_result = audio.evaluate(
                """
                async element => {
                  let seeked = false;
                  if (Number.isFinite(element.duration) && element.duration > 0.25) {
                    const seekedEvent = new Promise(resolve =>
                      element.addEventListener("seeked", () => resolve(true), { once: true })
                    );
                    element.currentTime = Math.min(0.25, element.duration / 2);
                    seeked = await Promise.race([
                      seekedEvent,
                      new Promise(resolve => setTimeout(() => resolve(false), 1000)),
                    ]);
                  }
                  return { currentTime: element.currentTime, seeked };
                }
                """
            )
            assert seek_result["seeked"] is True
            assert seek_result["currentTime"] > 0

            authenticated_range = context.request.get(
                f"{public_url}/api/meetings/{meeting_id}/audio",
                headers={"Range": "bytes=0-5"},
            )
            assert authenticated_range.status == 206
            assert len(authenticated_range.body()) == 6
            assert authenticated_range.headers["content-range"].startswith("bytes 0-5/")
            unauthenticated_context = browser.new_context()
            try:
                unauthenticated_audio = unauthenticated_context.request.get(
                    f"{public_url}/api/meetings/{meeting_id}/audio"
                )
                assert unauthenticated_audio.status == 401
            finally:
                unauthenticated_context.close()

            server.should_exit = True
            server_thread.join(timeout=5)
            assert not server_thread.is_alive(), "test server did not stop for restart"
            server_socket.close()
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(("127.0.0.1", port))
            server_socket.listen()
            server = uvicorn.Server(
                uvicorn.Config(
                    create_app(settings),
                    log_config=None,
                    log_level="warning",
                    access_log=False,
                )
            )
            server_thread = threading.Thread(
                target=server.run,
                kwargs={"sockets": [server_socket]},
                daemon=True,
            )
            server_thread.start()
            restart_deadline = time.monotonic() + 10
            while not server.started and time.monotonic() < restart_deadline:
                time.sleep(0.025)
            assert server.started, "test server did not restart"

            page.reload(wait_until="domcontentloaded")
            expect(page.locator("#meeting-title")).to_have_text("Điều phối sản phẩm — tuần 42")
            expect(page.locator("#meeting-date")).to_have_attribute("datetime", "2026-10-15")
            expect(page.locator("#meeting-language")).to_have_text("English")
            expect(page.locator("#meeting-audio")).to_be_visible()

            methods_and_paths = [
                (request["method"], request["url"].removeprefix(public_url))
                for request in api_requests
            ]
            content_paths = [
                path
                for method, path in methods_and_paths
                if method == "PUT" and path.endswith("/content")
            ]
            complete_path = next(
                path
                for method, path in methods_and_paths
                if method == "POST" and path.endswith("/complete")
            )
            upload_id = complete_path.split("/")[3]
            assert ("GET", "/api/uploads/policy") in methods_and_paths
            assert methods_and_paths.count(("POST", "/api/uploads")) == 2
            assert len(content_paths) == 2
            assert content_paths[0] != content_paths[1]
            assert f"/api/uploads/{upload_id}/content" in content_paths
            assert complete_path == f"/api/uploads/{upload_id}/complete"
            assert methods_and_paths.count(("POST", "/api/meetings")) == 2
            assert ("GET", f"/api/meetings/{meeting_id}") in methods_and_paths
            assert ("GET", f"/api/meetings/{meeting_id}/audio") in methods_and_paths

            meeting_request = next(
                request
                for request in api_requests
                if request["method"] == "POST" and request["url"].endswith("/api/meetings")
            )
            meeting_payload = json.loads(str(meeting_request["post_data"]))
            assert meeting_payload == {
                "upload_id": upload_id,
                "title": "Điều phối sản phẩm — tuần 42",
                "meeting_date": "2026-10-15",
                "language_hint": "en",
            }
            upload_requests = [
                request
                for request in api_requests
                if request["method"] == "POST" and request["url"].endswith("/api/uploads")
            ]
            assert len(upload_requests) == 2
            for upload_request in upload_requests:
                upload_payload = json.loads(str(upload_request["post_data"]))
                assert upload_payload == {
                    "filename": recording_path.name,
                    "size_bytes": recording_path.stat().st_size,
                }

            browser.close()
    finally:
        server.should_exit = True
        server_thread.join(timeout=5)
        server_socket.close()
