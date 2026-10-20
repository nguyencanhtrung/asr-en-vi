#!/usr/bin/env python3
"""Check test prerequisites with bounded probes before running the suite."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path


def probe(name: str) -> None:
    if name == "cache":
        cache = os.environ.get("UV_CACHE_DIR")
        if not cache:
            cache = subprocess.check_output(["uv", "cache", "dir"], text=True, timeout=5).strip()
        directory = Path(cache)
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=directory) as stream:
            stream.write(b"cache probe")
            stream.flush()
    elif name == "socket":
        with socket.socket() as server, socket.socket() as client:
            server.settimeout(2)
            client.settimeout(2)
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            client.connect(server.getsockname())
            connection, _ = server.accept()
            with connection:
                connection.settimeout(2)
                client.sendall(b"ok")
                if connection.recv(2) != b"ok":
                    raise RuntimeError("Loopback socket did not deliver data")
    elif name == "async-file":
        asyncio.run(probe_async_file())


async def probe_async_file() -> None:
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from starlette.responses import FileResponse

    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "probe.txt"
        path.write_text("file response ok", encoding="utf-8")
        app = FastAPI()

        @app.get("/")
        async def serve():
            return FileResponse(path)

        async with AsyncClient(transport=ASGITransport(app), base_url="http://probe") as client:
            response = await client.get("/")
            if response.status_code != 200 or response.text != "file response ok":
                raise RuntimeError("Async FileResponse did not deliver expected data")


def check(names: list[str], timeout: float) -> dict:
    checks = []
    for name in names:
        try:
            result = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--probe", name],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            checks.append(
                {
                    "probe": name,
                    "status": "pass" if result.returncode == 0 else "blocked",
                    "detail": result.stderr.strip()[-1000:] if result.returncode else "",
                }
            )
        except subprocess.TimeoutExpired:
            checks.append({"probe": name, "status": "blocked", "detail": "deadline exceeded"})
    blocked = any(item["status"] == "blocked" for item in checks)
    return {
        "status": "blocked" if blocked else "pass",
        "category": "test_environment",
        "checks": checks,
        "next_action": (
            "Check sandbox socket/async-file permissions and UV_CACHE_DIR; "
            "rerun the failing probe in an authorized environment before the suite."
            if blocked
            else "Run repository checks."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-only", action="store_true")
    parser.add_argument("--probe", choices=("cache", "socket", "async-file"))
    parser.add_argument("--timeout", type=float, default=10)
    args = parser.parse_args()
    if not 0 < args.timeout <= 60:
        parser.error("timeout must be positive and at most 60 seconds")
    if args.probe:
        try:
            probe(args.probe)
            return 0
        except (OSError, RuntimeError, ImportError, subprocess.SubprocessError) as error:
            print(f"{type(error).__name__}: {error}", file=sys.stderr)
            return 1
    value = check(["cache"] if args.cache_only else ["cache", "socket", "async-file"], args.timeout)
    print(json.dumps(value))
    return 1 if value["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
