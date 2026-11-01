"""Prove that a body-limited local tunnel accepts a large upload in chunks."""

from __future__ import annotations

import argparse
import http.client
import json
import socket
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import uvicorn

from asr_en_vi.app import create_app
from asr_en_vi.auth import AuthStore
from asr_en_vi.config import Settings

DEFAULT_CHUNK_BYTES = 64 * 1024**2
DEFAULT_EDGE_LIMIT = 100 * 1024**2


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _proxy_handler(backend_port: int, body_limit: int):
    class LimitedProxy(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: object) -> None:
            return

        def do_DELETE(self) -> None:
            self._forward()

        def do_GET(self) -> None:
            self._forward()

        def do_POST(self) -> None:
            self._forward()

        def do_PUT(self) -> None:
            self._forward()

        def _forward(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            if length > body_limit:
                body = json.dumps(
                    {"detail": {"code": "proxy_body_too_large", "limit_bytes": body_limit}}
                ).encode()
                self.send_response(413)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(body)
                return

            body = self.rfile.read(length) if length else None
            target = urlsplit(self.path)
            path = target.path or "/"
            if target.query:
                path += f"?{target.query}"
            headers = {
                key: value
                for key, value in self.headers.items()
                if key.lower() not in {"connection", "content-length", "host"}
            }
            headers["Host"] = self.headers.get("Host", f"127.0.0.1:{backend_port}")
            connection = http.client.HTTPConnection("127.0.0.1", backend_port, timeout=300)
            try:
                connection.request(self.command, path, body=body, headers=headers)
                response = connection.getresponse()
                response_body = response.read()
                self.send_response(response.status)
                for key, value in response.getheaders():
                    if key.lower() not in {"connection", "transfer-encoding", "content-length"}:
                        self.send_header(key, value)
                self.send_header("Content-Length", str(len(response_body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(response_body)
            finally:
                connection.close()

    return LimitedProxy


def _run_ffmpeg(path: Path, duration: int) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:sample_rate=48000:duration={duration}",
            "-c:a",
            "pcm_s16le",
            "-ac",
            "2",
            "-ar",
            "48000",
            str(path),
        ],
        check=True,
        timeout=300,
    )


def _assert(response: httpx.Response, expected: int) -> dict[str, object]:
    if response.status_code != expected:
        raise RuntimeError(f"expected HTTP {expected}, got {response.status_code}: {response.text}")
    if expected == 204:
        return {}
    return response.json()


def run(duration: int, edge_limit: int) -> None:
    with tempfile.TemporaryDirectory(prefix="asr-chunk-proof-") as temporary:
        root = Path(temporary)
        source = root / "large-proof.wav"
        _run_ffmpeg(source, duration)
        size = source.stat().st_size
        if size <= edge_limit:
            raise RuntimeError(f"generated media is only {size} bytes, need more than {edge_limit}")

        backend_port = _free_port()
        proxy = ThreadingHTTPServer(("127.0.0.1", 0), _proxy_handler(backend_port, edge_limit))
        proxy_url = f"http://127.0.0.1:{proxy.server_port}"
        settings = Settings(
            data_dir=root / "data",
            auth_dir=root / "auth",
            public_url=proxy_url,
            upload_chunk_bytes=DEFAULT_CHUNK_BYTES,
        )
        app_server = uvicorn.Server(
            uvicorn.Config(
                create_app(settings),
                host="127.0.0.1",
                port=backend_port,
                log_config=None,
                log_level="warning",
                access_log=False,
            )
        )
        backend_thread = threading.Thread(target=app_server.run, daemon=True)
        proxy_thread = threading.Thread(target=proxy.serve_forever, daemon=True)
        backend_thread.start()
        proxy_thread.start()
        try:
            deadline = threading.Event()
            for _ in range(200):
                if app_server.started:
                    break
                if deadline.wait(0.05):
                    break
            if not app_server.started:
                raise RuntimeError("the live backend did not start")

            auth = AuthStore(settings.auth_dir).load()
            headers = {"Origin": proxy_url}
            with httpx.Client(base_url=proxy_url, timeout=300, trust_env=False) as client:
                _assert(
                    client.post("/api/access/session", headers=headers, json={"token": auth.token}),
                    204,
                )
                probe = _assert(
                    client.post(
                        "/api/uploads",
                        headers=headers,
                        json={"filename": source.name, "size_bytes": size},
                    ),
                    201,
                )
                with source.open("rb") as stream:
                    oversized = stream.read(edge_limit + 1)
                rejected = client.put(
                    f"/api/uploads/{probe['id']}/content?offset=0",
                    headers=headers,
                    content=oversized,
                )
                if rejected.status_code != 413:
                    raise RuntimeError(f"proxy did not reject a large body: {rejected.status_code}")
                _assert(client.delete(f"/api/uploads/{probe['id']}", headers=headers), 200)
                oversized = None
                created = _assert(
                    client.post(
                        "/api/uploads",
                        headers=headers,
                        json={"filename": source.name, "size_bytes": size},
                    ),
                    201,
                )
                upload_id = str(created["id"])
                offset = 0
                chunks = 0
                with source.open("rb") as stream:
                    while chunk := stream.read(DEFAULT_CHUNK_BYTES):
                        transferred = _assert(
                            client.put(
                                f"/api/uploads/{upload_id}/content?offset={offset}",
                                headers=headers,
                                content=chunk,
                            ),
                            200,
                        )
                        offset = int(transferred["received_bytes"])
                        chunks += 1
                if offset != size:
                    raise RuntimeError(f"server committed {offset} of {size} bytes")
                ready = _assert(
                    client.post(f"/api/uploads/{upload_id}/complete", headers=headers), 200
                )
                meeting = _assert(
                    client.post(
                        "/api/meetings",
                        headers=headers,
                        json={
                            "upload_id": upload_id,
                            "title": "Chunk proxy proof",
                            "language_hint": "en",
                        },
                    ),
                    201,
                )
            print(
                json.dumps(
                    {
                        "proxy_body_limit_bytes": edge_limit,
                        "source_bytes": size,
                        "chunk_bytes": DEFAULT_CHUNK_BYTES,
                        "chunks": chunks,
                        "upload_status": ready["status"],
                        "meeting_id": meeting["id"],
                    },
                    sort_keys=True,
                )
            )
        finally:
            app_server.should_exit = True
            proxy.shutdown()
            backend_thread.join(timeout=10)
            proxy.server_close()
            proxy_thread.join(timeout=10)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--duration", type=int, default=960, help="Generated audio duration in seconds."
    )
    parser.add_argument("--edge-limit", type=int, default=DEFAULT_EDGE_LIMIT)
    args = parser.parse_args()
    run(args.duration, args.edge_limit)


if __name__ == "__main__":
    main()
