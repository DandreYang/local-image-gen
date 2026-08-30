#!/usr/bin/env python3
"""Local studio for local-image-gen. Stdlib only. Default bind is loopback."""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import mimetypes
import os
import re
import shutil
import struct
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

from director import look_at_image
from job import brief as build_brief, merge_revision_draft, provider_allowed_aspects
from snippets import add_snippet, color_sentence, delete_snippet, list_snippets as load_snippets
import local_image_gen as cli

WORKSPACE = Path(__file__).resolve().parents[1]
CLI = WORKSPACE / "scripts" / "local_image_gen.py"
CLIENT = Path(__file__).resolve().parent / "client"
STUDIO_API_PREFIX = "/studio-api"


def studio_fixture_enabled() -> bool:
    return os.environ.get("LOCAL_IMAGE_GEN_STUDIO_FIXTURE", "").strip().lower() in {"1", "true", "yes"}


def fixture_outputs_root() -> Path:
    """Fixture runs get their own store so canned images never touch the real library."""
    return (cli.default_share_home() / "fixture-outputs").resolve()


def _fixture_requested_before_import() -> bool:
    if studio_fixture_enabled():
        return True
    return Path(sys.argv[0]).name == "server.py" and "--fixture" in sys.argv[1:]


def resolve_outputs_root() -> Path:
    """Studio storage follows the CLI: workspace/outputs → ~/.local-image-gen store.

    Priority: explicit Studio override > fixture store > CLI store override >
    Dyro workspace store > package-local ``outputs``. Overrides are used as-is
    and never re-point a workspace ``outputs`` link.
    """
    override = os.environ.get("LOCAL_IMAGE_GEN_STUDIO_OUTPUTS", "").strip()
    if override:
        return Path(os.path.expanduser(override)).resolve()
    if _fixture_requested_before_import():
        return fixture_outputs_root()
    for start in (Path.cwd(), WORKSPACE):
        found = cli.find_dyro_workspace(start)
        if found is not None:
            name = cli.dyro_workspace_name(found) or found.name
            store = cli.generated_images_root(name)
            if cli.outputs_store_overridden():
                # Explicit store override: a pure sink, never touches the workspace link.
                return store
            return cli.workspace_outputs_dir(found, store)
    return WORKSPACE / "outputs"


OUTPUTS = resolve_outputs_root()
IMAGE_DIR = OUTPUTS / "images"
JOB_DIR = OUTPUTS / ".jobs"


def ensure_private_storage_root(root: Path, images: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    images.mkdir(parents=True, exist_ok=True)
    for path in (root, images):
        try:
            os.chmod(path, 0o700)
        except OSError:
            pass


def fixture_png_bytes() -> bytes:
    width, height = 64, 64
    raw = b"".join(b"\x00" + (b"\x70\x88\xa0" * width) for _ in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
INBOX = IMAGE_DIR / "inbox"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"
OVERLAY_MAX_BYTES = 20 * 1024 * 1024
COMPOSITE_MAX_BYTES = 40 * 1024 * 1024
OVERLAY_DIR = OUTPUTS / "overlays"
MASK_DIR = OUTPUTS / ".masks"
PROJECTS_DIR = OUTPUTS / "projects"
THUMB_DIR = OUTPUTS / ".thumbs"
TRASH_DIR = OUTPUTS / ".trash"
INDEX_PATH = OUTPUTS / ".index.json"
PROJECT_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
STATIC_MIME = {
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
}
HOST = "127.0.0.1"
DEFAULT_PORT = 8765
LAN_WARNING = "warning: LAN bind shares this machine's image backends with the network."
MAX_PARALLEL = 2
MAX_JSON_BYTES = 10 * 1024 * 1024
MAX_BATCH_JOBS = 24
MAX_ACTIVE_BATCHES = 2
STUDIO_TOKEN: Optional[str] = None
STUDIO_TOKEN_HEADER = "X-Studio-Token"
BIND_HOST = HOST
_BATCH_DIR = OUTPUTS / ".batches"
BATCH_DIR = _BATCH_DIR
_BATCHES: Dict[str, Dict[str, Any]] = {}
_BATCH_LOCK = threading.Lock()
_BATCHES_LOADED = False


_STATIC_LOOPBACK_NAMES = {"127.0.0.1", "::1", "localhost", "0.0.0.0", "::"}


def primary_lan_ipv4() -> Optional[str]:
    """Best-effort local IPv4 without blocking on hostname/mDNS lookup."""
    try:
        import socket as _socket

        with _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = str(sock.getsockname()[0] or "")
            return ip or None
    except OSError:
        return None


def loopback_hostnames() -> "set[str]":
    names = set(_STATIC_LOOPBACK_NAMES)
    lan_ip = primary_lan_ipv4()
    if lan_ip:
        names.add(lan_ip)
    return names


def bound_addresses(bind_host: str) -> "set[str]":
    """Addresses a client can actually reach when we bind ``bind_host``."""
    if bind_host in {"0.0.0.0", "::"}:
        return loopback_hostnames() | {"*"}
    if bind_host in _STATIC_LOOPBACK_NAMES:
        return set(_STATIC_LOOPBACK_NAMES)
    return set(_STATIC_LOOPBACK_NAMES) | {bind_host}


def host_allows(host_header: Any, bind_host: str) -> bool:
    """Board 2026-08-23 P0-A: the Host header must name an address we really bound.

    DNS-rebinding attacks win by making the browser send an attacker-chosen
    Host to a same-origin-seeming request; comparing against the bound
    addresses closes that. Host is optional for CLI clients (no header).
    """
    if not host_header:
        return True
    raw = str(host_header).strip()
    if not raw:
        return False
    netloc = (urlparse(f"//{raw}" if "//" not in raw else raw).netloc or raw).lower()
    hostname = netloc.rsplit(":", 1)[0].strip("[]") if netloc else ""
    if not hostname:
        return False
    allowed_names = {item.lower() for item in bound_addresses(bind_host)}
    if "*" in allowed_names:
        return True
    try:
        import ipaddress as _ipaddress

        candidate = _ipaddress.ip_address(hostname)
        allowed: "set[str]" = set()
        for item in allowed_names:
            try:
                allowed.add(str(_ipaddress.ip_address(item.strip("[]"))))
            except ValueError:
                allowed.add(item)
        return str(candidate) in allowed
    except ValueError:
        return hostname in allowed_names


def issue_studio_token() -> str:
    global STUDIO_TOKEN
    import secrets as _secrets

    STUDIO_TOKEN = _secrets.token_urlsafe(24)
    return STUDIO_TOKEN


def studio_token_required(bind_host: str) -> bool:
    return bind_host not in {"127.0.0.1", "::1", "localhost"}


def studio_token_ok(headers: Any, *, client_host: str = "", request_path: str = "") -> bool:
    if STUDIO_TOKEN is None:
        return True
    if request_path == "/api/runtime" and client_host:
        try:
            import ipaddress as _ipaddress

            if _ipaddress.ip_address(client_host).is_loopback:
                return True
        except ValueError:
            pass
    supplied = str(headers.get(STUDIO_TOKEN_HEADER) or "").strip()
    if not supplied:
        cookie = str(headers.get("Cookie") or "")
        match = re.search(r"(?:^|;\s*)studio_token=([A-Za-z0-9_\-]+)", cookie)
        supplied = match.group(1) if match else ""
    import hmac as _hmac

    return bool(supplied) and _hmac.compare_digest(supplied, STUDIO_TOKEN)


def public_studio_url(host: str, port: int) -> str:
    if host in {"0.0.0.0", "::"}:
        return f"http://127.0.0.1:{port}"
    return f"http://{host}:{port}"


def print_studio_banner(host: str, port: int) -> None:
    if host in {"0.0.0.0", "::"}:
        print(f"local studio  http://127.0.0.1:{port}", flush=True)
        for url in cli.lan_studio_urls(port):
            print(f"LAN          {url}", flush=True)
        print(LAN_WARNING, flush=True)
    else:
        print(f"local studio  http://{host}:{port}", flush=True)
    try:
        resolved = OUTPUTS.resolve()
    except OSError:
        resolved = OUTPUTS
    if resolved != OUTPUTS:
        print(f"outputs      {OUTPUTS} -> {resolved}", flush=True)
    else:
        print(f"outputs      {OUTPUTS}", flush=True)
    if studio_fixture_enabled():
        print("fixture      on  (no model quota; canned images stay in the fixture store above)", flush=True)


def maybe_open_browser(url: str, *, open_browser: bool) -> None:
    if not open_browser:
        return
    try:
        webbrowser.open(url)
    except Exception as exc:
        print(f"warning: could not open browser: {exc}", flush=True)


def json_bytes(payload: Any, status: int = 200) -> tuple[int, bytes, str]:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    return status, body, "application/json; charset=utf-8"


def parse_cli_json(text: str) -> Optional[Dict[str, Any]]:
    blob = (text or "").strip()
    if not blob:
        return None
    for candidate in reversed(blob.splitlines()):
        candidate = candidate.strip()
        if not candidate.startswith("{"):
            continue
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def studio_doctor_payload(*, skip_update_check: bool = True) -> Dict[str, Any]:
    payload = run_cli(["doctor"], timeout=25, skip_update_check=skip_update_check)
    providers = payload.get("providers")
    if isinstance(providers, list):
        payload["providers"] = annotate_studio_providers(providers)
    payload["studio_runtime"] = {
        "fixture": studio_fixture_enabled(),
        "bind_host": BIND_HOST,
        "outputs_root": str(OUTPUTS),
    }
    return payload


STUDIO_UNSAFE_AGENT_PROVIDERS = {"agy", "antigravity", "cursor"}
STUDIO_SAFE_PROVIDER_ORDER = ("grok", "codex", "gemini", "xai", "openai")

# Aspects a provider can actually draw live in one place (studio/job.py) so the
# brief, the confirm gate and the model catalog can never disagree.
def provider_aspects(provider: Any) -> Tuple[str, ...]:
    return provider_allowed_aspects(str(provider or ""))


def studio_provider_allowed(provider: Any) -> bool:
    return str(provider or "").strip().lower() not in STUDIO_UNSAFE_AGENT_PROVIDERS


def annotate_studio_providers(providers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for raw in providers:
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        enabled = studio_provider_allowed(row.get("provider"))
        row["studio_enabled"] = enabled
        if not enabled:
            row["studio_disabled_reason"] = "该通路当前依赖全权限编程代理，尚未达到 Studio 权限隔离要求"
        rows.append(row)
    return rows


def studio_provider_available(row: Dict[str, Any]) -> bool:
    provider = str(row.get("provider") or "")
    if not studio_provider_allowed(provider) or row.get("studio_enabled") is False:
        return False
    if provider == "codex":
        return bool(row.get("subscription"))
    return bool(row.get("subscription") or row.get("api_key"))


def resolve_studio_provider(requested: Any, providers: List[Dict[str, Any]]) -> str:
    wanted = str(requested or "auto").strip().lower() or "auto"
    indexed = {str(row.get("provider") or ""): row for row in providers if isinstance(row, dict)}
    if wanted != "auto":
        if not studio_provider_allowed(wanted):
            raise ValueError(f"Studio 暂未安全开放 {wanted} 通路")
        row = indexed.get(wanted)
        if row is None or not studio_provider_available(row):
            raise ValueError(f"Studio 的 {wanted} 安全通路当前不可用")
        return wanted
    for provider in STUDIO_SAFE_PROVIDER_ORDER:
        row = indexed.get(provider)
        if row is not None and studio_provider_available(row):
            return provider
    raise ValueError("没有可用的 Studio 安全通路；请登录 Grok/Codex 或配置官方 API Key")


def studio_brief_provider(requested: Any, providers: List[Dict[str, Any]], model: Any = "") -> str:
    """Local brief may name a safe provider before login; confirm still fail-closes.

    In `auto` mode a chosen model implies its provider: picking `gpt-image-2` means
    Codex, never "auto → Grok with a Codex model" that the confirm gate would reject.
    """
    if studio_fixture_enabled():
        return "fixture"
    wanted = str(requested or "auto").strip().lower() or "auto"
    if wanted != "auto":
        if not studio_provider_allowed(wanted):
            raise ValueError(f"Studio 暂未安全开放 {wanted} 通路")
        return wanted
    chosen_model = str(model or "").strip()
    if chosen_model:
        indexed = {str(row.get("provider") or ""): row for row in providers if isinstance(row, dict)}
        for provider in STUDIO_SAFE_PROVIDER_ORDER:
            row = indexed.get(provider)
            if row is None or not studio_provider_available(row):
                continue
            if any(
                item.get("provider") == provider and item.get("model") == chosen_model
                for item in studio_models_payload().get("models") or []
            ):
                return provider
    try:
        return resolve_studio_provider("auto", providers)
    except ValueError:
        return "auto"


def current_studio_providers() -> List[Dict[str, Any]]:
    loaded = cli.env_search_files(None)
    return annotate_studio_providers(cli.list_provider_status(loaded))


def studio_models_payload() -> Dict[str, Any]:
    """Expose only models reachable through non-agent Studio providers."""
    rows: List[Dict[str, Any]] = []
    for model, meta in cli.MODEL_CATALOG.items():
        base = {
            "model": model,
            "aliases": list(meta.get("aliases") or ()),
            "resolutions": list(meta.get("resolutions") or ()),
            "qualities": list(meta.get("qualities") or ()),
        }
        catalog_provider = str(meta.get("provider") or "")

        def row_for(provider: str) -> Dict[str, Any]:
            return {**base, "provider": provider, "aspects": list(provider_aspects(provider))}

        if catalog_provider == "antigravity":
            rows.append(row_for("gemini"))
        elif catalog_provider == "grok":
            rows.append(row_for("grok"))
            rows.append(row_for("xai"))
        elif catalog_provider == "codex":
            rows.append(row_for("codex"))
            rows.append(row_for("openai"))
        elif studio_provider_allowed(catalog_provider):
            rows.append(row_for(catalog_provider))
    return {"success": True, "models": rows}


def normalize_studio_generation_settings(
    provider: str,
    model: Any,
    resolution: Any,
    providers: List[Dict[str, Any]],
) -> Dict[str, str]:
    indexed = {str(row.get("provider") or ""): row for row in providers if isinstance(row, dict)}
    selected_model = str(model or indexed.get(provider, {}).get("default_model") or "").strip()
    selected_resolution = str(resolution or "").strip()
    warning = ""
    if selected_model and selected_resolution:
        model_row = next(
            (
                row
                for row in studio_models_payload().get("models") or []
                if row.get("provider") == provider and row.get("model") == selected_model
            ),
            None,
        )
        supported = list((model_row or {}).get("resolutions") or [])
        if selected_resolution not in supported:
            warning = f"{provider} / {selected_model} 不接受 {selected_resolution} 清晰度，已改用模型原生尺寸"
            selected_resolution = ""
    return {"model": selected_model, "resolution": selected_resolution, "warning": warning}


def redact_public_text(text: Any) -> str:
    return cli.redact_secrets(str(text or ""))


def _redact_deep(value: Any) -> Any:
    """Board 2026-08-23 P1-4: redact every string, whatever field carries it."""
    if isinstance(value, str):
        return redact_public_text(value)
    if isinstance(value, list):
        return [_redact_deep(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact_deep(item) for key, item in value.items()}
    return value


def redact_cli_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Strip keys from CLI JSON before it reaches receipts, batches, or the UI."""
    out = dict(payload)
    if out.get("error"):
        out["error"] = redact_public_text(out["error"])
    if out.get("details"):
        out["details"] = redact_public_text(out["details"])
    notes = out.get("notes")
    if isinstance(notes, list):
        out["notes"] = [redact_public_text(item) for item in notes]
    elif isinstance(notes, str):
        out["notes"] = redact_public_text(notes)
    for key, value in out.items():
        if key not in {"error", "details", "notes"}:
            out[key] = _redact_deep(value)
    return out


def attach_saved_artifact(payload: Dict[str, Any]) -> Dict[str, Any]:
    """If the CLI saved a file then failed aspect check, surface that path."""
    error = payload.get("error")
    if isinstance(error, str) and error.startswith("{"):
        nested = parse_cli_json(error)
        if nested and nested.get("error"):
            payload["error"] = nested["error"]
    text = str(payload.get("error") or "")
    match = re.search(r"(local-generated-image-\S+\.(?:png|jpg|jpeg|webp))", text)
    if not match:
        return payload
    saved = IMAGE_DIR / match.group(1)
    if saved.is_file():
        payload["saved_image"] = str(saved)
        payload["saved_but_failed"] = True
    return payload


def _cli_timeout_message(args: List[str], timeout: int) -> str:
    command = str(args[0]) if args else ""
    if command in {"doctor", "--doctor", "--list-models", "--list-providers"}:
        return (
            f"本机命令 local-image-gen {command} 超过 {timeout} 秒没有返回；"
            "请检查是否有卡住的 local-image-gen 进程，然后点“重新检测”。"
        )
    return (
        f"生图任务超过 {timeout} 秒没有返回。"
        "Codex / Grok 通常需要 1–3 分钟；请稍后重试，或检查本机进程。"
    )


def run_cli(args: List[str], timeout: int = 300, *, skip_update_check: bool = True) -> Dict[str, Any]:
    env = os.environ.copy()
    # Studio already resolved its store. The child must use that root even when the
    # parent shell exported a different LOCAL_IMAGE_GEN_OUTPUTS (fixture/e2e).
    env["LOCAL_IMAGE_GEN_OUTPUTS"] = str(OUTPUTS)
    if skip_update_check:
        env["LOCAL_IMAGE_GEN_SKIP_UPDATE_CHECK"] = "1"
    else:
        env.pop("LOCAL_IMAGE_GEN_SKIP_UPDATE_CHECK", None)
    try:
        proc = subprocess.run(
            [sys.executable, str(CLI), *args],
            cwd=str(WORKSPACE),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": _cli_timeout_message(args, timeout),
            "exit_code": None,
        }
    payload = parse_cli_json(proc.stdout) or parse_cli_json(proc.stderr)
    if payload is None:
        detail = (proc.stderr or proc.stdout or "CLI returned no JSON").strip()[:800]
        return {"success": False, "error": redact_public_text(detail), "exit_code": proc.returncode}
    payload.setdefault("success", proc.returncode == 0)
    payload["exit_code"] = proc.returncode
    return attach_saved_artifact(redact_cli_payload(payload))


def crop_to_aspect(src: Path, aspect: str) -> Optional[Path]:
    """Top-aligned crop to the requested ratio. macOS sips only."""
    if sys.platform != "darwin" or not src.is_file() or not aspect or ":" not in aspect:
        return None
    try:
        width, height = cli.read_image_dimensions(src)
    except cli.ImageGenError:
        return None
    if cli.dimensions_match_aspect(width, height, aspect):
        return src
    target = cli.aspect_ratio_value(aspect)
    current = width / height
    if current < target:
        new_w, new_h = width, max(16, int(round(width / target)))
        offset_y, offset_x = 0, 0
    else:
        new_h, new_w = height, max(16, int(round(height * target)))
        offset_y, offset_x = 0, max(0, (width - new_w) // 2)
    dest = src.with_name(f"{src.stem}-{aspect.replace(':', 'x')}{src.suffix}")
    proc = subprocess.run(
        [
            "sips",
            "--cropOffset",
            str(offset_y),
            str(offset_x),
            "--cropToHeightWidth",
            str(new_h),
            str(new_w),
            str(src),
            "--out",
            str(dest),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not dest.is_file():
        return None
    try:
        out_w, out_h = cli.read_image_dimensions(dest)
    except cli.ImageGenError:
        return None
    if not cli.dimensions_match_aspect(out_w, out_h, aspect):
        return None
    return dest


CROP_SUFFIX = re.compile(r"-(\d+)x(\d+)$")


def _nonzero(value: Any) -> bool:
    return value not in (None, "", [], {})


def prompt_parts(payload: Dict[str, Any]) -> Dict[str, Any]:
    prompt = payload.get("prompt") if isinstance(payload.get("prompt"), dict) else {}
    used = payload.get("sent_prompt") or prompt.get("used") or payload.get("prompt_used")
    original = prompt.get("original") or payload.get("prompt_original")
    return {"original": original, "used": used}


_SIDECAR_LOCKS: Dict[str, threading.Lock] = {}
_SIDECAR_LOCKS_GUARD = threading.Lock()
_SIDECAR_WARNINGS: List[str] = []

try:  # Board 2026-08-23 P1-3: cross-process mutual exclusion where available.
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - non-POSIX
    _fcntl = None
try:
    import msvcrt as _msvcrt
except ImportError:  # pragma: no cover - non-Windows
    _msvcrt = None

import contextlib as _contextlib


@_contextlib.contextmanager
def file_lock(path: Path):
    """Advisory whole-file lock shared across processes (thread lock still applies)."""
    lock_path = path.with_name(path.name + ".lock")
    handle = None
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(lock_path, "a+b")
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
    except OSError:
        if handle is not None:
            handle.close()
        yield
        return
    try:
        if _fcntl is not None:
            _fcntl.flock(handle.fileno(), _fcntl.LOCK_EX)
            try:
                yield
            finally:
                _fcntl.flock(handle.fileno(), _fcntl.LOCK_UN)
        elif _msvcrt is not None:
            _msvcrt.locking(handle.fileno(), _msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                _msvcrt.locking(handle.fileno(), _msvcrt.LK_UNLCK, 1)
        else:
            yield
    finally:
        handle.close()


def sidecar_lock_for(path: Path) -> threading.Lock:
    key = str(path.resolve())
    with _SIDECAR_LOCKS_GUARD:
        lock = _SIDECAR_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _SIDECAR_LOCKS[key] = lock
        return lock


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        # Board 2026-08-23 P2-7: receipts and batches are private to the user.
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        last_error: Optional[OSError] = None
        for attempt in range(8):
            try:
                os.replace(str(tmp), str(path))
                last_error = None
                break
            except PermissionError as exc:
                last_error = exc
                time.sleep(0.02 * (attempt + 1))
        if last_error is not None:
            raise last_error
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def drain_sidecar_warnings() -> List[str]:
    items = list(_SIDECAR_WARNINGS)
    _SIDECAR_WARNINGS.clear()
    return items


def read_sidecar(path: Path) -> Dict[str, Any]:
    sidecar = path if path.suffix.lower() == ".json" else path.with_suffix(".json")
    if not sidecar.is_file():
        return {}
    try:
        loaded = json.loads(sidecar.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        corrupt = sidecar.with_name(f"{sidecar.name}.corrupt-{stamp}")
        try:
            os.replace(str(sidecar), str(corrupt))
            _SIDECAR_WARNINGS.append(f"sidecar corrupt, renamed to {corrupt.name}")
        except OSError:
            _SIDECAR_WARNINGS.append(f"sidecar corrupt, could not rename {sidecar.name}")
        return {}
    except OSError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def merge_sidecar(path: Path, fields: Dict[str, Any]) -> Path:
    sidecar = path.with_suffix(".json")
    with sidecar_lock_for(sidecar), file_lock(sidecar):
        existing = read_sidecar(sidecar)
        prompt: Dict[str, Any] = {}
        if isinstance(existing.get("prompt"), dict):
            prompt.update({key: value for key, value in existing["prompt"].items() if _nonzero(value)})
        incoming_prompt = fields.get("prompt") if isinstance(fields.get("prompt"), dict) else {}
        prompt.update({key: value for key, value in incoming_prompt.items() if _nonzero(value)})
        merged = dict(existing)
        for key, value in fields.items():
            if key == "prompt" or not _nonzero(value):
                continue
            merged[key] = value
        if prompt:
            merged["prompt"] = prompt
        atomic_write_text(sidecar, json.dumps(merged, ensure_ascii=False, indent=2) + "\n")
        return sidecar


def write_media_receipt(path: Path, payload: Dict[str, Any]) -> None:
    prompt = prompt_parts(payload)
    merge_sidecar(
        path,
        {
            "schema": 1,
            "ok": bool(payload.get("success", True)),
            "created_at": payload.get("created_at")
            or (cli.utc_now_iso() if hasattr(cli, "utc_now_iso") else None),
            "image": path.name,
            "provider": payload.get("provider"),
            "provider_requested": payload.get("provider_requested"),
            "auth": payload.get("auth"),
            "model": payload.get("model"),
            "model_requested": payload.get("model_requested"),
            "aspect_ratio": payload.get("aspect_ratio"),
            "aspect_requested": payload.get("aspect_requested"),
            "quality": payload.get("quality"),
            "quality_requested": payload.get("quality_requested"),
            "resolution": payload.get("resolution"),
            "resolution_reported": payload.get("resolution_reported"),
            "resolution_requested": payload.get("resolution_requested"),
            "size": payload.get("size"),
            "actual_width": payload.get("actual_width"),
            "actual_height": payload.get("actual_height"),
            "actual_mime": payload.get("actual_mime"),
            "cropped_from": payload.get("cropped_from"),
            "notes": payload.get("notes"),
            "warning": payload.get("warning"),
            "aspect_mismatch": payload.get("aspect_mismatch"),
            "prompt": prompt,
            "cli": "local-image-gen",
            "studio": True,
            "version": getattr(cli, "__version__", None),
            "composed_from": payload.get("composed_from"),
            "overlays": payload.get("overlays"),
            "session_id": payload.get("session_id"),
            "parent": payload.get("parent"),
            "batch_id": payload.get("batch_id"),
            "mode": payload.get("mode"),
            "template": payload.get("template"),
            "starred": payload.get("starred"),
            "project_id": payload.get("project_id"),
        },
    )


def recover_aspect(result: Dict[str, Any], aspect: str) -> Dict[str, Any]:
    saved = result.get("saved_image") or result.get("image")
    if not saved or not aspect:
        return result
    cropped = crop_to_aspect(Path(str(saved)), aspect)
    if not cropped:
        return result
    result["success"] = True
    result["image"] = str(cropped)
    result["images"] = [str(cropped)]
    result["cropped_from"] = str(saved)
    result["aspect_ratio"] = aspect
    notes = list(result.get("notes") or [])
    notes.append(f"后端画出的画幅不对，已顶对齐裁成 {aspect}。")
    result["notes"] = notes
    result["error"] = None
    write_media_receipt(cropped, result)
    return result


def stamp_job_meta(result: Dict[str, Any], job: Dict[str, Any], used: str) -> Dict[str, Any]:
    result = dict(result)
    result["sent_prompt"] = used
    if job.get("style"):
        result["style"] = job.get("style")
    job_provider = str(job.get("provider") or "").strip()
    if job_provider and job_provider != "auto":
        result["provider_requested"] = job_provider
    if job.get("model"):
        result["model_requested"] = job.get("model")
    if job.get("quality"):
        result["quality_requested"] = job.get("quality")
    if job.get("resolution"):
        result["resolution_requested"] = job.get("resolution")
        reported_resolution = result.pop("resolution", None)
        if reported_resolution and reported_resolution != job.get("resolution"):
            result["resolution_reported"] = reported_resolution
    aspect = job.get("aspect") or result.get("aspect_ratio")
    if aspect:
        result["aspect_ratio"] = aspect
    if job.get("aspect"):
        result["aspect_requested"] = job["aspect"]
    prompt = result.get("prompt") if isinstance(result.get("prompt"), dict) else {}
    if used:
        result["prompt"] = {
            "original": job.get("user_prompt") or prompt.get("original") or used,
            "used": used,
        }
    return result


def persist_result_receipts(result: Dict[str, Any]) -> None:
    image = result.get("image") or result.get("saved_image")
    if not image:
        return
    path = Path(str(image))
    if path.is_file():
        write_media_receipt(path, result)
    cropped_from = result.get("cropped_from")
    if not cropped_from:
        return
    original = Path(str(cropped_from))
    if original.is_file():
        merge_sidecar(
            original,
            {
                "provider": result.get("provider"),
                "auth": result.get("auth"),
                "model": result.get("model"),
                "model_requested": result.get("model_requested"),
                "quality": result.get("quality"),
                "quality_requested": result.get("quality_requested"),
                "resolution": result.get("resolution"),
                "resolution_requested": result.get("resolution_requested"),
                "prompt": prompt_parts(result),
                "notes": result.get("notes"),
            },
        )


def finalize_generated(result: Dict[str, Any], job: Dict[str, Any], used: str) -> Dict[str, Any]:
    result = stamp_job_meta(result, job, used)
    studio_committed = bool(result.pop("_studio_committed", False))
    aspect = str(job.get("aspect") or "")
    if result.get("saved_but_failed"):
        # Edits keep the paid canvas. Generations try a crop first; if that fails
        # the image is already in the library, so the same keep-and-warn path
        # must run instead of reporting a total failure over a saved file.
        if aspect and not job.get("images"):
            result = recover_aspect(result, aspect)
        if not result.get("success"):
            result = accept_edit_canvas(result, aspect)
    saved = result.get("image") or result.get("saved_image")
    if saved:
        path = Path(str(saved))
        if path.is_file():
            result.update(actual_image_facts(path))
    try:
        persist_result_receipts(result)
    except Exception:
        if studio_committed:
            saved = result.get("image") or result.get("saved_image")
            if saved:
                Path(str(saved)).unlink(missing_ok=True)
        raise
    invalidate_library_cache()
    return result


def is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def sniff_image_suffix(data: bytes) -> Optional[str]:
    if data.startswith(PNG_MAGIC):
        return ".png"
    if data.startswith(JPEG_MAGIC):
        return ".jpg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None


def actual_image_facts(path: Path) -> Dict[str, Any]:
    try:
        with path.open("rb") as handle:
            head = handle.read(16)
    except OSError:
        return {}
    suffix = sniff_image_suffix(head)
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp"}.get(suffix or "")
    try:
        width, height = cli.read_image_dimensions(path)
    except (OSError, ValueError, cli.ImageGenError):
        width = height = None
    facts: Dict[str, Any] = {"actual_mime": mime}
    if width and height:
        facts.update({"actual_width": width, "actual_height": height, "size": f"{width}x{height}"})
    return facts


def save_image_bytes(
    dest_dir: Path,
    data: bytes,
    *,
    max_bytes: int,
    allowed: Tuple[str, ...],
    name_suffix: str = "",
) -> Path:
    if not data:
        raise ValueError("empty upload")
    if len(data) > max_bytes:
        raise ValueError("upload too large")
    sniffed = sniff_image_suffix(data)
    if sniffed is None or sniffed not in allowed:
        raise ValueError("not a PNG or JPEG")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{uuid.uuid4().hex[:10]}{name_suffix}{sniffed}"
    # Board 2026-08-23 P1-8: constrain the parent first, then write via
    # temp + fsync + replace so a crash never leaves a truncated image.
    if not is_under(dest_dir, OUTPUTS):
        raise ValueError("image is outside the library")
    tmp = dest.with_name(f".{dest.name}.{uuid.uuid4().hex}.tmp")
    try:
        with open(tmp, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(str(tmp), str(dest))
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise
    return dest


def load_receipt(path: Path) -> Optional[Dict[str, Any]]:
    own = read_sidecar(path)
    parent: Dict[str, Any] = {}
    stripped = CROP_SUFFIX.sub("", path.stem)
    if stripped != path.stem:
        parent = read_sidecar(path.with_name(stripped + ".json"))
    if not own and not parent:
        return None
    merged = dict(parent)
    parent_prompt = merged.get("prompt") if isinstance(merged.get("prompt"), dict) else {}
    own_prompt = own.get("prompt") if isinstance(own.get("prompt"), dict) else {}
    for key, value in own.items():
        if key == "prompt":
            continue
        if _nonzero(value):
            merged[key] = value
    prompt = dict(parent_prompt)
    prompt.update({key: value for key, value in own_prompt.items() if _nonzero(value)})
    if prompt:
        merged["prompt"] = prompt
    return merged


def aspect_from_pixels(width: int, height: int) -> str:
    """Nearest supported ratio within tolerance, else the exact reduced ratio."""
    described = cli.describe_dimensions(width, height)
    if ":" in described:
        return described
    from math import gcd

    factor = gcd(int(width), int(height)) or 1
    return f"{int(width) // factor}:{int(height) // factor}"


def peek_png_size(path: Path) -> Optional[Tuple[int, int]]:
    try:
        with path.open("rb") as handle:
            head = handle.read(24)
    except OSError:
        return None
    if len(head) >= 24 and head.startswith(b"\x89PNG\r\n\x1a\n"):
        return struct.unpack(">II", head[16:24])
    return None


def media_item(path: Path) -> Dict[str, Any]:
    receipt = load_receipt(path)
    rel = path.resolve().relative_to(OUTPUTS.resolve()).as_posix()
    stat = path.stat()
    prompt = (receipt or {}).get("prompt") if isinstance((receipt or {}).get("prompt"), dict) else {}
    crop_match = CROP_SUFFIX.search(path.stem)
    cropped_from = (receipt or {}).get("cropped_from")
    if crop_match and not cropped_from:
        parent_path = path.with_name(path.stem[: crop_match.start()] + path.suffix)
        if parent_path.is_file():
            cropped_from = str(parent_path)
    aspect = None
    raw_aspect = (receipt or {}).get("aspect_ratio")
    actual = actual_image_facts(path)
    pixels = (
        (int(actual["actual_width"]), int(actual["actual_height"]))
        if actual.get("actual_width") and actual.get("actual_height")
        else None
    )
    if crop_match:
        aspect = f"{crop_match.group(1)}:{crop_match.group(2)}"
    elif pixels:
        # The picture on disk is the truth; the requested ratio stays in aspect_requested.
        aspect = aspect_from_pixels(*pixels)
    elif isinstance(raw_aspect, str) and raw_aspect and " or " not in raw_aspect:
        aspect = raw_aspect
    size = f"{pixels[0]}x{pixels[1]}" if pixels else (receipt or {}).get("size")
    created = (receipt or {}).get("created_at")
    if not created:
        created = dt.datetime.fromtimestamp(stat.st_mtime, dt.timezone.utc).isoformat().replace("+00:00", "Z")
    used = prompt.get("used") or (receipt or {}).get("prompt_used")
    original = prompt.get("original") or (receipt or {}).get("prompt_original")
    return {
        "id": rel,
        "name": path.name,
        "url": "/media/" + rel,
        "mtime": int(stat.st_mtime),
        "bytes": stat.st_size,
        "folder": path.parent.resolve().relative_to(OUTPUTS.resolve()).as_posix(),
        "provider": (receipt or {}).get("provider"),
        "provider_requested": (receipt or {}).get("provider_requested"),
        "model": (receipt or {}).get("model"),
        "model_requested": (receipt or {}).get("model_requested"),
        "aspect_ratio": aspect,
        "aspect_requested": (receipt or {}).get("aspect_requested"),
        "quality": (receipt or {}).get("quality"),
        "quality_requested": (receipt or {}).get("quality_requested"),
        "resolution": size,
        "resolution_requested": (receipt or {}).get("resolution_requested"),
        "size": size,
        "actual_width": actual.get("actual_width") or (receipt or {}).get("actual_width"),
        "actual_height": actual.get("actual_height") or (receipt or {}).get("actual_height"),
        "actual_mime": actual.get("actual_mime") or (receipt or {}).get("actual_mime"),
        "auth": (receipt or {}).get("auth"),
        "created_at": created,
        "prompt_original": original,
        "prompt_used": used,
        "has_receipt": receipt is not None,
        "cropped_from": cropped_from,
        "notes": (receipt or {}).get("notes"),
        "warning": (receipt or {}).get("warning"),
        "aspect_mismatch": (receipt or {}).get("aspect_mismatch"),
        "receipt": receipt,
        "composed_from": (receipt or {}).get("composed_from"),
        "overlays": (receipt or {}).get("overlays"),
        "session_id": (receipt or {}).get("session_id"),
        "parent": (receipt or {}).get("parent"),
        "batch_id": (receipt or {}).get("batch_id"),
        "mode": (receipt or {}).get("mode"),
        "template": (receipt or {}).get("template"),
        "starred": (receipt or {}).get("starred"),
        "project_id": (receipt or {}).get("project_id"),
    }


def _skip_library_path(path: Path) -> bool:
    try:
        parts = path.resolve().relative_to(OUTPUTS.resolve()).parts
    except (OSError, ValueError):
        return True
    return any(part.startswith(".") or part == "overlays" for part in parts)


def list_library() -> List[Dict[str, Any]]:
    if not OUTPUTS.is_dir():
        return []
    items: List[Dict[str, Any]] = []
    for path in OUTPUTS.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if _skip_library_path(path):
            continue
        items.append(media_item(path))
    items.sort(key=lambda item: item["mtime"], reverse=True)
    return items


def invalidate_library_cache() -> None:
    try:
        INDEX_PATH.unlink()
    except FileNotFoundError:
        pass


def list_library_cached() -> List[Dict[str, Any]]:
    try:
        payload = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        items = payload.get("items") if isinstance(payload, dict) else None
        if isinstance(items, list) and items:
            if all((OUTPUTS / str(item.get("id") or "")).is_file() for item in items):
                return items
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    items = list_library()
    try:
        atomic_write_text(INDEX_PATH, json.dumps({"items": items}, ensure_ascii=False, indent=2) + "\n")
    except OSError:
        pass
    return items


def _ps_single_quote(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _windows_jpeg_thumb(source: Path, dest: Path) -> bool:
    """Resize with Windows PowerShell + System.Drawing. No extra Python deps."""
    src = _ps_single_quote(str(source))
    out = _ps_single_quote(str(dest))
    script = (
        "Add-Type -AssemblyName System.Drawing; "
        f"$src = [System.Drawing.Image]::FromFile({src}); "
        "try { "
        "$edge = [Math]::Max($src.Width, $src.Height); "
        "$scale = if ($edge -gt 480) { 480.0 / $edge } else { 1.0 }; "
        "$w = [Math]::Max(1, [int][Math]::Round($src.Width * $scale)); "
        "$h = [Math]::Max(1, [int][Math]::Round($src.Height * $scale)); "
        "$bmp = New-Object System.Drawing.Bitmap $w, $h; "
        "$g = [System.Drawing.Graphics]::FromImage($bmp); "
        "$g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic; "
        "$g.DrawImage($src, 0, 0, $w, $h); "
        f"$bmp.Save({out}, [System.Drawing.Imaging.ImageFormat]::Jpeg); "
        "$g.Dispose(); $bmp.Dispose() "
        "} finally { $src.Dispose() }"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0 and dest.is_file()


def _linux_jpeg_thumb(source: Path, dest: Path) -> bool:
    """Create a bounded JPEG with ffmpeg or ImageMagick when available."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f".{dest.stem}.{uuid.uuid4().hex}.tmp.jpg")
    commands: List[List[str]] = []
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        commands.append(
            [
                ffmpeg,
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(source),
                "-vf",
                "scale=w=480:h=480:force_original_aspect_ratio=decrease",
                "-frames:v",
                "1",
                str(tmp),
            ]
        )
    image_magick = shutil.which("magick") or shutil.which("convert")
    if image_magick:
        commands.append(
            [image_magick, str(source), "-auto-orient", "-thumbnail", "480x480>", "-quality", "84", str(tmp)]
        )
    try:
        for command in commands:
            tmp.unlink(missing_ok=True)
            proc = subprocess.run(command, capture_output=True, text=True, check=False)
            if proc.returncode != 0 or not tmp.is_file():
                continue
            try:
                width, height = cli.read_image_dimensions(tmp)
                with tmp.open("rb") as handle:
                    is_jpeg = handle.read(len(JPEG_MAGIC)) == JPEG_MAGIC
            except (OSError, ValueError, cli.ImageGenError):
                continue
            if not is_jpeg or max(width, height) > 480:
                continue
            try:
                os.chmod(tmp, 0o600)
            except OSError:
                pass
            os.replace(str(tmp), str(dest))
            return True
    finally:
        tmp.unlink(missing_ok=True)
    return False


def thumb_file(rel: str) -> Path:
    """Return a cached JPEG no larger than 480px when a platform encoder exists."""
    source = resolve_library_image(rel)
    cache = THUMB_DIR / (Path(rel).as_posix() + ".jpg")
    if THUMB_DIR.is_symlink() or not is_under(cache, OUTPUTS):
        return source
    # Board 2026-08-23 P1-2: the cache lives under OUTPUTS; a symlinked or
    # escaped cache path must never be served just because it looks fresh.
    cache_ok = (
        cache.is_file()
        and not cache.is_symlink()
        and is_under(cache, OUTPUTS)
        and cache.resolve().is_relative_to(OUTPUTS.resolve())
        and cache.stat().st_mtime >= source.stat().st_mtime
    )
    if cache_ok:
        return cache
    cache.parent.mkdir(parents=True, exist_ok=True)
    if cache.parent.is_symlink() or not is_under(cache, OUTPUTS):
        return source
    made = False
    if sys.platform == "darwin":
        proc = subprocess.run(
            ["sips", "-s", "format", "jpeg", "-Z", "480", str(source), "--out", str(cache)],
            capture_output=True,
            text=True,
        )
        made = proc.returncode == 0 and cache.is_file()
    elif sys.platform == "win32":
        made = _windows_jpeg_thumb(source, cache)
    elif sys.platform.startswith("linux"):
        made = _linux_jpeg_thumb(source, cache)
    if made and cache.is_file() and is_under(cache, OUTPUTS):
        try:
            os.chmod(cache, 0o600)
        except OSError:
            pass
        return cache
    return source


def slugify_project(name: str) -> str:
    raw = re.sub(r"[^a-z0-9]+", "-", str(name or "").lower()).strip("-")
    if not raw:
        raw = "project"
    slug = raw[:64]
    if not PROJECT_SLUG.fullmatch(slug):
        slug = re.sub(r"[^a-z0-9-]", "", "p" + slug)[:64]
    if not PROJECT_SLUG.fullmatch(slug):
        slug = ("p" + uuid.uuid4().hex)[:16]
    return slug


def load_project(slug: str) -> Optional[Dict[str, Any]]:
    if not PROJECT_SLUG.fullmatch(str(slug or "")):
        return None
    path = PROJECTS_DIR / slug / "project.json"
    if not path.is_file() or not is_under(path, OUTPUTS):
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def list_projects() -> List[Dict[str, Any]]:
    if not PROJECTS_DIR.is_dir():
        return []
    rows: List[Dict[str, Any]] = []
    for path in sorted(PROJECTS_DIR.glob("*/project.json")):
        if not is_under(path, OUTPUTS):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            payload.setdefault("id", path.parent.name)
            rows.append(payload)
    return rows


def save_project(body: Dict[str, Any]) -> Dict[str, Any]:
    name = str(body.get("name") or "").strip()
    slug = str(body.get("id") or "").strip()
    if slug:
        if not PROJECT_SLUG.fullmatch(slug):
            raise ValueError("invalid project id")
    else:
        slug = slugify_project(name)
    refs = []
    for raw in body.get("refs") or []:
        path = resolve_library_image(str(raw))
        refs.append(path.resolve().relative_to(OUTPUTS.resolve()).as_posix())
    overlays = []
    for raw in body.get("overlays") or []:
        path = resolve_library_image(str(raw))
        overlays.append(path.resolve().relative_to(OUTPUTS.resolve()).as_posix())
    payload = {
        "id": slug,
        "name": name or slug,
        "refs": refs,
        "overlays": overlays,
        "brand_constraints": [str(item) for item in (body.get("brand_constraints") or []) if str(item).strip()],
        "defaults": body.get("defaults") if isinstance(body.get("defaults"), dict) else {},
    }
    dest = PROJECTS_DIR / slug / "project.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not is_under(dest, OUTPUTS):
        raise ValueError("project is outside the library")
    atomic_write_text(dest, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return payload


def patch_receipt(rel: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    path = resolve_library_image(rel)
    allowed = {key: fields[key] for key in ("starred", "project_id") if key in fields}
    merge_sidecar(path, allowed)
    invalidate_library_cache()
    return media_item(path)


def _rel_of(path: Path) -> str:
    return path.resolve().relative_to(OUTPUTS.resolve()).as_posix()


def trash_item(rel: str) -> Dict[str, Any]:
    root = resolve_library_image(rel)
    wanted = {root}
    sidecar = root.with_suffix(".json")
    if sidecar.is_file():
        wanted.add(sidecar)
    thumb = THUMB_DIR / (rel + ".jpg")
    if thumb.is_file():
        wanted.add(thumb)
    for item in list_library():
        pointers = [item.get("composed_from"), item.get("parent"), item.get("cropped_from")]
        if rel in {str(ptr or "") for ptr in pointers} or any(str(ptr or "").endswith("/" + Path(rel).name) for ptr in pointers):
            child = resolve_library_image(str(item["id"]))
            wanted.add(child)
            child_side = child.with_suffix(".json")
            if child_side.is_file():
                wanted.add(child_side)
    for path in list(wanted):
        if not is_under(path, OUTPUTS):
            raise ValueError("trash path is outside the library")
    moved: List[Tuple[Path, Path]] = []
    try:
        for path in wanted:
            dest = TRASH_DIR / _rel_of(path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                dest = dest.with_name(dest.stem + "-" + uuid.uuid4().hex[:6] + dest.suffix)
            path.replace(dest)
            moved.append((path, dest))
    except OSError as exc:
        for original, dest in reversed(moved):
            original.parent.mkdir(parents=True, exist_ok=True)
            dest.replace(original)
        raise ValueError(f"trash failed: {exc}") from exc
    return {"success": True, "moved": [str(dest) for _src, dest in moved]}


def list_overlays() -> List[Dict[str, Any]]:
    if not OVERLAY_DIR.is_dir():
        return []
    items: List[Dict[str, Any]] = []
    for path in sorted(OVERLAY_DIR.iterdir()):
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if not is_under(path, OUTPUTS):
            continue
        rel = path.resolve().relative_to(OUTPUTS.resolve()).as_posix()
        items.append(
            {
                "id": rel,
                "name": path.name,
                "url": "/media/" + rel,
                "bytes": path.stat().st_size,
            }
        )
    return items


def save_overlay(data: bytes) -> Dict[str, Any]:
    path = save_image_bytes(
        OVERLAY_DIR,
        data,
        max_bytes=OVERLAY_MAX_BYTES,
        allowed=(".png", ".jpg"),
    )
    rel = path.resolve().relative_to(OUTPUTS.resolve()).as_posix()
    return {"id": rel, "name": path.name, "url": "/media/" + rel, "bytes": path.stat().st_size}


def save_inbox_images(bodies: List[bytes]) -> List[str]:
    INBOX.mkdir(parents=True, exist_ok=True)
    saved: List[str] = []
    for body in bodies:
        path = save_image_bytes(
            INBOX,
            body,
            max_bytes=OVERLAY_MAX_BYTES,
            allowed=(".png", ".jpg"),
        )
        saved.append(str(path.resolve().relative_to(OUTPUTS.resolve()).as_posix()))
    invalidate_library_cache()
    return saved


def save_composite(png: bytes, composed_from: str, overlays: Any) -> Dict[str, Any]:
    source = resolve_library_image(composed_from)
    source_rel = source.resolve().relative_to(OUTPUTS.resolve()).as_posix()
    path = save_image_bytes(
        IMAGE_DIR,
        png,
        max_bytes=COMPOSITE_MAX_BYTES,
        allowed=(".png",),
        name_suffix="-composed",
    )
    records = overlays if isinstance(overlays, list) else None
    try:
        write_media_receipt(
            path,
            {
                "success": True,
                "composed_from": source_rel,
                "overlays": records,
            },
        )
    except Exception:
        path.unlink(missing_ok=True)
        raise
    invalidate_library_cache()
    return media_item(path)


def optimize_draft(job: Dict[str, Any]) -> Dict[str, Any]:
    """Rewrite one draft with the family-matched text model via the CLI dry-run.

    Only reachable through the explicit ``POST /api/optimize-draft`` action on the
    confirmation card; nothing calls it automatically.
    """
    prompt = str(job.get("prompt") or "")
    if studio_fixture_enabled():
        return {
            "success": True,
            "dry_run": True,
            "fixture": True,
            "prompt": {
                "original": prompt,
                "used": prompt,
                "optimize": {"family": "imagine", "mode": "off"},
            },
        }
    args = [
        prompt,
        "--provider",
        str(job.get("provider") or "auto"),
        "--optimize",
        "on",
        "--dry-run",
    ]
    if job.get("aspect"):
        args.extend(["--aspect-ratio", str(job["aspect"])])
    if job.get("profile"):
        args.extend(["--prompt-profile", str(job["profile"])])
    if job.get("model"):
        args.extend(["--model", str(job["model"])])
    return run_cli(args, timeout=90)


def run_optimize_draft(body: Dict[str, Any]) -> Dict[str, Any]:
    """Explicit, user-triggered rewrite of the confirmation-card draft (one text call)."""
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("draft required")
    if studio_fixture_enabled():
        return {
            "success": True,
            "draft": prompt,
            "backend": {"provider": "fixture", "model": None},
            "calls": 0,
            "family": "fixture",
        }
    job = {
        "prompt": prompt,
        "provider": str(body.get("provider") or "auto"),
        "model": str(body.get("model") or ""),
        "aspect": str(body.get("aspect") or ""),
        "profile": str(body.get("profile") or ""),
    }
    compiled = optimize_draft(job)
    if compiled.get("success") is False:
        return {"success": False, "error": str(compiled.get("error") or "改写失败")}
    meta = compiled.get("prompt") if isinstance(compiled.get("prompt"), dict) else {}
    optimize = meta.get("optimize") if isinstance(meta.get("optimize"), dict) else {}
    used = str(meta.get("used") or "").strip() or prompt
    return {
        "success": True,
        "draft": used,
        "backend": {"provider": optimize.get("text_provider"), "model": optimize.get("text_model")},
        "calls": 1,
        "family": optimize.get("family"),
    }


def saved_image_path(result: Dict[str, Any]) -> Optional[str]:
    for key in ("image", "saved_image"):
        raw = result.get(key)
        if not raw:
            continue
        path = Path(str(raw))
        if not path.is_absolute():
            path = (OUTPUTS / path).resolve()
        if path.is_file():
            return str(path)
    return None


def generate_compiled(job: Dict[str, Any], used: str) -> Dict[str, Any]:
    if studio_fixture_enabled():
        dest = save_image_bytes(
            IMAGE_DIR,
            fixture_png_bytes(),
            max_bytes=COMPOSITE_MAX_BYTES,
            allowed=(".png",),
            name_suffix="-fixture",
        )
        return {
            "success": True,
            "fixture": True,
            "provider": "fixture",
            "auth": "fixture",
            "model": "fixture",
            "image": str(dest),
            "images": [str(dest)],
            "saved_image": str(dest),
            "aspect_ratio": str(job.get("aspect") or "1:1"),
            "prompt": {"original": used, "used": used},
            "_studio_committed": True,
        }
    args = [
        used,
        "--raw",
        "--provider",
        str(job.get("provider") or "auto"),
    ]
    if job.get("aspect"):
        args.extend(["--aspect-ratio", str(job["aspect"])])
    if job.get("quality"):
        args.extend(["--quality", str(job["quality"])])
    if job.get("resolution"):
        args.extend(["--resolution", str(job["resolution"])])
    if job.get("model"):
        args.extend(["--model", str(job["model"])])
    job_dir = JOB_DIR / uuid.uuid4().hex
    job_dir.mkdir(parents=True, mode=0o700, exist_ok=False)
    args.extend(["--out-dir", str(job_dir)])
    try:
        for raw in job.get("images") or []:
            args.extend(["-i", str(reference_image_path(raw))])
        result = run_cli(args, timeout=320)
        if not result.get("success"):
            result = attach_private_artifact(result, job_dir)
        return commit_generated_artifact(result, job_dir)
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


def reference_image_path(raw: Any) -> Path:
    """A reference image must exist inside the library. A missing one is an error,
    never a silent downgrade from edit to text-to-image."""
    path = Path(str(raw))
    if not path.is_absolute():
        path = (OUTPUTS / path).resolve()
    if not path.is_file() or not is_under(path, OUTPUTS):
        raise ValueError(f"参考图 {Path(str(raw)).name} 不在素材库里（可能已移到回收站），请重新选择底图。")
    return path


def attach_private_artifact(result: Dict[str, Any], job_dir: Path) -> Dict[str, Any]:
    """An edit whose backend ignored the requested canvas still produced a paid image
    inside the private job directory. Keep it so finalize_generated can label it."""
    if "Requested aspect" not in str(result.get("error") or ""):
        return result
    if result.get("saved_image") or result.get("image"):
        out = dict(result)
        out["saved_but_failed"] = True
        return out
    if not job_dir.is_dir():
        return result
    candidates = sorted(
        item
        for item in job_dir.iterdir()
        if item.is_file() and item.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    )
    if len(candidates) != 1:
        return result
    out = dict(result)
    out["saved_image"] = str(candidates[0])
    out["saved_but_failed"] = True
    return out


def accept_edit_canvas(result: Dict[str, Any], aspect: str) -> Dict[str, Any]:
    """Edits keep whatever canvas came back: requested vs actual is recorded, the
    image is not thrown away, and the job succeeds with a visible warning."""
    out = dict(result)
    notes = out.get("notes")
    if isinstance(notes, str) and notes:
        kept = [notes]
    elif isinstance(notes, list):
        kept = [item for item in notes if item]
    else:
        kept = []
    detail = str(out.get("error") or "").strip()
    out["notes"] = kept + ([detail] if detail else [])
    out["success"] = True
    out["aspect_mismatch"] = True
    out["warning"] = f"通路没有按请求的 {aspect or '画幅'} 出图，已按实际尺寸保存并如实记录。"
    out["image"] = out.get("image") or out.get("saved_image")
    out.pop("error", None)
    out.pop("saved_but_failed", None)
    return out


def commit_generated_artifact(result: Dict[str, Any], job_dir: Path) -> Dict[str, Any]:
    out = dict(result)
    if not out.get("success") and not out.get("saved_but_failed"):
        return out
    raw = out.get("image") or out.get("saved_image")
    if not raw:
        raise ValueError("provider finished without an image artifact")
    source = Path(str(raw)).expanduser().resolve()
    private_root = job_dir.resolve()
    if not source.is_file() or not source.is_relative_to(private_root):
        raise ValueError("provider image escaped its private job directory")
    if source.stat().st_size > COMPOSITE_MAX_BYTES:
        raise ValueError(f"provider image too large (limit {COMPOSITE_MAX_BYTES} bytes)")
    with source.open("rb") as handle:
        data = handle.read(COMPOSITE_MAX_BYTES + 1)
    if len(data) > COMPOSITE_MAX_BYTES:
        raise ValueError(f"provider image too large (limit {COMPOSITE_MAX_BYTES} bytes)")
    suffix = sniff_image_suffix(data[:16])
    if suffix not in {".png", ".jpg", ".webp"}:
        raise ValueError("provider returned an unsupported image format")
    saved = save_image_bytes(
        IMAGE_DIR,
        data,
        max_bytes=COMPOSITE_MAX_BYTES,
        allowed=(suffix,),
    )
    out["image"] = str(saved)
    out["saved_image"] = str(saved)
    out["images"] = [str(saved)]
    out["_studio_committed"] = True
    out.update(actual_image_facts(saved))
    return out


def _run_one_job(job: Dict[str, Any]) -> Dict[str, Any]:
    try:
        used = str(job.get("draft") or job.get("prompt") or "").strip()
        generated = generate_compiled(job, used)
        for key in ("session_id", "parent", "batch_id", "mode", "template", "starred", "project_id"):
            if job.get(key) not in (None, ""):
                generated[key] = job[key]
        return finalize_generated(generated, job, used)
    except ValueError as exc:
        return {"success": False, "error": redact_public_text(str(exc))}


def valid_batch_id(batch_id: Any) -> bool:
    """Board 2026-08-23 P1-1: batch ids are 12-hex uuid slices, nothing else."""
    return bool(re.fullmatch(r"[0-9a-f]{12}", str(batch_id or "").strip().lower()))


def persist_batch(rec: Dict[str, Any]) -> None:
    batch_id = str(rec.get("id") or "").strip()
    if not valid_batch_id(batch_id):
        return
    batch_dir = BATCH_DIR.resolve()
    target = (batch_dir / f"{batch_id}.json").resolve()
    if not target.is_relative_to(batch_dir):
        return
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "id": rec.get("id"),
        "mode": rec.get("mode"),
        "status": rec.get("status"),
        "started": rec.get("started"),
        "finished": rec.get("finished"),
        "error": redact_public_text(rec.get("error")) if rec.get("error") else rec.get("error"),
        "session_id": rec.get("session_id"),
        "parent": rec.get("parent"),
        "template": rec.get("template"),
        "jobs": [
            {
                "id": item.get("id"),
                "style": item.get("style"),
                "beat": item.get("beat"),
                "status": item.get("status"),
                "provider": item.get("provider"),
                "model": item.get("model"),
                "quality": item.get("quality"),
                "resolution": item.get("resolution"),
                "started_at": item.get("started_at"),
                "finished_at": item.get("finished_at"),
                "result": (
                    redact_cli_payload(item.get("result"))
                    if isinstance(item.get("result"), dict)
                    else None
                ),
            }
            for item in rec.get("jobs") or []
        ],
    }
    atomic_write_text(target, json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")


def ensure_batches_loaded() -> None:
    global _BATCHES_LOADED
    if _BATCHES_LOADED:
        return
    _BATCHES_LOADED = True
    if not BATCH_DIR.is_dir():
        return
    for path in BATCH_DIR.glob("*.json"):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(rec, dict) or not rec.get("id"):
            continue
        if rec.get("status") == "running":
            rec["status"] = "interrupted"
            persist_batch(rec)
        with _BATCH_LOCK:
            _BATCHES.setdefault(str(rec["id"]), rec)


def _set_job(batch_id: str, index: int, **fields: Any) -> None:
    with _BATCH_LOCK:
        rec = _BATCHES.get(batch_id)
        if not rec or index >= len(rec["jobs"]):
            return
        job = rec["jobs"][index]
        status = str(fields.get("status") or "")
        if status == "running" and not job.get("started_at") and "started_at" not in fields:
            fields["started_at"] = time.time()
        if status in {"done", "failed", "interrupted"} and not job.get("finished_at") and "finished_at" not in fields:
            fields["finished_at"] = time.time()
        job.update(fields)
        persist_batch(rec)


def _finish_batch(batch_id: str, status: str) -> None:
    with _BATCH_LOCK:
        rec = _BATCHES.get(batch_id)
        if rec:
            rec["status"] = status
            rec["finished"] = time.time()
            persist_batch(rec)


def execute_series(batch_id: str, jobs: List[Dict[str, Any]]) -> None:
    prev: Optional[str] = None
    for index, job in enumerate(jobs):
        _set_job(batch_id, index, status="running")
        if prev and job.get("chain_prev"):
            images = [prev] + [item for item in (job.get("images") or []) if item != prev]
            job = dict(job)
            job["images"] = images
        result = _run_one_job(job)
        _set_job(batch_id, index, status="done" if result.get("success") else "failed", result=result)
        if not result.get("success"):
            for later in range(index + 1, len(jobs)):
                _set_job(batch_id, later, status="skipped")
            _finish_batch(batch_id, "failed")
            return
        prev = saved_image_path(result) or prev
    _finish_batch(batch_id, "done")


def execute_parallel(batch_id: str, jobs: List[Dict[str, Any]]) -> None:
    workers = min(MAX_PARALLEL, max(1, len(jobs)))

    def run_index(index: int, job: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        _set_job(batch_id, index, status="running")
        return index, _run_one_job(job)

    failed = False
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run_index, index, job) for index, job in enumerate(jobs)]
        for future in as_completed(futures):
            index, result = future.result()
            ok = bool(result.get("success"))
            failed = failed or not ok
            _set_job(batch_id, index, status="done" if ok else "failed", result=result)
    _finish_batch(batch_id, "failed" if failed else "done")


def _worker(batch_id: str, mode: str, jobs: List[Dict[str, Any]]) -> None:
    try:
        if mode == "series":
            execute_series(batch_id, jobs)
        else:
            execute_parallel(batch_id, jobs)
    except Exception as exc:  # noqa: BLE001
        # Board 2026-08-23 P2-2: the failure reason must reach disk, not just memory.
        with _BATCH_LOCK:
            rec = _BATCHES.get(batch_id)
            if rec:
                rec["error"] = redact_public_text(str(exc))
        _finish_batch(batch_id, "failed")


def batch_public(rec: Dict[str, Any]) -> Dict[str, Any]:
    jobs = []
    results = []
    for item in rec.get("jobs") or []:
        result = item.get("result") if isinstance(item.get("result"), dict) else None
        row = {
            "id": item.get("id"),
            "style": item.get("style"),
            "beat": item.get("beat"),
            "status": item.get("status") or "queued",
        }
        if result:
            row["error"] = result.get("error")
            row["warning"] = result.get("warning")
            row["image"] = result.get("image") or result.get("saved_image")
            results.append(result)
        jobs.append(row)
    status = str(rec.get("status") or "running")
    done = sum(1 for item in rec.get("jobs") or [] if item.get("status") == "done")
    error = rec.get("error")
    if not error:
        for row in jobs:
            if row.get("error"):
                error = row["error"]
                break
    return {
        # The snapshot itself succeeded; the batch outcome lives in `status`, so a
        # failed batch reaches the UI as data instead of a transport error.
        "success": True,
        "batch_id": rec.get("id"),
        "mode": rec.get("mode"),
        "status": status,
        "error": error,
        "done": done,
        "session_id": rec.get("session_id"),
        "jobs": jobs,
        "results": results,
    }


def studio_runtime_status() -> Dict[str, int]:
    ensure_batches_loaded()
    with _BATCH_LOCK:
        active_records = [item for item in _BATCHES.values() if item.get("status") in {"queued", "running"}]
        active_jobs = sum(
            1
            for record in active_records
            for job in record.get("jobs") or []
            if job.get("status") in {"queued", "running"}
        )
    return {"active_batches": len(active_records), "active_jobs": active_jobs}


def _normalize_batch_mode(mode: str, jobs: List[Dict[str, Any]]) -> str:
    if mode in {"series", "candidates", "variants", "parallel", "single"}:
        return mode
    return "series" if any(job.get("chain_prev") for job in jobs) else ("parallel" if len(jobs) > 1 else "single")


def normalize_studio_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if studio_fixture_enabled():
        return jobs
    providers = current_studio_providers()
    model_pairs = {
        (str(row.get("provider") or ""), str(row.get("model") or ""))
        for row in studio_models_payload().get("models") or []
    }
    normalized: List[Dict[str, Any]] = []
    for raw in jobs:
        row = dict(raw)
        provider = resolve_studio_provider(row.get("provider"), providers)
        settings = normalize_studio_generation_settings(
            provider,
            row.get("model"),
            row.get("resolution"),
            providers,
        )
        if settings["warning"]:
            raise ValueError(f"确认卡上的设置已失效：{settings['warning']}")
        model = settings["model"]
        if model and (provider, model) not in model_pairs:
            raise ValueError(f"模型 {model} 不属于 {provider} 通路，请在设置里换一个模型或通路")
        aspect = str(row.get("aspect") or "")
        if aspect and aspect not in provider_aspects(provider):
            raise ValueError(f"{provider} 只能出 {' / '.join(provider_aspects(provider))}，不支持 {aspect}")
        for image_raw in row.get("images") or []:
            reference_image_path(image_raw)
        row["provider"] = provider
        row["model"] = model
        row["resolution"] = settings["resolution"]
        normalized.append(row)
    return normalized


def start_confirm_generate(body: Dict[str, Any]) -> Dict[str, Any]:
    ensure_batches_loaded()
    raw_jobs = body.get("jobs")
    if not isinstance(raw_jobs, list) or not raw_jobs:
        raise ValueError("没有可生成的任务，请返回重新整理。")
    if len(raw_jobs) > MAX_BATCH_JOBS:
        raise ValueError(f"一批最多 {MAX_BATCH_JOBS} 张，请减少数量后再确认。")
    jobs = [dict(item) for item in raw_jobs if isinstance(item, dict)]
    if not jobs:
        raise ValueError("没有可生成的任务，请返回重新整理。")
    with _BATCH_LOCK:
        active = sum(1 for item in _BATCHES.values() if item.get("status") in {"queued", "running"})
        if active >= MAX_ACTIVE_BATCHES:
            raise ValueError(f"本机已有 {MAX_ACTIVE_BATCHES} 批任务在运行，请等它们完成后再开始；右上角“素材库”可查看进度。")
    jobs = normalize_studio_jobs(jobs)
    mode = _normalize_batch_mode(str(body.get("mode") or jobs[0].get("mode") or "single"), jobs)
    batch_id = uuid.uuid4().hex[:12]
    session_id = str(body.get("session_id") or jobs[0].get("session_id") or uuid.uuid4().hex[:12])
    parent = str(body.get("parent") or jobs[0].get("parent") or "").strip() or None
    template = str(body.get("template") or jobs[0].get("template") or "").strip() or None
    stamped = []
    for job in jobs:
        row = dict(job)
        row["session_id"] = session_id
        row["batch_id"] = batch_id
        row["mode"] = mode
        if parent:
            row["parent"] = parent
        if template:
            row["template"] = template
        stamped.append(row)
    record = {
        "id": batch_id,
        "mode": mode,
        "status": "running",
        "started": time.time(),
        "session_id": session_id,
        "parent": parent,
        "template": template,
        "jobs": [{**job, "status": "queued", "result": None} for job in stamped],
    }
    with _BATCH_LOCK:
        stale = [key for key, item in _BATCHES.items() if time.time() - float(item.get("started") or 0) > 86400]
        for key in stale:
            _BATCHES.pop(key, None)
        active = sum(1 for item in _BATCHES.values() if item.get("status") in {"queued", "running"})
        if active >= MAX_ACTIVE_BATCHES:
            raise ValueError(f"本机已有 {MAX_ACTIVE_BATCHES} 批任务在运行，请等它们完成后再开始；右上角“素材库”可查看进度。")
        _BATCHES[batch_id] = record
        persist_batch(record)
    exec_mode = "series" if mode == "series" else "parallel"
    thread = threading.Thread(target=_worker, args=(batch_id, exec_mode, stamped), daemon=True)
    thread.start()
    return batch_public(record)


def get_batch(batch_id: str) -> Optional[Dict[str, Any]]:
    if not valid_batch_id(batch_id):
        return None
    ensure_batches_loaded()
    with _BATCH_LOCK:
        rec = _BATCHES.get(batch_id)
        if rec:
            return batch_public(rec)
    path = BATCH_DIR / f"{batch_id}.json"
    if not path.is_file():
        return None
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(rec, dict):
        return None
    if rec.get("status") == "running":
        rec["status"] = "interrupted"
        persist_batch(rec)
    with _BATCH_LOCK:
        _BATCHES[str(rec.get("id") or batch_id)] = rec
    return batch_public(rec)


def run_confirm_generate(body: Dict[str, Any]) -> Dict[str, Any]:
    """Synchronous helper for tests. Live UI uses start_confirm_generate."""
    jobs = body.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        raise ValueError("没有可生成的任务，请返回重新整理。")
    results: List[Dict[str, Any]] = []
    prev: Optional[str] = None
    mode = str(body.get("mode") or (jobs[0] or {}).get("mode") or "single")
    if mode in {"parallel", "candidates", "variants"} and len(jobs) > 1:
        workers = min(MAX_PARALLEL, len(jobs))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = [pool.submit(_run_one_job, dict(job)) for job in jobs if isinstance(job, dict)]
            results = [fut.result() for fut in futs]
        ok = all(item.get("success") for item in results) if results else False
        return {"success": ok, "mode": mode, "results": results}
    for job in jobs:
        if not isinstance(job, dict):
            continue
        working = dict(job)
        if prev and working.get("chain_prev"):
            working["images"] = [prev] + [item for item in (working.get("images") or []) if item != prev]
        generated = _run_one_job(working)
        results.append(generated)
        if not generated.get("success"):
            break
        prev = saved_image_path(generated) or prev
    ok = all(item.get("success") for item in results) if results else False
    return {"success": ok, "mode": mode, "results": results}


def resolve_library_image(raw: str) -> Path:
    path = Path(str(raw))
    if not path.is_absolute():
        path = (OUTPUTS / path).resolve()
    else:
        path = path.resolve()
    if not is_under(path, OUTPUTS):
        raise ValueError(f"image is outside the library: {raw}")
    if not path.is_file():
        raise ValueError(f"image not found: {raw}")
    return path


def run_look(body: Dict[str, Any]) -> Dict[str, Any]:
    path = resolve_library_image(str(body.get("image") or ""))
    if studio_fixture_enabled():
        return {
            "success": True,
            "looked": True,
            "backend": "fixture",
            "summary": "fixture：构图完整，字偏上。",
            "ok": True,
            "issues": [],
            "keep": ["主体还在"],
            "next": "字再大一点",
            "image": str(path),
        }
    return look_at_image(
        path,
        draft=str(body.get("draft") or ""),
        brief=str(body.get("brief") or ""),
    )


RESTART_TOKENS = ("从头", "重做", "重新画", "restart", "start over")


def revision_restarts(message: str) -> bool:
    """A revision that asks to start over is a fresh generation, not an edit of the last image."""
    lowered = str(message or "").lower()
    return any(token in lowered for token in RESTART_TOKENS)


def run_revise(body: Dict[str, Any]) -> Dict[str, Any]:
    image = str(body.get("image") or "").strip()
    last_image = ""
    if image:
        resolved = resolve_library_image(image)
        last_image = str(resolved.resolve().relative_to(OUTPUTS.resolve()).as_posix())
    message = str(body.get("message") or "").strip()
    draft = str(body.get("draft") or "").strip()
    mode = "generate" if revision_restarts(message) or not last_image else "edit"
    compiled, requirements = merge_revision_draft(draft, message)
    return {
        "success": True,
        "preflight": "local",
        "mode": mode,
        "draft": compiled,
        "requirements": requirements,
        "reason": "本地合并改稿要求；确认前未调用外部文本模型",
        "backend": "local",
        "images": [last_image] if mode == "edit" and last_image else [],
    }


def parse_generate(body: Dict[str, Any]) -> List[str]:
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("prompt is required")
    args = [prompt]
    requested_provider = str(body.get("provider") or "auto").strip()
    if studio_fixture_enabled():
        provider = "fixture"
    elif requested_provider in {"", "auto"}:
        provider = resolve_studio_provider("auto", current_studio_providers())
    elif not studio_provider_allowed(requested_provider):
        raise ValueError(f"Studio 暂未安全开放 {requested_provider} 通路")
    else:
        provider = requested_provider
    if provider:
        args.extend(["--provider", provider])
    model = str(body.get("model") or "").strip()
    if model:
        args.extend(["--model", model])
    aspect = str(body.get("aspect") or "").strip()
    if aspect:
        args.extend(["--aspect-ratio", aspect])
    quality = str(body.get("quality") or "").strip()
    if quality:
        args.extend(["--quality", quality])
    resolution = str(body.get("resolution") or "").strip()
    if resolution:
        args.extend(["--resolution", resolution])
    optimize = str(body.get("optimize") or "off").strip() or "off"
    args.extend(["--optimize", optimize])
    profile = str(body.get("profile") or "").strip()
    if profile:
        args.extend(["--prompt-profile", profile])
    if body.get("raw"):
        args.append("--raw")
    if body.get("scratch"):
        scratch_dir = OUTPUTS / ".repaint"
        scratch_dir.mkdir(parents=True, exist_ok=True)
        args.extend(["--out-dir", str(scratch_dir)])
    else:
        IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        args.extend(["--out-dir", str(IMAGE_DIR)])
    for raw in body.get("images") or []:
        path = Path(str(raw))
        if not path.is_absolute():
            path = (OUTPUTS / path).resolve()
        if not path.is_file() or not is_under(path, OUTPUTS):
            raise ValueError(f"reference image is outside the library: {raw}")
        args.extend(["-i", str(path)])
    mask_raw = str(body.get("mask") or "").strip()
    if mask_raw:
        provider = str(provider or "").strip()
        if provider != "openai":
            raise ValueError("mask requires provider openai")
        mask_path = resolve_library_image(mask_raw)
        args.extend(["--mask", str(mask_path)])
    if body.get("dry_run"):
        args.append("--dry-run")
    return args


def csrf_allows(headers: Any, host: str) -> bool:
    """Scheme A (spec §7): prefer Sec-Fetch-Site=same-origin.

    If that header is missing, Origin's host must equal this request's Host.
    If both headers are missing, allow — curl and scripts do not send them.
    Chosen over Scheme B (session token) so existing CLI POSTs keep working.
    Applied to POST and DELETE.
    """
    site = str(headers.get("Sec-Fetch-Site") or "").strip().lower()
    origin = str(headers.get("Origin") or "").strip()
    if site:
        return site == "same-origin"
    if origin:
        netloc = (urlparse(origin).netloc or "").lower()
        return netloc == str(host or "").lower()
    return True


def routed_request_path(raw_path: str) -> Tuple[Any, str]:
    parsed = urlparse(raw_path)
    path = unquote(parsed.path)
    if path == STUDIO_API_PREFIX:
        path = "/"
    elif path.startswith(STUDIO_API_PREFIX + "/"):
        path = path[len(STUDIO_API_PREFIX) :]
    return parsed, path


class Handler(BaseHTTPRequestHandler):
    server_version = "local-studio/0.1"

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write("studio: " + (format % args) + "\n")

    def _guard(self, bind_host: str, *, request_path: str = "") -> bool:
        """Shared request guard: Host allowlist (P0-A) and LAN token (P1-6)."""
        host_header = self.headers.get("Host") or ""
        if not host_allows(host_header, bind_host):
            self._send(*json_bytes({"success": False, "error": "host not allowed"}, 403))
            return False
        client_host = str(self.client_address[0] or "") if self.client_address else ""
        if not studio_token_ok(self.headers, client_host=client_host, request_path=request_path):
            self._send(*json_bytes({"success": False, "error": "studio token required"}, 403))
            return False
        return True

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' blob: data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'",
        )
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> Dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise ValueError("bad Content-Length")
        if length > MAX_JSON_BYTES:
            raise ValueError(f"request body too large (limit {MAX_JSON_BYTES} bytes)")
        raw = self.rfile.read(length) if length else b"{}"
        payload = json.loads(raw.decode("utf-8") or "{}")
        if not isinstance(payload, dict):
            raise ValueError("JSON object required")
        return payload

    def do_GET(self) -> None:  # noqa: N802
        parsed, path = routed_request_path(self.path)
        if not self._guard(BIND_HOST, request_path=path):
            return
        if "\x00" in path:
            self._send(*json_bytes({"error": "not found"}, 404))
            return
        if path == "/favicon.ico":
            self._send(204, b"", "image/x-icon")
            return
        if path in {"/", "/index.html"}:
            target = CLIENT / "index.html"
            if not target.is_file():
                self._send(*json_bytes({"error": "Studio client is missing; rebuild the local client"}, 503))
                return
            self._send(200, target.read_bytes(), "text/html; charset=utf-8")
            return
        if path.startswith("/assets/"):
            target = (CLIENT / path.lstrip("/")).resolve()
            if not is_under(target, CLIENT) or not target.is_file():
                self._send(*json_bytes({"error": "not found"}, 404))
                return
            mime = STATIC_MIME.get(target.suffix.lower()) or mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            self._send(200, target.read_bytes(), mime)
            return
        if path.startswith("/static/"):
            # The legacy darkroom UI was removed on 2026-08-30; nothing is served here.
            self._send(*json_bytes({"error": "not found"}, 404))
            return
        if path.startswith("/media/"):
            rel = path[len("/media/") :]
            target = (OUTPUTS / rel).resolve()
            if not is_under(target, OUTPUTS) or not target.is_file():
                self._send(*json_bytes({"error": "not found"}, 404))
                return
            mime = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            self._send(200, target.read_bytes(), mime)
            return
        if path == "/api/doctor":
            self._send(*json_bytes(studio_doctor_payload()))
            return
        if path == "/api/version":
            payload = studio_doctor_payload(skip_update_check=False)
            payload["changelog_available"] = (WORKSPACE / "CHANGELOG.md").is_file()
            payload["releases"] = "https://github.com/DandreYang/local-image-gen/releases"
            self._send(*json_bytes(payload))
            return
        if path == "/api/changelog":
            path_md = WORKSPACE / "CHANGELOG.md"
            if not path_md.is_file():
                self._send(*json_bytes({"success": False, "error": "CHANGELOG.md missing"}, 404))
                return
            self._send(
                *json_bytes(
                    {
                        "success": True,
                        "text": path_md.read_text(encoding="utf-8"),
                        "releases": "https://github.com/DandreYang/local-image-gen/releases",
                    }
                )
            )
            return
        if path == "/api/models":
            self._send(*json_bytes(studio_models_payload()))
            return
        if path == "/api/library":
            items = list_library_cached()
            warnings = drain_sidecar_warnings()
            self._send(*json_bytes({"success": True, "items": items, "warnings": warnings}))
            return
        if path == "/api/runtime":
            self._send(*json_bytes({"success": True, **studio_runtime_status()}))
            return
        if path.startswith("/thumb/"):
            rel = path[len("/thumb/") :]
            try:
                target = thumb_file(rel)
            except ValueError:
                self._send(*json_bytes({"error": "not found"}, 404))
                return
            if not target.is_file():
                self._send(*json_bytes({"error": "not found"}, 404))
                return
            mime = mimetypes.guess_type(str(target))[0] or "image/jpeg"
            self._send(200, target.read_bytes(), mime)
            return
        if path == "/api/projects":
            self._send(*json_bytes({"success": True, "items": list_projects()}))
            return
        if path == "/api/batch":
            query = parse_qs(parsed.query)
            batch_id = (query.get("id") or [""])[0].strip()
            payload = get_batch(batch_id) if batch_id else None
            if not payload:
                self._send(*json_bytes({"success": False, "error": "batch not found"}, 404))
                return
            self._send(*json_bytes(payload))
            return
        if path == "/api/overlays":
            self._send(*json_bytes({"success": True, "items": list_overlays()}))
            return
        if path == "/api/snippets":
            self._send(*json_bytes({"success": True, "snippets": load_snippets()}))
            return
        self._send(*json_bytes({"error": "not found"}, 404))

    def do_POST(self) -> None:  # noqa: N802
        if not self._guard(BIND_HOST):
            return
        parsed, path = routed_request_path(self.path)
        host = (self.headers.get("Host") or f"{HOST}:{DEFAULT_PORT}").strip()
        if not csrf_allows(self.headers, host):
            self._send(*json_bytes({"success": False, "error": "cross-origin request blocked"}, 403))
            return
        if path == "/api/brief":
            try:
                body = self._read_json()
                images = list(body.get("images") or [])
                project = load_project(str(body.get("project_id") or ""))
                if project:
                    for ref in project.get("refs") or []:
                        if ref not in images:
                            images.append(ref)
                providers = current_studio_providers()
                provider = studio_brief_provider(body.get("provider"), providers, body.get("model"))
                normalized = normalize_studio_generation_settings(
                    provider,
                    body.get("model"),
                    body.get("resolution"),
                    providers,
                )
                payload = build_brief(
                    str(body.get("prompt") or ""),
                    provider=provider,
                    template_id=str(body.get("template") or ""),
                    aspect=str(body.get("aspect") or ""),
                    quality=str(body.get("quality") or "high"),
                    resolution=normalized["resolution"],
                    model=normalized["model"],
                    images=images,
                )
                if payload.get("success"):
                    if normalized["warning"]:
                        payload.setdefault("warnings", []).append(normalized["warning"])
                    if project:
                        payload["project"] = project
                        payload["brand_constraints"] = list(project.get("brand_constraints") or [])
            except Exception as exc:  # noqa: BLE001
                self._send(*json_bytes({"success": False, "error": str(exc)}, 400))
                return
            self._send(*json_bytes(payload))
            return
        if path == "/api/confirm-generate":
            try:
                body = self._read_json()
                payload = start_confirm_generate(body)
            except (ValueError, json.JSONDecodeError) as exc:
                self._send(*json_bytes({"success": False, "error": str(exc)}, 400))
                return
            self._send(*json_bytes(payload))
            return
        if path == "/api/look":
            try:
                body = self._read_json()
                payload = run_look(body)
            except (ValueError, json.JSONDecodeError) as exc:
                self._send(*json_bytes({"success": False, "looked": False, "error": str(exc)}, 400))
                return
            self._send(*json_bytes(payload))
            return
        if path == "/api/revise":
            try:
                body = self._read_json()
                payload = run_revise(body)
            except (ValueError, json.JSONDecodeError) as exc:
                self._send(*json_bytes({"success": False, "error": str(exc)}, 400))
                return
            self._send(*json_bytes(payload))
            return
        if path == "/api/optimize-draft":
            try:
                body = self._read_json()
                payload = run_optimize_draft(body)
            except (ValueError, json.JSONDecodeError) as exc:
                self._send(*json_bytes({"success": False, "error": str(exc)}, 400))
                return
            self._send(*json_bytes(payload, 200 if payload.get("success") else 502))
            return
        if path == "/api/preview":
            try:
                body = self._read_json()
                body["dry_run"] = True
                payload = run_cli(parse_generate(body), timeout=60)
            except (ValueError, json.JSONDecodeError) as exc:
                self._send(*json_bytes({"success": False, "error": str(exc)}, 400))
                return
            self._send(*json_bytes(payload))
            return
        if path == "/api/generate":
            try:
                body = self._read_json()
                body["dry_run"] = False
                payload = run_cli(parse_generate(body), timeout=320)
                if body.get("composed_from"):
                    source = resolve_library_image(str(body.get("composed_from")))
                    payload["composed_from"] = source.resolve().relative_to(OUTPUTS.resolve()).as_posix()
                if isinstance(body.get("overlays"), list):
                    payload["overlays"] = body.get("overlays")
                prompt_meta = payload.get("prompt") if isinstance(payload.get("prompt"), dict) else {}
                used = str(prompt_meta.get("used") or body.get("prompt") or "")
                payload = finalize_generated(payload, body, used)
            except (ValueError, json.JSONDecodeError) as exc:
                self._send(*json_bytes({"success": False, "error": str(exc)}, 400))
                return
            self._send(*json_bytes(payload))
            return
        if path == "/api/composite":
            try:
                body = self._read_json()
                raw = str(body.get("png_base64") or "").strip()
                if not raw:
                    raise ValueError("png_base64 is required")
                png = base64.b64decode(raw, validate=False)
                item = save_composite(png, str(body.get("composed_from") or ""), body.get("overlays"))
            except (ValueError, json.JSONDecodeError, OSError) as exc:
                self._send(*json_bytes({"success": False, "error": str(exc)}, 400))
                return
            self._send(*json_bytes({"success": True, "item": item}))
            return
        if path == "/api/upload":
            kind = (parse_qs(parsed.query).get("kind") or [""])[0].strip()
            self._send(*json_bytes(self._save_upload(kind)))
            return
        if path == "/api/overlays":
            self._send(*json_bytes(self._save_upload("overlay")))
            return
        if path == "/api/trash":
            try:
                body = self._read_json()
                payload = trash_item(str(body.get("id") or body.get("image") or ""))
            except (ValueError, json.JSONDecodeError, OSError) as exc:
                self._send(*json_bytes({"success": False, "error": str(exc)}, 400))
                return
            self._send(*json_bytes(payload))
            return
        if path == "/api/receipt":
            try:
                body = self._read_json()
                item = patch_receipt(str(body.get("id") or ""), body)
            except (ValueError, json.JSONDecodeError, OSError) as exc:
                self._send(*json_bytes({"success": False, "error": str(exc)}, 400))
                return
            self._send(*json_bytes({"success": True, "item": item}))
            return
        if path == "/api/projects":
            try:
                body = self._read_json()
                item = save_project(body)
            except (ValueError, json.JSONDecodeError, OSError) as exc:
                self._send(*json_bytes({"success": False, "error": str(exc)}, 400))
                return
            self._send(*json_bytes({"success": True, "item": item, "items": list_projects()}))
            return
        if path == "/api/snippets":
            try:
                body = self._read_json()
                if body.get("color"):
                    text = color_sentence(str(body.get("color") or ""))
                    self._send(*json_bytes({"success": True, "text": text}))
                    return
                row = add_snippet(str(body.get("label") or ""), str(body.get("text") or ""))
            except (ValueError, json.JSONDecodeError) as exc:
                self._send(*json_bytes({"success": False, "error": str(exc)}, 400))
                return
            self._send(*json_bytes({"success": True, "snippet": row, "snippets": load_snippets()}))
            return
        self._send(*json_bytes({"error": "not found"}, 404))

    def do_DELETE(self) -> None:  # noqa: N802
        if not self._guard(BIND_HOST):
            return
        host = (self.headers.get("Host") or f"{HOST}:{DEFAULT_PORT}").strip()
        if not csrf_allows(self.headers, host):
            self._send(*json_bytes({"success": False, "error": "cross-origin request blocked"}, 403))
            return
        parsed, path = routed_request_path(self.path)
        if path != "/api/snippets":
            self._send(*json_bytes({"error": "not found"}, 404))
            return
        snippet_id = (parse_qs(parsed.query).get("id") or [""])[0].strip()
        if not delete_snippet(snippet_id):
            self._send(*json_bytes({"success": False, "error": "没有这句。"}, 404))
            return
        self._send(*json_bytes({"success": True, "snippets": load_snippets()}))

    def _read_multipart_images(self, max_bytes: int) -> List[bytes]:
        content_type = self.headers.get("Content-Type") or ""
        if "multipart/form-data" not in content_type:
            raise ValueError("multipart/form-data required")
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > max_bytes:
            raise ValueError("upload too large or empty")
        payload = self.rfile.read(length)
        boundary = None
        for part in content_type.split(";"):
            part = part.strip()
            if part.startswith("boundary="):
                boundary = part.split("=", 1)[1].strip().strip('"')
        if not boundary:
            raise ValueError("missing multipart boundary")
        marker = b"--" + boundary.encode("ascii", "replace")
        bodies: List[bytes] = []
        for chunk in payload.split(marker):
            header_end = chunk.find(b"\r\n\r\n")
            if header_end < 0 or b"filename=" not in chunk[:header_end]:
                continue
            body = chunk[header_end + 4 :]
            if body.endswith(b"\r\n"):
                body = body[:-2]
            if body:
                bodies.append(body)
        if not bodies:
            raise ValueError("no image part found")
        return bodies

    def _save_upload(self, kind: str = "") -> Dict[str, Any]:
        try:
            bodies = self._read_multipart_images(OVERLAY_MAX_BYTES)
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        if kind == "overlay":
            saved = []
            item = None
            for body in bodies:
                try:
                    item = save_overlay(body)
                except ValueError as exc:
                    return {"success": False, "error": str(exc)}
                saved.append(item["id"])
            return {"success": True, "item": item, "items": list_overlays(), "saved": saved}
        if kind == "mask":
            saved: List[str] = []
            for body in bodies:
                try:
                    path = save_image_bytes(
                        MASK_DIR,
                        body,
                        max_bytes=OVERLAY_MAX_BYTES,
                        allowed=(".png",),
                    )
                except ValueError as exc:
                    return {"success": False, "error": str(exc)}
                saved.append(str(path.resolve().relative_to(OUTPUTS.resolve()).as_posix()))
            return {"success": True, "items": saved}
        try:
            saved = save_inbox_images(bodies)
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        return {"success": True, "items": saved}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Local studio for local-image-gen.")
    parser.add_argument("--host", default=HOST, help="Bind address. Default 127.0.0.1. Use 0.0.0.0 for LAN.")
    parser.add_argument("--lan", action="store_true", help="Bind 0.0.0.0 so other devices on the LAN can connect.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-open", action="store_true", help="Do not open a browser.")
    parser.add_argument("--ready-file", help=argparse.SUPPRESS)
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="Return canned images and looks. Does not call image or text backends.",
    )
    args = parser.parse_args(argv)
    if args.fixture:
        os.environ["LOCAL_IMAGE_GEN_STUDIO_FIXTURE"] = "1"
    host = "0.0.0.0" if args.lan else args.host
    global BIND_HOST
    BIND_HOST = host
    if studio_token_required(host):
        issue_studio_token()
        print(
            f"LAN token: set cookie studio_token={STUDIO_TOKEN} for this address "
            f"(header {STUDIO_TOKEN_HEADER} also accepted).",
            flush=True,
        )
    ensure_private_storage_root(OUTPUTS, IMAGE_DIR)
    server = ThreadingHTTPServer((host, args.port), Handler)
    if args.ready_file:
        ready = Path(args.ready_file).expanduser()
        ready.parent.mkdir(parents=True, exist_ok=True)
        tmp = ready.with_name(f".{ready.name}.{os.getpid()}.tmp")
        tmp.write_text(f"{os.getpid()}\n", encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(str(tmp), str(ready))
    print_studio_banner(host, args.port)
    maybe_open_browser(public_studio_url(host, args.port), open_browser=not args.no_open)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped", flush=True)
    finally:
        if args.ready_file:
            try:
                Path(args.ready_file).unlink()
            except FileNotFoundError:
                pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
