"""Measure Chromium memory while the browser extracts audio from a long video."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import uvicorn
from playwright.sync_api import expect, sync_playwright

from asr_studio.app import create_app
from asr_studio.auth import AuthStore
from asr_studio.config import Settings


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _make_video(path: Path, duration: int) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size=160x90:rate=1:duration={duration}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:sample_rate=48000:duration={duration}",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-b:v",
            "100k",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            str(path),
        ],
        check=True,
        timeout=600,
    )


def _process_tree(root_pid: int) -> set[int]:
    parents = {}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / "stat").read_text(encoding="utf-8").split()
            parents[int(entry.name)] = int(fields[3])
        except (FileNotFoundError, ValueError):
            continue
    tree = {root_pid}
    changed = True
    while changed:
        changed = False
        for pid, parent in parents.items():
            if parent in tree and pid not in tree:
                tree.add(pid)
                changed = True
    return tree


def _rss_bytes(root_pid: int) -> int:
    total = 0
    for pid in _process_tree(root_pid):
        try:
            for line in (
                (Path("/proc") / str(pid) / "status").read_text(encoding="utf-8").splitlines()
            ):
                if line.startswith("VmRSS:"):
                    total += int(line.split()[1]) * 1024
                    break
        except (FileNotFoundError, ValueError):
            continue
    return total


def _js_memory(page) -> dict[str, int | None]:
    value = page.evaluate(
        """
        () => performance.memory ? {
          used_js_heap_bytes: performance.memory.usedJSHeapSize,
          total_js_heap_bytes: performance.memory.totalJSHeapSize,
        } : {used_js_heap_bytes: null, total_js_heap_bytes: null}
        """
    )
    return value


def run(duration: int) -> None:
    with tempfile.TemporaryDirectory(prefix="asr-memory-proof-") as temporary:
        root = Path(temporary)
        video = root / "long-memory-proof.mp4"
        _make_video(video, duration)
        settings = Settings(
            data_dir=root / "data",
            auth_dir=root / "auth",
            public_url=f"http://127.0.0.1:{_free_port()}",
        )
        server = uvicorn.Server(
            uvicorn.Config(
                create_app(settings),
                host="127.0.0.1",
                port=int(settings.public_url.rsplit(":", 1)[1]),
                log_config=None,
                log_level="warning",
                access_log=False,
            )
        )
        server_thread = threading.Thread(target=server.run, daemon=True)
        server_thread.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started and time.monotonic() < deadline:
                time.sleep(0.025)
            if not server.started:
                raise RuntimeError("the memory-measurement server did not start")

            with sync_playwright() as playwright:
                chrome_path = shutil.which("google-chrome")
                launch = {"executable_path": chrome_path} if chrome_path else {}
                launch["args"] = ["--enable-precise-memory-info"]
                browser = playwright.chromium.launch(headless=True, **launch)
                try:
                    driver_pid = browser._impl_obj._channel._connection._transport._proc.pid
                    context = browser.new_context()
                    page = context.new_page()
                    page.goto(
                        f"{settings.public_url}/access#{AuthStore(settings.auth_dir).load().token}",
                        wait_until="domcontentloaded",
                    )
                    page.wait_for_url(f"{settings.public_url}/", timeout=10_000)
                    before = {"rss_bytes": _rss_bytes(driver_pid), **_js_memory(page)}
                    chunks: list[tuple[int, int]] = []
                    held = []
                    page.expose_function(
                        "recordExtractChunk",
                        lambda offset, size: chunks.append((int(offset), int(size))),
                    )
                    page.evaluate(
                        """
                        (() => {
                          const open = XMLHttpRequest.prototype.open;
                          const send = XMLHttpRequest.prototype.send;
                          XMLHttpRequest.prototype.open = function (method, url, ...rest) {
                            this.__uploadUrl = url;
                            return open.call(this, method, url, ...rest);
                          };
                          XMLHttpRequest.prototype.send = function (body) {
                            if (
                              body instanceof Blob
                              && this.__uploadUrl.includes('/content?offset=')
                            ) {
                              const offset = new URL(this.__uploadUrl, location.href)
                                .searchParams.get('offset');
                              window.recordExtractChunk(offset, body.size);
                            }
                            return send.call(this, body);
                          };
                        })()
                        """
                    )
                    upload_pattern = re.compile(r".*/api/uploads/[0-9a-f]+/content\?offset=\d+$")

                    def hold_first(route):
                        if held:
                            route.continue_()
                        else:
                            held.append(route)

                    page.route(upload_pattern, hold_first)
                    page.get_by_role("button", name="Cuộc họp mới").first.click()
                    expect(page.locator("#recording-file")).to_be_enabled(timeout=10_000)
                    page.locator("#recording-file").set_input_files(str(video))
                    page.wait_for_function(
                        "document.querySelector('#meeting-name')?.value.length > 0"
                    )
                    page.locator('input[name="language_hint"][value="en"]').check()
                    page.locator("#auto-transcribe").set_checked(False)
                    page.get_by_role("button", name="Tạo cuộc họp").click()
                    deadline = time.monotonic() + max(120, duration // 2)
                    while not held and time.monotonic() < deadline:
                        page.wait_for_timeout(100)
                    if not held:
                        raise RuntimeError("the browser did not reach the first upload chunk")
                    after = {"rss_bytes": _rss_bytes(driver_pid), **_js_memory(page)}
                    held[0].continue_()
                    page.unroute(upload_pattern)
                    page.wait_for_url(re.compile(r".*/meetings/[0-9a-f]+$"), timeout=120_000)
                    page.wait_for_timeout(100)
                    extracted_bytes = sum(size for _, size in chunks)
                    output = {
                        "duration_seconds": duration,
                        "source_bytes": video.stat().st_size,
                        "extracted_upload_bytes": extracted_bytes,
                        "four_hour_linear_upload_bytes": round(
                            extracted_bytes * 4 * 3600 / duration
                        ),
                        "before": before,
                        "after_extraction": after,
                        "rss_delta_bytes": after["rss_bytes"] - before["rss_bytes"],
                        "js_heap_delta_bytes": (
                            after["used_js_heap_bytes"] - before["used_js_heap_bytes"]
                            if after["used_js_heap_bytes"] is not None
                            and before["used_js_heap_bytes"] is not None
                            else None
                        ),
                    }
                    print(json.dumps(output, sort_keys=True))
                finally:
                    browser.close()
        finally:
            server.should_exit = True
            server_thread.join(timeout=10)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=int, default=3600)
    args = parser.parse_args()
    run(args.duration)


if __name__ == "__main__":
    main()
