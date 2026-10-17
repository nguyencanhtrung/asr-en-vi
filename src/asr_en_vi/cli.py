"""Local operator commands for access credentials and runtime preflight checks."""

from __future__ import annotations

import argparse
import ctypes
import sys
from urllib.error import URLError
from urllib.request import Request, urlopen

import ctranslate2
import qrcode
from qrcode.constants import ERROR_CORRECT_M

from asr_en_vi import __version__
from asr_en_vi.auth import AuthState, AuthStore
from asr_en_vi.config import Settings
from asr_en_vi.runner import ModelConfigurationError, prepared_model_directory
from asr_en_vi.runtime import MODEL_REPOSITORIES, RuntimeConfigurationError, select_runtime


def access_link(state: AuthState, settings: Settings) -> str:
    return f"{settings.access_url_prefix}{state.token}"


def print_qr_code(value: str) -> None:
    qr_code = qrcode.QRCode(error_correction=ERROR_CORRECT_M, border=2, box_size=1)
    qr_code.add_data(value)
    qr_code.make(fit=True)
    for row in qr_code.get_matrix():
        print("".join("██" if cell else "  " for cell in row))


def print_access_details(state: AuthState, settings: Settings, *, rotated: bool = False) -> None:
    if rotated:
        print("Access token rotated. Previous links and sessions are invalid.")
        print()
    print("Local access link:")
    print(access_link(state, settings))
    print()
    print("Scan or save this QR code:")
    print_qr_code(access_link(state, settings))


def check_health(settings: Settings) -> int:
    request = Request(
        "http://127.0.0.1:8765/healthz",
        headers={"Host": settings.host_header},
    )
    try:
        with urlopen(request, timeout=2) as response:
            return 0 if response.status == 200 else 1
    except (OSError, URLError):
        return 1


def _select_runtime(settings: Settings, *, require_model: bool = True):
    try:
        return select_runtime(
            settings,
            get_cuda_device_count=ctranslate2.get_cuda_device_count,
            load_library=ctypes.CDLL,
            get_supported_compute_types=ctranslate2.get_supported_compute_types,
            require_model=require_model,
        )
    except RuntimeConfigurationError as error:
        print(str(error), file=sys.stderr)
        return None


def check_model(settings: Settings) -> int:
    profile = _select_runtime(settings)
    if profile is None:
        return 1
    print(f"Local ASR model is ready: {profile.model_path}")
    return 0


def prepare_model(settings: Settings) -> int:
    profile = _select_runtime(settings, require_model=False)
    if profile is None:
        return 1
    try:
        prepared_model_directory(profile.model_path)
        print(f"Local ASR model is ready: {profile.model_path}")
        return 0
    except ModelConfigurationError:
        pass

    repository = MODEL_REPOSITORIES[profile.device]
    print(f"Downloading {repository} to {profile.model_path}...")
    try:
        from huggingface_hub import snapshot_download

        snapshot_download(repo_id=repository, local_dir=profile.model_path)
        prepared_model_directory(profile.model_path)
    except (OSError, RuntimeError, ValueError, ModelConfigurationError) as error:
        print(
            f"Could not prepare local ASR model at {profile.model_path}: {error}",
            file=sys.stderr,
        )
        return 1
    print(f"Local ASR model is ready: {profile.model_path}")
    return 0


def check_runtime(settings: Settings) -> int:
    profile = _select_runtime(settings)
    if profile is None:
        return 1
    if profile.device == "cuda":
        print(
            f"NVIDIA GPU is ready; local ASR model: {profile.model_path} ({profile.compute_type})"
        )
    else:
        print(
            f"CPU fallback is ready; local ASR model: {profile.model_path} ({profile.compute_type})"
        )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="asr-en-vi")
    parser.add_argument("--version", action="version", version=f"asr-en-vi {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    access_parser = commands.add_parser("access", help="manage the local access token")
    access_commands = access_parser.add_subparsers(dest="access_command", required=True)
    access_commands.add_parser("show", help="print the current access link and QR code")
    access_commands.add_parser("rotate", help="replace the token and invalidate old sessions")
    commands.add_parser("health", help="check the local app liveness endpoint")
    model_parser = commands.add_parser("model", help="validate local ASR model resources")
    model_commands = model_parser.add_subparsers(dest="model_command", required=True)
    model_commands.add_parser("check", help="validate the configured local ASR model")
    model_commands.add_parser("prepare", help="download the selected local ASR model if needed")
    runtime_parser = commands.add_parser("runtime", help="validate local ASR execution")
    runtime_commands = runtime_parser.add_subparsers(dest="runtime_command", required=True)
    runtime_commands.add_parser("check", help="validate the model and compute runtime")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    settings = Settings.from_env()
    if arguments.command == "health":
        return check_health(settings)
    if arguments.command == "model":
        if arguments.model_command == "prepare":
            return prepare_model(settings)
        return check_model(settings)
    if arguments.command == "runtime":
        return check_runtime(settings)

    store = AuthStore(settings.auth_dir)
    if arguments.access_command == "show":
        print_access_details(store.ensure(), settings)
        return 0
    if arguments.access_command == "rotate":
        print_access_details(store.rotate(), settings, rotated=True)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
