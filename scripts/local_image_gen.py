#!/usr/bin/env python3
"""Generate or edit images from local subscriptions or API keys.

Stdlib only. Reuses Grok / Antigravity / Cursor / Codex logins when present,
and accepts official per-provider API keys as a fallback.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import datetime as dt
import hashlib
import json
import mimetypes
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from prompt_compile import (  # noqa: E402
    OPTIMIZE_MODES,
    PROMPT_PROFILES,
    PromptCompileResult,
    apply_profile,
    build_optimize_messages,
    decide_optimize,
    default_text_model,
    detect_prompt_format,
    fallback_prompt,
    preferred_text_backends,
    prompt_family,
    sanitize_optimized_prompt,
)

__version__ = "0.1.5"

CODEX_AUTH_PATH = Path("~/.codex/auth.json").expanduser()
GROK_AUTH_PATH = Path("~/.grok/auth.json").expanduser()

CODEX_RESPONSES_ENDPOINT = "https://chatgpt.com/backend-api/codex/responses"
CODEX_REFRESH_ENDPOINT = "https://auth.openai.com/oauth/token"
CODEX_REFRESH_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
CODEX_RESPONSE_MODEL = os.environ.get("CODEX_RESPONSE_MODEL", "gpt-5.6-terra")

GROK_REFRESH_ENDPOINT = "https://auth.x.ai/oauth2/token"
GROK_DEFAULT_CLIENT_ID = "b1a00492-073a-47ea-816f-4c329264a828"
GROK_API_BASE = "https://api.x.ai/v1"  # official Imagine API; never an unofficial proxy

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"

OPENAI_API_BASE = "https://api.openai.com/v1"

# Non-subscription (API-key) defaults are official vendor hosts only.
# Custom proxies are opt-in via env / dotenv / --base-url.
OFFICIAL_API_BASES = {
    "grok": GROK_API_BASE,
    "xai": GROK_API_BASE,
    "openai": OPENAI_API_BASE,
    "gemini": GEMINI_API_BASE,
}
API_BASE_ENV_NAMES = {
    "grok": ("XAI_BASE_URL", "XAI_API_BASE"),
    "xai": ("XAI_BASE_URL", "XAI_API_BASE"),
    "openai": ("OPENAI_BASE_URL", "OPENAI_API_BASE"),
    "gemini": ("GEMINI_BASE_URL", "GEMINI_API_BASE"),
}

REQUEST_TIMEOUT = 300
OPTIMIZE_TIMEOUT = 25
GROK_MAX_REFERENCE_IMAGES = 3
TOKEN_EXPIRY_SKEW_SECONDS = 60
DEFAULT_OUTPUT_STEM = "local-generated-image"
DYRO_TOML_NAME = "dyro.toml"
DYRO_IMAGE_DIR = Path("outputs") / "images"

ASPECT_ALIASES = {
    "square": "1:1",
    "landscape": "16:9",
    "portrait": "9:16",
}
SUPPORTED_ASPECTS = (
    "1:1",
    "16:9",
    "9:16",
    "4:3",
    "3:4",
    "3:2",
    "2:3",
    "2:1",
    "1:2",
)
CODEX_ASPECT_TO_SIZE = {
    "1:1": "1024x1024",
    "16:9": "1536x1024",
    "9:16": "1024x1536",
    "4:3": "1536x1024",
    "3:4": "1024x1536",
    "3:2": "1536x1024",
    "2:3": "1024x1536",
    "2:1": "1536x1024",
    "1:2": "1024x1536",
}
GROK_ASPECTS = set(SUPPORTED_ASPECTS)
GEMINI_ASPECTS = set(SUPPORTED_ASPECTS)

PROVIDERS = ("auto", "grok", "codex", "gemini", "antigravity", "agy", "cursor", "openai", "xai")
# Generic --provider auto when the user did not name a model family.
AUTO_PROVIDER_ORDER = ("grok", "codex", "antigravity", "cursor", "gemini", "xai", "openai")
PROVIDER_ALIASES = {"agy": "antigravity"}
QUALITY_CHOICES = ("auto", "low", "medium", "high")
RESOLUTION_CHOICES = ("1k", "2k", "4k")

# Gemini CLI public client is used only to refresh an already-issued local token.
MODEL_CATALOG: Dict[str, Dict[str, Any]] = {
    "grok-imagine-image-2.0": {
        "provider": "grok",
        "aliases": ("grok-imagine", "grok-imagine-2", "imagine-2", "imagine"),
        "resolutions": ("1k", "2k"),
        "qualities": ("low", "medium"),
    },
    "grok-imagine-image": {
        "provider": "grok",
        "aliases": ("grok-imagine-1", "imagine-1"),
        "resolutions": ("1k", "2k"),
        "qualities": (),
    },
    "grok-imagine-image-quality": {
        "provider": "grok",
        "aliases": ("grok-imagine-quality", "grok-imagine-pro", "imagine-pro"),
        "resolutions": ("1k", "2k"),
        "qualities": (),
    },
    "gpt-image-2": {
        "provider": "codex",
        "aliases": ("gpt-image", "codex-image"),
        "resolutions": (),
        "qualities": ("low", "medium", "high", "auto"),
    },
    "gpt-image-1": {
        "provider": "openai",
        "aliases": (),
        "resolutions": (),
        "qualities": ("low", "medium", "high", "auto"),
    },
    "gemini-3.1-flash-image": {
        "provider": "antigravity",
        "aliases": (
            "nano-banana-2",
            "nano-banana",
            "gemini-3.1-flash-image-preview",
            "gemini-flash-image",
        ),
        "resolutions": ("1k", "2k", "4k"),
        "qualities": (),
    },
    "gemini-3-pro-image": {
        "provider": "antigravity",
        "aliases": ("nano-banana-pro", "gemini-3-pro-image-preview"),
        "resolutions": ("1k", "2k", "4k"),
        "qualities": (),
    },
    "gemini-2.5-flash-image-preview": {
        "provider": "antigravity",
        "aliases": ("nano-banana-v1", "gemini-2.5-flash-image"),
        "resolutions": ("1k", "2k", "4k"),
        "qualities": (),
    },
    "gemini-3.1-flash-lite-image": {
        "provider": "antigravity",
        "aliases": ("nano-banana-lite", "gemini-3.1-flash-lite-image-preview"),
        "resolutions": ("1k", "2k"),
        "qualities": (),
    },
}

DEFAULT_MODEL_FOR_PROVIDER = {
    "grok": "grok-imagine-image-2.0",
    "xai": "grok-imagine-image-2.0",
    "codex": "gpt-image-2",
    "openai": "gpt-image-2",
    "gemini": "gemini-3.1-flash-image",
    "antigravity": "gemini-3.1-flash-image",
    "cursor": "gemini-3-pro-image",
}

ENV_KEY_NAMES = {
    "xai": ("XAI_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY", "NANOBANANA_API_KEY", "NANOBANANA_GEMINI_API_KEY"),
}

SIZE_PATTERN = re.compile(r"^(auto|\d+x\d+)$", re.IGNORECASE)
PUBLISHED_VERSION_RE = re.compile(r'^__version__\s*=\s*["\']([^"\']+)["\']', re.M)
REPO_SLUG_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

DEFAULT_REPO_SLUG = "DandreYang/local-image-gen"
UPDATE_CHECK_TIMEOUT = 2
META_COMMANDS = ("doctor", "update")
ASPECT_PATTERN = re.compile(
    r"^\s*(?:(?P<w>\d+(?:\.\d+)?)\s*[:/x]\s*(?P<h>\d+(?:\.\d+)?)|(?P<name>[A-Za-z][A-Za-z0-9_-]*))\s*$"
)


class ImageGenError(Exception):
    """Expected failure that should be shown to the user."""


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def print_json(payload: Dict[str, Any], *, stream: Any = sys.stdout) -> None:
    stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
    stream.flush()


def fail(message: str, *, details: Optional[str] = None, extra: Optional[Dict[str, Any]] = None) -> None:
    payload: Dict[str, Any] = {"success": False, "error": message}
    if details:
        payload["details"] = details
    if extra:
        payload.update(extra)
    print_json(payload, stream=sys.stderr)
    raise SystemExit(1)


def alias_to_model() -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for model, meta in MODEL_CATALOG.items():
        mapping[model.lower()] = model
        for alias in meta.get("aliases") or ():
            mapping[str(alias).lower()] = model
    return mapping


def canonical_model(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    return alias_to_model().get(name.strip().lower(), name.strip())


def catalog_provider(model: Optional[str]) -> Optional[str]:
    resolved = canonical_model(model)
    if not resolved:
        return None
    meta = MODEL_CATALOG.get(resolved)
    if not meta:
        if resolved.startswith("grok-imagine"):
            return "grok"
        if resolved.startswith("gpt-image"):
            return "codex"
        if resolved.startswith("gemini-") or resolved.startswith("nano-banana"):
            return "antigravity"
        return None
    return str(meta["provider"])


def normalize_aspect(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    match = ASPECT_PATTERN.match(text)
    if not match:
        raise ImageGenError(f"Unsupported aspect ratio: {raw}")
    if match.group("name"):
        alias = match.group("name").lower()
        if alias in ASPECT_ALIASES:
            return ASPECT_ALIASES[alias]
        raise ImageGenError(f"Unknown aspect alias: {raw}")
    width = float(match.group("w"))
    height = float(match.group("h"))
    if width <= 0 or height <= 0:
        raise ImageGenError("Aspect ratio values must be positive.")
    for candidate in SUPPORTED_ASPECTS:
        cw, ch = candidate.split(":")
        if abs(width / height - float(cw) / float(ch)) < 1e-6:
            return candidate
    # Nearest supported aspect.
    target = width / height
    best = min(
        SUPPORTED_ASPECTS,
        key=lambda item: abs(target - (float(item.split(":")[0]) / float(item.split(":")[1]))),
    )
    return best


def parse_size(size: str) -> Tuple[int, int]:
    width, height = size.lower().split("x", maxsplit=1)
    return int(width), int(height)


def pixel_size_for_aspect(aspect: str, resolution: Optional[str]) -> str:
    """Explicit WIDTHxHEIGHT so OpenAI-compatible hosts cannot default to 16:9."""
    long_edge = 2048 if (resolution or "1k") == "2k" else 1024
    width_n, height_n = (float(part) for part in aspect.split(":", maxsplit=1))
    if width_n >= height_n:
        width = long_edge
        height = max(16, int(round(long_edge * height_n / width_n / 16.0)) * 16)
    else:
        height = long_edge
        width = max(16, int(round(long_edge * width_n / height_n / 16.0)) * 16)
    return f"{width}x{height}"


def aspect_ratio_value(aspect: str) -> float:
    width_n, height_n = (float(part) for part in aspect.split(":", maxsplit=1))
    return width_n / height_n


def dimensions_match_aspect(width: int, height: int, aspect: str, tolerance: float = 0.04) -> bool:
    if width <= 0 or height <= 0:
        return False
    return abs((width / height) - aspect_ratio_value(aspect)) <= tolerance


def describe_dimensions(width: int, height: int) -> str:
    for candidate in SUPPORTED_ASPECTS:
        if dimensions_match_aspect(width, height, candidate):
            return candidate
    return f"{width}x{height}"


def read_image_dimensions(path: Path) -> Tuple[int, int]:
    data = path.read_bytes()
    if len(data) >= 24 and data.startswith(b"\x89PNG\r\n\x1a\n"):
        return struct.unpack(">II", data[16:24])
    if data[:2] == b"\xff\xd8":
        index = 2
        while index + 9 < len(data):
            if data[index] != 0xFF:
                index += 1
                continue
            marker = data[index + 1]
            if marker in {0xC0, 0xC1, 0xC2}:
                height, width = struct.unpack(">HH", data[index + 5 : index + 9])
                return width, height
            if marker == 0xD9:
                break
            if marker in {0xD8, 0x01} or 0xD0 <= marker <= 0xD7:
                index += 2
                continue
            if index + 4 > len(data):
                break
            length = struct.unpack(">H", data[index + 2 : index + 4])[0]
            index += 2 + length
    raise ImageGenError(f"Could not read image dimensions from {path}")


def assert_saved_aspect(paths: Sequence[Path], *aspects: Optional[str]) -> None:
    accepted = [item for item in aspects if item]
    if not accepted:
        return
    for path in paths:
        width, height = read_image_dimensions(path)
        if any(dimensions_match_aspect(width, height, item) for item in accepted):
            continue
        actual = describe_dimensions(width, height)
        wanted = " or ".join(accepted)
        message = (
            f"Requested aspect {wanted} but {path.name} is {width}x{height} ({actual}). "
            "The backend ignored the ratio (many OpenAI-compatible hosts default to 16:9). "
            "Retry with --provider grok and no XAI_BASE_URL, or pass --size for an explicit canvas."
        )
        write_aspect_fail_receipt(path, message, wanted, f"{width}x{height}", actual)
        raise ImageGenError(message)


def aspect_from_size(size: str) -> str:
    width, height = parse_size(size)
    return normalize_aspect(f"{width}:{height}") or "1:1"


def nearest_codex_size(aspect: Optional[str], size: Optional[str]) -> str:
    if size and size != "auto":
        width, height = parse_size(size)
        aspect = normalize_aspect(f"{width}:{height}")
    aspect = aspect or "1:1"
    return CODEX_ASPECT_TO_SIZE.get(aspect, "1024x1024")


def map_grok_quality(quality: str, resolution: Optional[str]) -> Tuple[Optional[str], Optional[str], List[str]]:
    notes: List[str] = []
    grok_quality: Optional[str] = None
    grok_resolution = resolution
    if quality == "low":
        grok_quality = "low"
    elif quality in {"medium", "auto"}:
        grok_quality = "medium"
    elif quality == "high":
        grok_quality = "medium"
        if not grok_resolution:
            grok_resolution = "2k"
            notes.append("Mapped --quality high to Grok quality=medium and resolution=2k.")
        else:
            notes.append("Mapped --quality high to Grok quality=medium (maximum for grok-imagine-image-2.0).")
    if grok_resolution == "4k":
        raise ImageGenError("Grok Imagine supports resolution 1k or 2k, not 4k.")
    return grok_quality, grok_resolution, notes


def map_gemini_image_size(quality: str, resolution: Optional[str]) -> str:
    if resolution == "4k":
        return "4K"
    if resolution == "2k" or quality == "high":
        return "2K"
    return "1K"


def detect_harness() -> Optional[str]:
    if os.environ.get("GROK_AGENT") or os.environ.get("GROK_SESSION_ID") or os.environ.get("GROK_HOME"):
        return "grok"
    if os.environ.get("CODEX_THREAD_ID") or os.environ.get("CODEX_HOME"):
        return "codex"
    if (
        os.environ.get("ANTIGRAVITY")
        or os.environ.get("ANTIGRAVITY_PROJECT_ID")
        or os.environ.get("ANTIGRAVITY_LS_ADDRESS")
        or os.environ.get("AGY_BIN")
    ):
        return "antigravity"
    if os.environ.get("CURSOR_AGENT") or os.environ.get("CURSOR_CLI"):
        return "cursor"
    return None


def atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        try:
            tmp_path.chmod(0o600)
        except OSError:
            pass
        tmp_path.replace(path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def read_json(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ImageGenError(f"Missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ImageGenError(f"Cannot parse {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ImageGenError(f"{path} must contain a JSON object.")
    return data


def pad_base64url(value: str) -> str:
    return value + "=" * (-len(value) % 4)


def decode_jwt_payload(token: str) -> Dict[str, Any]:
    parts = token.split(".")
    if len(parts) < 2:
        raise ImageGenError("Token is not a JWT.")
    try:
        payload = base64.urlsafe_b64decode(pad_base64url(parts[1]))
        data = json.loads(payload.decode("utf-8"))
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ImageGenError(f"Cannot decode JWT payload: {exc}") from exc
    if not isinstance(data, dict):
        raise ImageGenError("JWT payload is not an object.")
    return data


def jwt_expired(token: str, *, now: Optional[dt.datetime] = None) -> bool:
    payload = decode_jwt_payload(token)
    exp = payload.get("exp")
    if not isinstance(exp, (int, float)):
        return False
    current = (now or utc_now()).timestamp()
    return current >= (float(exp) - TOKEN_EXPIRY_SKEW_SECONDS)


def iso_expired(value: str, *, now: Optional[dt.datetime] = None) -> bool:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        stamp = dt.datetime.fromisoformat(text)
    except ValueError:
        return True
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=dt.timezone.utc)
    current = now or utc_now()
    return current.timestamp() >= (stamp.timestamp() - TOKEN_EXPIRY_SKEW_SECONDS)


SECRET_QUERY_RE = re.compile(r"([?&](?:key|api_key|access_token)=)[^&\s]+", re.IGNORECASE)
BEARER_RE = re.compile(r"(Bearer\s+)\S+", re.IGNORECASE)
USERINFO_RE = re.compile(r"(https?://)[^/\s]+@", re.IGNORECASE)


def redact_secrets(text: str) -> str:
    out = SECRET_QUERY_RE.sub(r"\1***", text)
    out = BEARER_RE.sub(r"\1***", out)
    return USERINFO_RE.sub(r"\1***@", out)


def http_request(
    url: str,
    *,
    method: str = "POST",
    headers: Optional[Dict[str, str]] = None,
    body: Optional[bytes] = None,
    timeout: int = REQUEST_TIMEOUT,
    expect_json: bool = True,
) -> Tuple[int, Any, Dict[str, str]]:
    request = urllib.request.Request(url=url, data=body, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
            text = raw.decode(charset, errors="replace")
            header_map = {k.lower(): v for k, v in response.headers.items()}
            if not expect_json:
                return response.status, raw, header_map
            if not text.strip():
                return response.status, {}, header_map
            return response.status, json.loads(text), header_map
    except TimeoutError as exc:
        raise ImageGenError("Request timed out.") from exc
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise ImageGenError(f"HTTP {exc.code}: {raw.strip() or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise ImageGenError(f"Network error: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ImageGenError(f"Non-JSON response from {redact_secrets(url)}: {exc}") from exc


def package_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_share_home() -> Path:
    override = os.environ.get("LOCAL_IMAGE_GEN_HOME", "").strip()
    if override:
        return Path(os.path.expanduser(override)).resolve()
    return (Path.home() / ".local" / "share" / "local-image-gen").resolve()


def install_source(root: Path) -> str:
    try:
        if root.resolve() == default_share_home():
            return "share"
    except OSError:
        pass
    return "checkout"


def repo_slug() -> str:
    slug = os.environ.get("LOCAL_IMAGE_GEN_REPO", DEFAULT_REPO_SLUG).strip() or DEFAULT_REPO_SLUG
    if not REPO_SLUG_RE.fullmatch(slug):
        raise ImageGenError("LOCAL_IMAGE_GEN_REPO must be owner/name.")
    return slug


def latest_version_url(slug: Optional[str] = None) -> str:
    return f"https://raw.githubusercontent.com/{slug or repo_slug()}/main/scripts/local_image_gen.py"


def strip_remote_userinfo(url: str) -> str:
    return USERINFO_RE.sub(r"\1", (url or "").strip()).rstrip("/")


def origin_is_official(url: str, slug: Optional[str] = None) -> bool:
    text = strip_remote_userinfo(url)
    escaped = re.escape(slug or repo_slug())
    return bool(
        re.fullmatch(
            rf"(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/){escaped}(?:\.git)?",
            text,
            re.IGNORECASE,
        )
    )


def parse_published_version(text: str) -> Optional[str]:
    match = PUBLISHED_VERSION_RE.search(text or "")
    return match.group(1) if match else None


def installed_version(root: Path) -> str:
    script = root / "scripts" / "local_image_gen.py"
    try:
        text = script.read_text(encoding="utf-8")
    except OSError:
        return __version__
    return parse_published_version(text) or __version__


def version_tuple(text: str) -> Tuple[int, ...]:
    parts: List[int] = []
    for item in (text or "").split("."):
        if item.isdigit():
            parts.append(int(item))
        else:
            break
    return tuple(parts) or (0,)


def version_is_newer(remote: str, local: str) -> bool:
    return version_tuple(remote) > version_tuple(local)


def update_check_enabled() -> bool:
    flag = os.environ.get("LOCAL_IMAGE_GEN_SKIP_UPDATE_CHECK", "").strip().lower()
    return flag not in {"1", "true", "yes", "on"}


def fetch_latest_version() -> str:
    url = latest_version_url()
    status, raw, _headers = http_request(
        url,
        method="GET",
        timeout=UPDATE_CHECK_TIMEOUT,
        expect_json=False,
    )
    if status != 200:
        raise ImageGenError(f"Version check HTTP {status}.")
    text = raw.decode("utf-8", errors="replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
    version = parse_published_version(text)
    if not version:
        raise ImageGenError("Remote script did not contain __version__.")
    return version


def git_run(root: Path, *args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise ImageGenError("git is required for local-image-gen update.") from exc
    except subprocess.TimeoutExpired as exc:
        raise ImageGenError("git timed out.") from exc


def git_output(root: Path, *args: str, timeout: int = 60) -> str:
    proc = git_run(root, *args, timeout=timeout)
    if proc.returncode != 0:
        err = redact_secrets((proc.stderr or proc.stdout or "git failed").strip())
        raise ImageGenError(err or "git failed")
    return proc.stdout


def inspect_install(root: Optional[Path] = None) -> Dict[str, Any]:
    resolved = (root or package_root()).resolve()
    git = (resolved / ".git").exists()
    dirty: Optional[bool] = None
    if git:
        try:
            dirty = bool(git_output(resolved, "status", "--porcelain", timeout=5).strip())
        except ImageGenError:
            dirty = None
    return {
        "version": installed_version(resolved),
        "latest": None,
        "update_available": None,
        "root": str(resolved),
        "source": install_source(resolved),
        "git": git,
        "dirty": dirty,
        "check_error": None,
    }


def attach_latest_version(info: Dict[str, Any]) -> Dict[str, Any]:
    try:
        latest = fetch_latest_version()
    except ImageGenError as exc:
        info["latest"] = None
        info["update_available"] = None
        info["check_error"] = str(exc)
        return info
    info["latest"] = latest
    info["update_available"] = version_is_newer(latest, str(info.get("version") or ""))
    info["check_error"] = None
    return info


def doctor_payload(loaded_files: Sequence[Path]) -> Dict[str, Any]:
    workspace = find_dyro_workspace()
    output_dir, _detected = default_image_dir()
    install = inspect_install()
    if update_check_enabled():
        attach_latest_version(install)
    else:
        install["check_error"] = "skipped"
    return {
        "success": True,
        "command": "doctor",
        "version": __version__,
        "cli": "local-image-gen",
        "harness": detect_harness(),
        "install": install,
        "dyro": {
            "optional": True,
            "cli": dyro_cli_version(),
            "workspace": str(workspace) if workspace else None,
            "workspace_name": dyro_workspace_name(workspace) if workspace else None,
            "output_dir": str(output_dir),
        },
        "providers": list_provider_status(loaded_files),
    }


def _run_installer(root: Path, *, dry_run: bool) -> str:
    installer = root / "install.sh"
    if not installer.is_file():
        raise ImageGenError(f"missing {installer}")
    cmd = ["bash", str(installer)]
    if dry_run:
        cmd.append("--dry-run")
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError as exc:
        raise ImageGenError("bash is required for local-image-gen update.") from exc
    except subprocess.TimeoutExpired as exc:
        raise ImageGenError("install.sh timed out.") from exc
    output = redact_secrets((proc.stdout or proc.stderr or "").strip())
    if proc.returncode != 0:
        raise ImageGenError(output or "install.sh failed")
    return output


def run_update(*, dry_run: bool = False) -> Dict[str, Any]:
    root = package_root()
    before = inspect_install(root)
    if update_check_enabled():
        attach_latest_version(before)
    if not before["git"]:
        raise ImageGenError(
            f"Not a git checkout: {root}. Re-run the official installer from "
            f"https://github.com/{DEFAULT_REPO_SLUG}"
        )
    if before["dirty"] is True:
        raise ImageGenError(
            f"Working tree is dirty: {root}. Commit or stash, or update "
            f"{default_share_home()} instead."
        )
    if before["dirty"] is not False:
        raise ImageGenError(
            f"Could not determine whether {root} is clean. Refusing to update."
        )
    origin = git_output(root, "remote", "get-url", "origin").strip()
    if not origin_is_official(origin):
        raise ImageGenError(
            f"origin is not github.com/{repo_slug()}. Refusing to update."
        )
    branch = git_output(root, "rev-parse", "--abbrev-ref", "HEAD").strip()
    if branch not in {"main", "master"}:
        raise ImageGenError(
            f"Refusing to update branch {branch!r}. Checkout main first."
        )
    pull_args = ["pull", "--ff-only", "origin", "main" if branch == "main" else branch]
    if dry_run:
        pull_args.append("--dry-run")
    pull = git_run(root, *pull_args, timeout=120)
    pull_out = redact_secrets((pull.stdout or pull.stderr or "").strip())
    if pull.returncode != 0:
        raise ImageGenError(pull_out or "git pull --ff-only failed")
    installer_out = _run_installer(root, dry_run=dry_run)
    after = inspect_install(root)
    after["latest"] = before.get("latest")
    latest = after.get("latest")
    if latest:
        after["update_available"] = version_is_newer(str(latest), str(after.get("version") or ""))
    after["check_error"] = before.get("check_error")
    return {
        "success": True,
        "command": "update",
        "dry_run": dry_run,
        "from": before["version"],
        "to": after["version"],
        "install": after,
        "steps": [
            {"step": "git pull --ff-only", "dry_run": dry_run, "output": pull_out},
            {"step": "install.sh", "dry_run": dry_run, "output": installer_out},
        ],
    }


def guess_mime(path: Path) -> str:
    return mimetypes.guess_type(str(path))[0] or "application/octet-stream"


def encode_data_url(path: Path) -> str:
    if not path.is_file():
        raise ImageGenError(f"Image not found: {path}")
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{guess_mime(path)};base64,{payload}"


def normalize_image_source(value: str) -> str:
    text = value.strip()
    if not text:
        raise ImageGenError("Empty image path.")
    lowered = text.lower()
    if lowered.startswith(("http://", "https://", "data:")):
        return text
    return encode_data_url(Path(os.path.expandvars(os.path.expanduser(text))))


def download_bytes(url: str) -> Tuple[bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "local-image-gen/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            mime = response.headers.get_content_type() or "application/octet-stream"
            return response.read(), mime
    except urllib.error.HTTPError as exc:
        raise ImageGenError(f"Failed to download {url} (HTTP {exc.code}).") from exc
    except urllib.error.URLError as exc:
        raise ImageGenError(f"Failed to download {url}: {exc.reason}") from exc


def load_local_image_bytes(source: str) -> Tuple[bytes, str]:
    text = source.strip()
    if text.startswith("data:"):
        match = re.match(r"^data:(?P<mime>[^;,]+)?(?P<b64>;base64)?,(?P<data>.*)$", text, re.DOTALL)
        if not match:
            raise ImageGenError("Invalid data URL.")
        mime = match.group("mime") or "application/octet-stream"
        data = match.group("data")
        if match.group("b64"):
            return base64.b64decode(data), mime
        return urllib.parse.unquote_to_bytes(data), mime
    if text.lower().startswith(("http://", "https://")):
        return download_bytes(text)
    path = Path(os.path.expandvars(os.path.expanduser(text)))
    if not path.is_file():
        raise ImageGenError(f"Image not found: {path}")
    return path.read_bytes(), guess_mime(path)


def suffix_for_mime(mime: str) -> str:
    return {"image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}.get(mime, ".png")


def materialize_image_file(source: str, directory: Path, index: int) -> Path:
    raw, mime = load_local_image_bytes(source)
    target = directory / f"input-{index}{suffix_for_mime(mime)}"
    target.write_bytes(raw)
    return target


def encode_multipart(
    fields: Dict[str, Any],
    file_fields: Sequence[Tuple[str, Path]],
) -> Tuple[str, bytes]:
    boundary = f"----local-image-gen-{uuid.uuid4().hex}"
    chunks: List[bytes] = []
    for name, value in fields.items():
        if value is None:
            continue
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"),
                str(value).encode("utf-8"),
                b"\r\n",
            ]
        )
    for field_name, path in file_fields:
        filename = path.name
        content_type = guess_mime(path)
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                (
                    f'Content-Disposition: form-data; name="{field_name}"; '
                    f'filename="{filename}"\r\n'
                ).encode("utf-8"),
                f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
                path.read_bytes(),
                b"\r\n",
            ]
        )
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return boundary, b"".join(chunks)


def unique_output_path(path: Path, overwrite: bool) -> Path:
    if overwrite or not path.exists():
        return path
    for version in range(2, 10000):
        candidate = path.with_name(f"{path.stem}-v{version}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise ImageGenError(f"Could not allocate an output path for {path}")


def default_output_path(prompt: str, out_dir: Path, fmt: str) -> Path:
    digest = hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:12]
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = {".jpg": ".jpg", "jpeg": ".jpg", "jpg": ".jpg", "webp": ".webp"}.get(fmt, ".png")
    if fmt in {".jpg", "jpeg", "jpg"}:
        suffix = ".jpg"
    elif fmt == "webp":
        suffix = ".webp"
    else:
        suffix = ".png"
    return out_dir / f"{DEFAULT_OUTPUT_STEM}-{stamp}-{digest}{suffix}"


def find_dyro_workspace(start: Optional[Path] = None) -> Optional[Path]:
    """Return the nearest ancestor that contains dyro.toml, if any."""
    current = (start or Path.cwd()).expanduser()
    try:
        current = current.resolve()
    except OSError:
        return None
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / DYRO_TOML_NAME).is_file():
            return candidate
    return None


def dyro_workspace_name(root: Path) -> Optional[str]:
    path = root / DYRO_TOML_NAME
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    in_workspace = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            in_workspace = line == "[workspace]"
            continue
        if not in_workspace:
            continue
        match = re.match(r'^name\s*=\s*"(.*)"\s*$', line)
        if match:
            return match.group(1)
    return None


def dyro_cli_version() -> Optional[str]:
    exe = shutil.which("dyro")
    if not exe:
        return None
    try:
        proc = subprocess.run(
            [exe, "--version"],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "present"
    text = (proc.stdout or proc.stderr or "").strip().splitlines()
    return text[0] if text else "present"


def default_image_dir(explicit: Optional[Path] = None, start: Optional[Path] = None) -> Tuple[Path, Optional[Path]]:
    """Return (output_dir, dyro_workspace_or_none)."""
    if explicit:
        return explicit.expanduser(), find_dyro_workspace(start)
    workspace = find_dyro_workspace(start)
    if workspace:
        return workspace / DYRO_IMAGE_DIR, workspace
    return (start or Path(".")).expanduser(), None


def strip_env_value(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1]
    if " #" in text:
        text = text.split(" #", maxsplit=1)[0].strip()
    return text


def parse_env_file(path: Path) -> Dict[str, str]:
    if not path.is_file():
        return {}
    values: Dict[str, str] = {}
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    pattern = re.compile(r"^(?:export\s+)?([A-Z][A-Z0-9_]+)\s*=\s*(.+?)\s*$")
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = pattern.match(line)
        if match:
            values[match.group(1)] = strip_env_value(match.group(2))
    return values


def env_search_files(explicit: Optional[Path]) -> List[Path]:
    files: List[Path] = []
    if explicit:
        files.append(explicit.expanduser())
    files.extend(
        [
            Path.cwd() / ".env",
            Path.home() / ".local-image-gen.env",
            Path.home() / ".config" / "local-image-gen.env",
        ]
    )
    return files


def lookup_env(name: str, loaded_files: Sequence[Path]) -> Optional[str]:
    value = os.environ.get(name)
    if value and value.strip():
        return value.strip()
    for path in loaded_files:
        parsed = parse_env_file(path)
        if parsed.get(name):
            return parsed[name]
    return None


def first_env(names: Sequence[str], loaded_files: Sequence[Path]) -> Optional[str]:
    for name in names:
        value = lookup_env(name, loaded_files)
        if value:
            return value
    return None


def normalize_api_base(url: str) -> str:
    value = url.strip().rstrip("/")
    if not value:
        raise ImageGenError("API base URL is empty.")
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ImageGenError(f"API base URL must be an absolute http(s) URL: {url}")
    return value


def resolve_api_base(
    provider: str,
    loaded_files: Sequence[Path],
    override: Optional[str] = None,
) -> Tuple[str, str]:
    """Return (base_url, source) for an API-key path.

    Defaults are official vendor hosts. Custom bases are explicit only.
    """
    if override and str(override).strip():
        return normalize_api_base(str(override)), "flag"
    for name in API_BASE_ENV_NAMES.get(provider, ()):
        value = lookup_env(name, loaded_files)
        if value:
            return normalize_api_base(value), name
    official = OFFICIAL_API_BASES.get(provider)
    if official:
        return official.rstrip("/"), "official"
    raise ImageGenError(f"{provider} does not have an API base.")


def optional_api_base(provider: str, loaded_files: Sequence[Path]) -> Tuple[Optional[str], Optional[str]]:
    try:
        base, source = resolve_api_base(provider, loaded_files)
        return base, source
    except ImageGenError:
        return None, None


def grok_auth_available() -> bool:
    return GROK_AUTH_PATH.is_file()


def codex_auth_available() -> bool:
    return CODEX_AUTH_PATH.is_file()


def find_agy() -> Optional[Path]:
    for candidate in (
        os.environ.get("ANTIGRAVITY_CLI"),
        os.environ.get("AGY_BIN"),
        shutil.which("agy"),
        str(Path.home() / ".local" / "bin" / "agy"),
        str(Path.home() / ".gemini" / "antigravity-cli" / "bin" / "agy"),
    ):
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if path.is_file() and os.access(path, os.X_OK):
            return path
    return None


def antigravity_auth_available() -> bool:
    if find_agy() is None:
        return False
    home = Path.home() / ".gemini" / "antigravity-cli"
    return (home / "settings.json").is_file() or (home / "cache" / "onboarding.json").is_file()


def find_cursor_agent() -> Optional[Path]:
    for candidate in (
        os.environ.get("CURSOR_AGENT"),
        os.environ.get("CURSOR_CLI"),
        shutil.which("cursor-agent"),
        str(Path.home() / ".local" / "bin" / "cursor-agent"),
    ):
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if path.is_file() and os.access(path, os.X_OK):
            return path
    return None


def cursor_auth_available() -> bool:
    if find_cursor_agent() is None:
        return False
    config = Path.home() / ".cursor" / "cli-config.json"
    if not config.is_file():
        return False
    try:
        data = read_json(config)
    except ImageGenError:
        return False
    auth = data.get("authInfo")
    if not isinstance(auth, dict):
        return False
    return bool(auth.get("email") or auth.get("userId") or auth.get("authId"))


def to_agy_image_model(model: str) -> str:
    mapping = {
        "gemini-3.1-flash-image-preview": "gemini-3.1-flash-image",
        "gemini-3-pro-image-preview": "gemini-3-pro-image",
        "gemini-2.5-flash-image": "gemini-2.5-flash-image-preview",
        "gemini-3.1-flash-lite-image-preview": "gemini-3.1-flash-lite-image",
    }
    return mapping.get(model, model)


def build_agy_worker_prompt(
    prompt: str,
    model: str,
    aspect: Optional[str],
    image_size: str,
    images: Sequence[str],
    output: Path,
) -> str:
    image_name = output.stem
    lines = [
        "You are a non-interactive image worker.",
        "Call the generate_image tool exactly once.",
        "Do not write code, search the web, edit files, or create extra documents.",
        f"generate_image.prompt: {prompt}",
        f"generate_image.model_name: {to_agy_image_model(model)}",
        f"generate_image.image_name: {image_name}",
        f"generate_image.aspect_ratio: {aspect or '1:1'}",
        f"Save the generated file to this exact path: {output.resolve()}",
        f"Prefer {image_size} output when the tool allows a resolution choice.",
    ]
    if images:
        abs_images = []
        for item in images:
            if item.lower().startswith(("http://", "https://", "data:")):
                abs_images.append(item)
            else:
                abs_images.append(str(Path(os.path.expandvars(os.path.expanduser(item))).resolve()))
        lines.append("generate_image.image_paths: " + json.dumps(abs_images, ensure_ascii=False))
    lines.append('When finished, print only this JSON: {"success": true, "image": "/absolute/path.png"}')
    return "\n".join(lines)


def build_agy_command(agy: Path, worker_prompt: str) -> List[str]:
    return [
        str(agy),
        "--dangerously-skip-permissions",
        "--disable-slash-commands",
        "--output-format",
        "json",
        "--print-timeout",
        "5m0s",
        "--print",
        worker_prompt,
    ]


def extract_image_paths(payload: Any) -> List[Path]:
    found: List[Path] = []

    def consider(value: str) -> None:
        text = value.strip().strip('"').strip("'")
        if not text or len(text) < 4:
            return
        lowered = text.lower()
        if not any(lowered.endswith(suffix) or suffix in lowered for suffix in (".png", ".jpg", ".jpeg", ".webp", ".gif")):
            return
        if lowered.startswith(("http://", "https://", "data:")):
            return
        path = Path(os.path.expandvars(os.path.expanduser(text.split()[0].strip(",;"))))
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            found.append(path)

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in {"image", "file_path", "filePath", "path", "generated_image", "generatedImage", "image_path", "imagePath"} and isinstance(value, str):
                    consider(value)
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, str):
            for match in re.findall(r"(?:~|/|\./)[^\s\"']+\.(?:png|jpg|jpeg|webp|gif)", node, re.IGNORECASE):
                consider(match)

    walk(payload)
    return found


def harvest_new_images(directory: Path, since: float) -> List[Path]:
    if not directory.is_dir():
        return []
    hits: List[Path] = []
    for path in directory.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            continue
        try:
            if path.stat().st_mtime + 0.05 >= since:
                hits.append(path)
        except OSError:
            continue
    hits.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return hits


def copy_to_output(source: Path, output: Path, overwrite: bool) -> Path:
    if not source.is_file():
        raise ImageGenError(f"Reported image does not exist: {source}")
    target = unique_output_path(output, overwrite)
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != target.resolve():
        shutil.copy2(source, target)
        return target
    return source


def run_antigravity(
    prompt: str,
    model: str,
    aspect: Optional[str],
    image_size: str,
    images: Sequence[str],
    output: Path,
    overwrite: bool,
    dry_run: bool,
) -> Dict[str, Any]:
    agy = find_agy()
    if agy is None and not dry_run:
        raise ImageGenError("Antigravity CLI (`agy`) was not found. Install it or set AGY_BIN.")
    worker_prompt = build_agy_worker_prompt(prompt, model, aspect, image_size, images, output)
    command = build_agy_command(agy or Path("agy"), worker_prompt)
    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "provider": "antigravity",
            "auth": "subscription",
            "model": to_agy_image_model(model),
            "endpoint": "agy --print generate_image",
            "command": command[:7] + ["<prompt>"],
            "request": {
                "model_name": to_agy_image_model(model),
                "aspect_ratio": aspect or "1:1",
                "image_size": image_size,
                "image_count": len(images),
                "output": str(output),
            },
            "output": str(output),
        }
    if not antigravity_auth_available():
        raise ImageGenError("Antigravity CLI is not logged in. Open `agy` and complete Google login.")

    started = time.time()
    try:
        completed = subprocess.run(
            command,
            cwd=str(output.parent.resolve()),
            capture_output=True,
            text=True,
            timeout=REQUEST_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ImageGenError("Antigravity CLI timed out while generating the image.") from exc
    except OSError as exc:
        raise ImageGenError(f"Failed to start Antigravity CLI: {exc}") from exc

    combined = (completed.stdout or "") + "\n" + (completed.stderr or "")
    candidates: List[Path] = []
    try:
        parsed = json.loads(completed.stdout) if completed.stdout and completed.stdout.strip().startswith("{") else None
    except json.JSONDecodeError:
        parsed = None
    if parsed is not None:
        candidates.extend(extract_image_paths(parsed))
    candidates.extend(extract_image_paths(combined))
    if output.is_file() and output.stat().st_mtime + 0.05 >= started:
        candidates.insert(0, output)
    candidates.extend(harvest_new_images(output.parent, started))

    existing = [path.expanduser() for path in candidates if path.expanduser().is_file()]
    if not existing:
        details = combined.strip()[-1200:]
        raise ImageGenError(
            "Antigravity CLI finished without a saved image. "
            "Open `agy` and confirm generate_image is available. "
            f"Exit {completed.returncode}. {details}"
        )
    saved = copy_to_output(existing[0], output, overwrite)
    assert_saved_aspect([saved], aspect)
    return {
        "success": True,
        "provider": "antigravity",
        "auth": "subscription",
        "model": to_agy_image_model(model),
        "image": str(saved),
        "images": [str(saved)],
        "aspect_ratio": aspect,
        "resolution": image_size.lower(),
    }


def resolve_local_image_sources(images: Sequence[str]) -> List[str]:
    resolved: List[str] = []
    for item in images:
        if item.lower().startswith(("http://", "https://", "data:")):
            resolved.append(item)
        else:
            resolved.append(str(Path(os.path.expandvars(os.path.expanduser(item))).resolve()))
    return resolved


def build_cursor_worker_prompt(
    prompt: str,
    aspect: Optional[str],
    image_size: str,
    images: Sequence[str],
    output: Path,
) -> str:
    lines = [
        "You are a non-interactive image worker.",
        "Call the GenerateImage / cursor/generate_image tool exactly once.",
        "Do not write code, search the web, or create extra documents.",
        f"GenerateImage.description: {prompt}",
        f"GenerateImage.file_path: {output.resolve()}",
        f"GenerateImage.aspect_ratio: {aspect or '1:1'}",
        f"Prefer {image_size} if the tool exposes a resolution or quality choice.",
        "Cursor's built-in image backend is Google Nano Banana Pro.",
    ]
    refs = resolve_local_image_sources(images)
    if refs:
        lines.append("GenerateImage.reference_image_paths: " + json.dumps(refs, ensure_ascii=False))
    lines.append('When finished, print only this JSON: {"success": true, "image": "/absolute/path.png"}')
    return "\n".join(lines)


def build_cursor_command(binary: Path, worker_prompt: str, workspace: Path) -> List[str]:
    return [
        str(binary),
        "--print",
        "--force",
        "--trust",
        "--output-format",
        "json",
        "--workspace",
        str(workspace),
        worker_prompt,
    ]


def collect_cli_image_candidates(stdout: str, stderr: str, output: Path, started: float) -> List[Path]:
    combined = (stdout or "") + "\n" + (stderr or "")
    candidates: List[Path] = []
    try:
        parsed = json.loads(stdout) if stdout and stdout.strip().startswith("{") else None
    except json.JSONDecodeError:
        parsed = None
    if parsed is not None:
        candidates.extend(extract_image_paths(parsed))
    candidates.extend(extract_image_paths(combined))
    if output.is_file() and output.stat().st_mtime + 0.05 >= started:
        candidates.insert(0, output)
    candidates.extend(harvest_new_images(output.parent, started))
    return [path.expanduser() for path in candidates if path.expanduser().is_file()]


def run_cursor(
    prompt: str,
    model: str,
    aspect: Optional[str],
    image_size: str,
    images: Sequence[str],
    output: Path,
    overwrite: bool,
    dry_run: bool,
) -> Dict[str, Any]:
    binary = find_cursor_agent()
    if binary is None and not dry_run:
        raise ImageGenError("Cursor CLI (`cursor-agent`) was not found. Install it or set CURSOR_AGENT.")
    worker_prompt = build_cursor_worker_prompt(prompt, aspect, image_size, images, output)
    command = build_cursor_command(binary or Path("cursor-agent"), worker_prompt, output.parent.resolve())
    notes = [
        "Cursor CLI image gen is Nano Banana Pro. Model/quality flags are best-effort in the worker prompt."
    ]
    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "provider": "cursor",
            "auth": "subscription",
            "model": "gemini-3-pro-image",
            "endpoint": "cursor-agent --print GenerateImage",
            "command": command[:8] + ["<prompt>"],
            "request": {
                "aspect_ratio": aspect or "1:1",
                "image_size": image_size,
                "image_count": len(images),
                "output": str(output),
                "requested_model": model,
            },
            "notes": notes,
            "output": str(output),
        }
    if not cursor_auth_available():
        raise ImageGenError("Cursor CLI is not logged in. Run: cursor-agent login")

    started = time.time()
    try:
        completed = subprocess.run(
            command,
            cwd=str(output.parent.resolve()),
            capture_output=True,
            text=True,
            timeout=REQUEST_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ImageGenError("Cursor CLI timed out while generating the image.") from exc
    except OSError as exc:
        raise ImageGenError(f"Failed to start Cursor CLI: {exc}") from exc

    existing = collect_cli_image_candidates(completed.stdout or "", completed.stderr or "", output, started)
    if not existing:
        details = ((completed.stdout or "") + "\n" + (completed.stderr or "")).strip()[-1200:]
        raise ImageGenError(
            "Cursor CLI finished without a saved image. "
            "Confirm GenerateImage is enabled for this account. "
            f"Exit {completed.returncode}. {details}"
        )
    saved = copy_to_output(existing[0], output, overwrite)
    assert_saved_aspect([saved], aspect)
    return {
        "success": True,
        "provider": "cursor",
        "auth": "subscription",
        "model": "gemini-3-pro-image",
        "image": str(saved),
        "images": [str(saved)],
        "aspect_ratio": aspect,
        "resolution": image_size.lower(),
        "notes": notes,
    }


def load_grok_entry(auth_data: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], str, Dict[str, Any]]:
    data = auth_data if auth_data is not None else read_json(GROK_AUTH_PATH)
    if "key" in data and "refresh_token" in data:
        return data, "root", data
    for key, value in data.items():
        if isinstance(value, dict) and (value.get("key") or value.get("refresh_token")):
            return data, str(key), value
    raise ImageGenError(f"{GROK_AUTH_PATH} does not contain a Grok login entry. Run: grok login")


def grok_access_token(entry: Dict[str, Any]) -> str:
    token = entry.get("key") or entry.get("access_token")
    if not isinstance(token, str) or not token.strip():
        raise ImageGenError("Grok auth.json is missing an access token. Run: grok login")
    return token.strip()


def grok_needs_refresh(entry: Dict[str, Any]) -> bool:
    expires_at = entry.get("expires_at")
    token = entry.get("key") or entry.get("access_token")
    if isinstance(expires_at, str) and expires_at.strip():
        return iso_expired(expires_at)
    if isinstance(token, str) and token.count(".") == 2:
        try:
            return jwt_expired(token)
        except ImageGenError:
            return True
    return True


def refresh_grok_auth() -> Tuple[str, str]:
    data, entry_key, entry = load_grok_entry()
    if not grok_needs_refresh(entry):
        return grok_access_token(entry), "subscription"
    refresh_token = entry.get("refresh_token")
    if not isinstance(refresh_token, str) or not refresh_token:
        raise ImageGenError("Grok access token expired and no refresh_token is stored. Run: grok login")
    client_id = entry.get("oidc_client_id") or GROK_DEFAULT_CLIENT_ID
    form = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
    ).encode("utf-8")
    try:
        _, payload, _ = http_request(
            GROK_REFRESH_ENDPOINT,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            body=form,
        )
    except ImageGenError as exc:
        raise ImageGenError("Failed to refresh Grok login. Run: grok login") from exc
    if not isinstance(payload, dict):
        raise ImageGenError("Grok token endpoint returned a non-object.")
    access = payload.get("access_token")
    if not isinstance(access, str) or not access:
        raise ImageGenError("Grok token refresh did not return access_token. Run: grok login")
    updated = dict(entry)
    updated["key"] = access
    if payload.get("refresh_token"):
        updated["refresh_token"] = payload["refresh_token"]
    expires_in = payload.get("expires_in")
    if isinstance(expires_in, (int, float)):
        updated["expires_at"] = (utc_now() + dt.timedelta(seconds=float(expires_in))).isoformat().replace("+00:00", "Z")
    if entry_key == "root":
        new_data = updated
    else:
        new_data = dict(data)
        new_data[entry_key] = updated
    atomic_write_json(GROK_AUTH_PATH, new_data)
    return access, "subscription"


def refresh_codex_auth() -> Tuple[str, str, str]:
    if not CODEX_AUTH_PATH.is_file():
        raise ImageGenError(f"Missing {CODEX_AUTH_PATH}. Run: codex auth login")
    auth_data = read_json(CODEX_AUTH_PATH)
    tokens = dict(auth_data.get("tokens") or {})
    access = tokens.get("access_token")
    if not isinstance(access, str) or not access:
        raise ImageGenError("Codex auth.json is missing tokens.access_token. Run: codex auth login")
    try:
        expired = jwt_expired(access)
    except ImageGenError:
        expired = True
    if expired:
        refresh_token = tokens.get("refresh_token")
        if not isinstance(refresh_token, str) or not refresh_token:
            raise ImageGenError("Codex access token expired. Run: codex auth login")
        form = urllib.parse.urlencode(
            {
                "client_id": CODEX_REFRESH_CLIENT_ID,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            }
        ).encode("utf-8")
        try:
            _, payload, _ = http_request(
                CODEX_REFRESH_ENDPOINT,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                    "User-Agent": "codex_cli_rs/0.0.0 (local-image-gen)",
                },
                body=form,
            )
        except ImageGenError as exc:
            raise ImageGenError("Failed to refresh Codex login. Run: codex auth login") from exc
        if not isinstance(payload, dict):
            raise ImageGenError("Codex token endpoint returned a non-object.")
        updated = dict(tokens)
        for key in ("access_token", "refresh_token", "id_token"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                updated[key] = value
        auth_data = dict(auth_data)
        auth_data["tokens"] = updated
        auth_data["last_refresh"] = utc_now_iso()
        atomic_write_json(CODEX_AUTH_PATH, auth_data)
        tokens = updated
        access = tokens["access_token"]
    payload = decode_jwt_payload(str(access))
    openai_auth = payload.get("https://api.openai.com/auth")
    account_id = None
    if isinstance(openai_auth, dict):
        account_id = openai_auth.get("chatgpt_account_id")
    account_id = account_id or payload.get("chatgpt_account_id") or payload.get("account_id") or tokens.get("account_id")
    if not account_id:
        raise ImageGenError("Cannot extract ChatGPT-Account-ID from Codex login.")
    return str(access), str(account_id), "subscription"


def extract_image_candidates(event_payload: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    finals: List[str] = []
    partials: List[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "image_generation_call" and isinstance(node.get("result"), str) and node["result"].strip():
                finals.append(node["result"].strip())
            partial = node.get("partial_image_b64")
            if isinstance(partial, str) and partial.strip():
                partials.append(partial.strip())
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(event_payload)
    return finals, partials


def stream_codex_image(access_token: str, account_id: str, request_body: Dict[str, Any]) -> str:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "User-Agent": "codex_cli_rs/0.0.0",
        "originator": "codex_cli_rs",
        "ChatGPT-Account-ID": account_id,
    }
    request = urllib.request.Request(
        url=CODEX_RESPONSES_ENDPOINT,
        data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    finals: List[str] = []
    partials: List[str] = []
    event_lines: List[str] = []

    def consume(lines: Iterable[str]) -> Optional[bool]:
        data_parts = [item[5:].lstrip() for item in lines if item.startswith("data:")]
        if not data_parts:
            return None
        payload_text = "\n".join(data_parts).strip()
        if not payload_text:
            return None
        if payload_text == "[DONE]":
            return True
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            return None
        more_finals, more_partials = extract_image_candidates(payload)
        finals.extend(more_finals)
        partials.extend(more_partials)
        return None

    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            while True:
                raw_line = response.readline()
                if not raw_line:
                    if event_lines:
                        consume(event_lines)
                    break
                line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                if line == "":
                    done = consume(event_lines)
                    event_lines = []
                    if done:
                        break
                    continue
                if line.startswith(":"):
                    continue
                event_lines.append(line)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace").strip()
        if exc.code == 401:
            raise ImageGenError("Codex returned 401. Run: codex auth login") from exc
        if exc.code == 403:
            raise ImageGenError(
                "Codex returned 403. Check User-Agent, originator, and ChatGPT-Account-ID; this is usually not a prompt issue."
            ) from exc
        raise ImageGenError(f"Codex Responses API failed (HTTP {exc.code}): {body or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise ImageGenError(f"Cannot reach Codex Responses API: {exc.reason}") from exc

    if finals:
        return finals[-1]
    if partials:
        return partials[-1]
    raise ImageGenError("Codex SSE stream ended without image data.")


def build_codex_request(prompt: str, model: str, size: str, quality: str, images: Sequence[str]) -> Dict[str, Any]:
    content: List[Dict[str, Any]] = [{"type": "input_text", "text": prompt}]
    for source in images:
        content.append({"type": "input_image", "image_url": normalize_image_source(source)})
    tool_quality = "medium" if quality == "auto" else quality
    return {
        "model": CODEX_RESPONSE_MODEL,
        "store": False,
        "instructions": (
            "You are an assistant that must fulfill image generation and image editing "
            "requests by using the image_generation tool when provided."
        ),
        "input": [{"type": "message", "role": "user", "content": content}],
        "tools": [
            {
                "type": "image_generation",
                "model": model,
                "size": size,
                "quality": tool_quality,
                "output_format": "png",
                "background": "opaque",
                "partial_images": 1,
            }
        ],
        "tool_choice": {
            "type": "allowed_tools",
            "mode": "required",
            "tools": [{"type": "image_generation"}],
        },
        "stream": True,
    }


def save_b64_image(image_b64: str, output: Path) -> Path:
    try:
        payload = base64.b64decode(image_b64, validate=False)
    except binascii.Error as exc:
        raise ImageGenError(f"Returned image was not valid base64: {exc}") from exc
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)
    return output


def save_url_image(url: str, output: Path) -> Path:
    request = urllib.request.Request(url, headers={"User-Agent": "local-image-gen/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        raise ImageGenError(f"Failed to download image URL (HTTP {exc.code}).") from exc
    except urllib.error.URLError as exc:
        raise ImageGenError(f"Failed to download image URL: {exc.reason}") from exc
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)
    return output


def save_openai_image_items(items: Sequence[Dict[str, Any]], output: Path, overwrite: bool) -> List[Path]:
    saved: List[Path] = []
    for index, item in enumerate(items):
        target = output if len(items) == 1 else output.with_name(f"{output.stem}-{index + 1}{output.suffix}")
        target = unique_output_path(target, overwrite)
        b64 = item.get("b64_json")
        url = item.get("url")
        if isinstance(b64, str) and b64:
            save_b64_image(b64, target)
        elif isinstance(url, str) and url:
            save_url_image(url, target)
        else:
            raise ImageGenError("Image result did not contain b64_json or url.")
        saved.append(target)
    return saved


def grok_image_payload(
    prompt: str,
    model: str,
    aspect: Optional[str],
    quality: Optional[str],
    resolution: Optional[str],
    n: int,
    images: Sequence[str],
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the xAI /images/generations body.

    The official Imagine API takes ``aspect_ratio`` and rejects a pixel
    ``size`` (HTTP 400). Custom OpenAI-compatible bases may ignore the ratio
    and default to 16:9, so only those get an explicit pixel ``size``.
    """
    payload: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "n": n,
        "response_format": "b64_json",
    }
    if aspect:
        payload["aspect_ratio"] = aspect
        if base_url and base_url.rstrip("/") != GROK_API_BASE:
            payload["size"] = pixel_size_for_aspect(aspect, resolution)
    if quality and model == "grok-imagine-image-2.0":
        payload["quality"] = quality
    if resolution:
        payload["resolution"] = resolution
    if images:
        encoded = [normalize_image_source(item) for item in images]
        payload["image"] = {"url": encoded[0], "type": "image_url"}
        if len(encoded) > 1:
            payload["images"] = [{"url": item, "type": "image_url"} for item in encoded[1:]]
    return payload


def run_grok(
    prompt: str,
    model: str,
    aspect: Optional[str],
    quality: Optional[str],
    resolution: Optional[str],
    n: int,
    images: Sequence[str],
    token: str,
    auth_mode: str,
    output: Path,
    overwrite: bool,
    dry_run: bool,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    payload = grok_image_payload(prompt, model, aspect, quality, resolution, n, images, base_url)
    endpoint = f"{(base_url or GROK_API_BASE).rstrip('/')}/{'images/edits' if images else 'images/generations'}"
    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "provider": "grok",
            "auth": auth_mode,
            "model": model,
            "endpoint": endpoint,
            "request": {k: v for k, v in payload.items() if k not in {"image", "images"}},
            "images": list(images),
            "output": str(output),
        }
    _, body, _ = http_request(
        endpoint,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        body=json.dumps(payload).encode("utf-8"),
    )
    if not isinstance(body, dict):
        raise ImageGenError("Grok image API returned a non-object.")
    data = body.get("data")
    if not isinstance(data, list) or not data:
        raise ImageGenError(f"Grok image API returned no image data: {json.dumps(body)[:800]}")
    saved = save_openai_image_items([item for item in data if isinstance(item, dict)], output, overwrite)
    assert_saved_aspect(saved, aspect)
    return {
        "success": True,
        "provider": "grok",
        "auth": auth_mode,
        "model": model,
        "image": str(saved[0]),
        "images": [str(path) for path in saved],
        "aspect_ratio": aspect,
        "size": payload.get("size"),
        "quality": quality,
        "resolution": resolution,
    }


def run_codex(
    prompt: str,
    model: str,
    size: str,
    quality: str,
    images: Sequence[str],
    output: Path,
    overwrite: bool,
    dry_run: bool,
    requested_aspect: Optional[str] = None,
) -> Dict[str, Any]:
    request_body = build_codex_request(prompt, model, size, quality, images)
    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "provider": "codex",
            "auth": "subscription",
            "model": model,
            "endpoint": CODEX_RESPONSES_ENDPOINT,
            "experimental": True,
            "request": {
                "response_model": CODEX_RESPONSE_MODEL,
                "size": size,
                "quality": quality,
                "image_count": len(images),
            },
            "output": str(output),
        }
    access, account_id, auth_mode = refresh_codex_auth()
    image_b64 = stream_codex_image(access, account_id, request_body)
    saved = unique_output_path(output, overwrite)
    save_b64_image(image_b64, saved)
    write_job_receipt(
        {
            "success": True,
            "provider": "codex",
            "auth": auth_mode,
            "experimental": True,
            "model": model,
            "image": str(saved),
            "images": [str(saved)],
            "aspect_ratio": requested_aspect,
            "size": size,
            "quality": quality,
            "prompt": {"original": prompt, "used": prompt},
        }
    )
    mapped = aspect_from_size(size) if size and size != "auto" else None
    assert_saved_aspect([saved], requested_aspect, mapped)
    return {
        "success": True,
        "provider": "codex",
        "auth": auth_mode,
        "experimental": True,
        "model": model,
        "image": str(saved),
        "images": [str(saved)],
        "size": size,
        "quality": quality,
    }


def gemini_parts(prompt: str, images: Sequence[str]) -> List[Dict[str, Any]]:
    parts: List[Dict[str, Any]] = [{"text": prompt}]
    for source in images:
        raw, mime = load_local_image_bytes(source)
        parts.append({"inline_data": {"mime_type": mime, "data": base64.b64encode(raw).decode("ascii")}})
    return parts


def extract_gemini_images(payload: Any) -> List[Tuple[str, str]]:
    found: List[Tuple[str, str]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            inline = node.get("inlineData") or node.get("inline_data")
            if isinstance(inline, dict) and isinstance(inline.get("data"), str) and len(inline["data"]) > 100:
                mime = str(inline.get("mimeType") or inline.get("mime_type") or "image/png")
                if mime.startswith("image/"):
                    found.append((inline["data"], mime))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return found


def run_gemini(
    prompt: str,
    model: str,
    aspect: Optional[str],
    image_size: str,
    images: Sequence[str],
    api_key: Optional[str],
    output: Path,
    overwrite: bool,
    dry_run: bool,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    generation_config = {
        "responseModalities": ["TEXT", "IMAGE"],
        "imageConfig": {"aspectRatio": aspect or "1:1", "imageSize": image_size},
    }
    contents = [{"role": "user", "parts": gemini_parts(prompt, images) if not dry_run else [{"text": prompt}]}]
    api_root = (base_url or GEMINI_API_BASE).rstrip("/")
    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "provider": "gemini",
            "auth": "api_key",
            "model": model,
            "endpoint": f"{api_root}/models/{model}:generateContent",
            "request": {"generationConfig": generation_config, "image_count": len(images)},
            "output": str(output),
        }

    if not api_key:
        raise ImageGenError("Gemini API key is missing.")
    url = f"{api_root}/models/{model}:generateContent"
    _, payload, _ = http_request(
        url,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-goog-api-key": api_key,
        },
        body=json.dumps({"contents": contents, "generationConfig": generation_config}).encode("utf-8"),
    )

    extracted = extract_gemini_images(payload)
    if not extracted:
        raise ImageGenError("Gemini returned no image parts. The subscription may not include this image model.")
    saved: List[Path] = []
    for index, (b64, mime) in enumerate(extracted):
        suffix = { "image/jpeg": ".jpg", "image/webp": ".webp"}.get(mime, output.suffix or ".png")
        target = output if len(extracted) == 1 else output.with_name(f"{output.stem}-{index + 1}{suffix}")
        if target.suffix != suffix:
            target = target.with_suffix(suffix)
        target = unique_output_path(target, overwrite)
        save_b64_image(b64, target)
        saved.append(target)
    assert_saved_aspect(saved, aspect)
    return {
        "success": True,
        "provider": "gemini",
        "auth": "api_key",
        "model": model,
        "image": str(saved[0]),
        "images": [str(path) for path in saved],
        "aspect_ratio": aspect,
        "resolution": image_size.lower(),
    }


def run_openai_compat(
    provider: str,
    prompt: str,
    model: str,
    size: str,
    quality: str,
    images: Sequence[str],
    n: int,
    api_key: str,
    base_url: str,
    output: Path,
    overwrite: bool,
    dry_run: bool,
    mask: Optional[Path] = None,
) -> Dict[str, Any]:
    endpoint = f"{base_url}/{'images/edits' if images else 'images/generations'}"
    body: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "n": n,
        "size": size,
        "quality": quality,
    }
    if dry_run:
        request = dict(body)
        if images and provider != "xai":
            request["transport"] = "multipart"
            request["image_count"] = len(images)
            request["mask"] = str(mask) if mask else None
        return {
            "success": True,
            "dry_run": True,
            "provider": provider,
            "auth": "api_key",
            "model": model,
            "endpoint": endpoint,
            "request": request,
            "images": list(images),
            "output": str(output),
        }
    if images:
        # xAI Imagine edits stay JSON. Official OpenAI Images edits are multipart.
        if provider == "xai":
            payload = grok_image_payload(prompt, model, None, None if quality == "auto" else quality, None, n, images)
            payload["size"] = size
            _, response, _ = http_request(
                endpoint,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                body=json.dumps(payload).encode("utf-8"),
            )
        else:
            with tempfile.TemporaryDirectory(prefix="local-image-gen-edit-") as tmp:
                tmpdir = Path(tmp)
                file_fields: List[Tuple[str, Path]] = [
                    ("image", materialize_image_file(source, tmpdir, index))
                    for index, source in enumerate(images)
                ]
                if mask:
                    file_fields.append(("mask", mask))
                boundary, payload = encode_multipart(body, file_fields)
                _, response, _ = http_request(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": f"multipart/form-data; boundary={boundary}",
                        "Accept": "application/json",
                    },
                    body=payload,
                )
    else:
        _, response, _ = http_request(
            endpoint,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            body=json.dumps(body).encode("utf-8"),
        )
    if not isinstance(response, dict):
        raise ImageGenError(f"{provider} image API returned a non-object.")
    data = response.get("data")
    if not isinstance(data, list) or not data:
        raise ImageGenError(f"{provider} image API returned no image data: {json.dumps(response)[:800]}")
    saved = save_openai_image_items([item for item in data if isinstance(item, dict)], output, overwrite)
    requested = None
    if size and size != "auto":
        requested = aspect_from_size(size)
    assert_saved_aspect(saved, requested)
    return {
        "success": True,
        "provider": provider,
        "auth": "api_key",
        "model": model,
        "image": str(saved[0]),
        "images": [str(path) for path in saved],
        "size": size,
        "quality": quality,
    }


def list_provider_status(loaded_files: Sequence[Path]) -> List[Dict[str, Any]]:
    grok_base, grok_base_source = optional_api_base("xai", loaded_files)
    gemini_base, gemini_base_source = optional_api_base("gemini", loaded_files)
    openai_base, openai_base_source = optional_api_base("openai", loaded_files)
    rows = [
        {
            "provider": "grok",
            "subscription": grok_auth_available(),
            "login": "grok login" if not grok_auth_available() else str(GROK_AUTH_PATH),
            "api_key": bool(first_env(ENV_KEY_NAMES["xai"], loaded_files)),
            "api_base": grok_base,
            "api_base_source": grok_base_source,
            "default_model": DEFAULT_MODEL_FOR_PROVIDER["grok"],
        },
        {
            "provider": "codex",
            "subscription": codex_auth_available(),
            "login": "codex auth login" if not codex_auth_available() else str(CODEX_AUTH_PATH),
            "api_key": False,
            "experimental": True,
            "notes": "Unofficial ChatGPT Codex image backend. May change or break; review OpenAI terms before depending on it.",
            "default_model": DEFAULT_MODEL_FOR_PROVIDER["codex"],
        },
        {
            "provider": "antigravity",
            "subscription": antigravity_auth_available(),
            "login": "agy (Antigravity login)" if not antigravity_auth_available() else str(find_agy() or "agy"),
            "api_key": False,
            "default_model": DEFAULT_MODEL_FOR_PROVIDER["antigravity"],
        },
        {
            "provider": "cursor",
            "subscription": cursor_auth_available(),
            "login": "cursor-agent login" if not cursor_auth_available() else str(find_cursor_agent() or "cursor-agent"),
            "api_key": False,
            "default_model": DEFAULT_MODEL_FOR_PROVIDER["cursor"],
        },
        {
            "provider": "gemini",
            "subscription": False,
            "login": None,
            "api_key": bool(first_env(ENV_KEY_NAMES["gemini"], loaded_files)),
            "api_base": gemini_base,
            "api_base_source": gemini_base_source,
            "default_model": DEFAULT_MODEL_FOR_PROVIDER["gemini"],
        },
        {
            "provider": "openai",
            "subscription": False,
            "login": None,
            "api_key": bool(first_env(ENV_KEY_NAMES["openai"], loaded_files)),
            "api_base": openai_base,
            "api_base_source": openai_base_source,
            "default_model": DEFAULT_MODEL_FOR_PROVIDER["openai"],
        },
        {
            "provider": "xai",
            "subscription": False,
            "login": None,
            "api_key": bool(first_env(ENV_KEY_NAMES["xai"], loaded_files)),
            "api_base": grok_base,
            "api_base_source": grok_base_source,
            "default_model": DEFAULT_MODEL_FOR_PROVIDER["xai"],
        },
    ]
    return rows


def list_models_payload() -> List[Dict[str, Any]]:
    rows = []
    for model, meta in MODEL_CATALOG.items():
        rows.append(
            {
                "model": model,
                "provider": meta["provider"],
                "aliases": list(meta.get("aliases") or ()),
                "resolutions": list(meta.get("resolutions") or ()),
                "qualities": list(meta.get("qualities") or ()),
            }
        )
    return rows


def choose_auto_provider(model: Optional[str], loaded_files: Sequence[Path]) -> str:
    hinted = catalog_provider(model)
    harness = detect_harness()
    status = {row["provider"]: row for row in list_provider_status(loaded_files)}

    def usable(name: str) -> bool:
        row = status.get(name)
        if not row:
            return False
        if name == "codex":
            return bool(row["subscription"])
        return bool(row["subscription"] or row["api_key"])

    if hinted == "grok":
        if usable("grok"):
            return "grok"
        if usable("xai"):
            return "xai"
        raise ImageGenError("This Grok Imagine model needs `grok login` or XAI_API_KEY.")
    if hinted == "codex":
        if usable("codex"):
            return "codex"
        if usable("openai"):
            return "openai"
        raise ImageGenError("This gpt-image model needs `codex auth login` or OPENAI_API_KEY.")
    if hinted in {"gemini", "antigravity", "cursor"}:
        if usable("antigravity"):
            return "antigravity"
        if usable("cursor"):
            return "cursor"
        if usable("gemini"):
            return "gemini"
        raise ImageGenError(
            "This Nano Banana model needs Antigravity CLI (`agy`), Cursor CLI (`cursor-agent login`), or GEMINI_API_KEY."
        )
    if harness and usable(harness):
        return harness
    for name in AUTO_PROVIDER_ORDER:
        if usable(name):
            return name
    raise ImageGenError(
        "No image backend is available. Login with grok, Codex, Antigravity (`agy`), or Cursor (`cursor-agent login`), or set an API key. Run --list-providers."
    )


def resolve_nano_banana_provider(loaded_files: Sequence[Path]) -> str:
    return choose_auto_provider("nano-banana", loaded_files)


def resolve_provider(requested: str, model: Optional[str], loaded_files: Sequence[Path]) -> str:
    requested = PROVIDER_ALIASES.get(requested, requested)
    if requested == "gemini":
        return resolve_nano_banana_provider(loaded_files)
    if requested != "auto":
        return requested
    return choose_auto_provider(model, loaded_files)


def extract_chat_text(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise ImageGenError("Prompt compiler returned a non-object.")
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"]
            if isinstance(first.get("text"), str):
                return first["text"]
    raise ImageGenError("Prompt compiler returned no text.")


def extract_gemini_text(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise ImageGenError("Prompt compiler returned a non-object.")
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ImageGenError("Gemini prompt compiler returned no text.")
    chunks: List[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("thought") is True:
                return
            text = node.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text)
            for key, value in node.items():
                if key in {"text", "thought"}:
                    continue
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(candidates)
    if chunks:
        return "\n".join(chunks)
    raise ImageGenError("Gemini prompt compiler returned no text.")


def grok_optimize_token(loaded_files: Sequence[Path], base_override: Optional[str]) -> Optional[Dict[str, str]]:
    if grok_auth_available():
        return {"provider": "grok", "auth": "subscription", "token": "", "base_url": GROK_API_BASE}
    key = first_env(ENV_KEY_NAMES["xai"], loaded_files)
    if not key:
        return None
    base, _source = resolve_api_base("xai", loaded_files, base_override)
    return {"provider": "grok", "auth": "api_key", "token": key, "base_url": base}


def openai_optimize_token(loaded_files: Sequence[Path], base_override: Optional[str]) -> Optional[Dict[str, str]]:
    key = first_env(ENV_KEY_NAMES["openai"], loaded_files)
    if not key:
        return None
    base, _source = resolve_api_base("openai", loaded_files, base_override)
    return {"provider": "openai", "auth": "api_key", "token": key, "base_url": base}


def gemini_optimize_token(loaded_files: Sequence[Path], base_override: Optional[str]) -> Optional[Dict[str, str]]:
    key = first_env(ENV_KEY_NAMES["gemini"], loaded_files)
    if not key:
        return None
    base, _source = resolve_api_base("gemini", loaded_files, base_override)
    return {"provider": "gemini", "auth": "api_key", "token": key, "base_url": base}


def _optimize_base_override(text_backend: str, image_provider: str, override: Optional[str]) -> Optional[str]:
    if not override:
        return None
    if text_backend == "grok" and image_provider in {"grok", "xai"}:
        return override
    if text_backend == "openai" and image_provider == "openai":
        return override
    if text_backend == "gemini" and image_provider == "gemini":
        return override
    return None


def list_optimize_backends(
    family: str,
    loaded_files: Sequence[Path],
    *,
    allow_missing_preferred: bool,
    image_provider: str,
    base_override: Optional[str],
) -> List[Dict[str, str]]:
    resolvers = {
        "grok": grok_optimize_token,
        "openai": openai_optimize_token,
        "gemini": gemini_optimize_token,
    }
    order = preferred_text_backends(family)
    available: List[Dict[str, str]] = []
    for name in order:
        try:
            resolved = resolvers[name](
                loaded_files, _optimize_base_override(name, image_provider, base_override)
            )
        except ImageGenError:
            continue
        if resolved:
            available.append(resolved)
    if not available:
        return []
    preferred_name = order[0]
    preferred = [item for item in available if item["provider"] == preferred_name]
    others = [item for item in available if item["provider"] != preferred_name]
    if preferred:
        return preferred + others
    if allow_missing_preferred:
        return others
    return []


def resolve_optimize_token(backend: Dict[str, str]) -> Dict[str, str]:
    if backend.get("provider") == "grok" and backend.get("auth") == "subscription":
        token, _auth = refresh_grok_auth()
        resolved = dict(backend)
        resolved["token"] = token
        return resolved
    return backend


def invoke_optimize_model(
    backend: Dict[str, str],
    family: str,
    system: str,
    user: str,
    model_override: Optional[str] = None,
) -> Tuple[str, str]:
    backend = resolve_optimize_token(backend)
    provider = backend["provider"]
    preferred = preferred_text_backends(family)[0]
    model = default_text_model(
        provider,
        model_override,
        allow_override=provider == preferred,
    )
    if provider in {"grok", "openai"}:
        endpoint = f"{backend['base_url'].rstrip('/')}/chat/completions"
        body: Dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.35,
            "max_tokens": 500,
        }
        # grok-4.6 defaults to high reasoning and can stall a 2-5 sentence compile.
        if provider == "grok" and "grok-4." in model:
            body["reasoning_effort"] = "low"
        if provider == "openai" and "gpt-5.6" in model:
            body["reasoning_effort"] = "low"
        _, payload, _ = http_request(
            endpoint,
            headers={
                "Authorization": f"Bearer {backend['token']}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            body=json.dumps(body).encode("utf-8"),
            timeout=OPTIMIZE_TIMEOUT,
        )
        return extract_chat_text(payload), model
    api_root = backend["base_url"].rstrip("/")
    url = f"{api_root}/models/{model}:generateContent"
    _, payload, _ = http_request(
        url,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-goog-api-key": backend["token"],
        },
        body=json.dumps(
            {
                "contents": [{"role": "user", "parts": [{"text": f"{system}\n\n---\n\n{user}"}]}],
                "generationConfig": {"temperature": 0.35, "maxOutputTokens": 500},
            }
        ).encode("utf-8"),
        timeout=OPTIMIZE_TIMEOUT,
    )
    return extract_gemini_text(payload), model


def compile_job_prompt(
    args: argparse.Namespace,
    provider: str,
    aspect: Optional[str],
    images: Sequence[str],
    loaded_files: Sequence[Path],
) -> PromptCompileResult:
    original = str(args.prompt).strip()
    profile = getattr(args, "prompt_profile", None)
    optimize_mode = getattr(args, "optimize", "off") or "off"
    raw = bool(getattr(args, "raw", False))
    from_file = bool(getattr(args, "prompt_from_file", False))
    family = prompt_family(provider)
    source_format = detect_prompt_format(original)
    notes: List[str] = []

    if raw and (profile or optimize_mode != "off"):
        notes.append("--raw sent the prompt verbatim and ignored --prompt-profile / --optimize.")

    should, skipped = decide_optimize(
        optimize_mode,
        original,
        raw=raw,
        from_file=from_file,
        provider=provider,
    )
    adapt_reason = None
    if should and skipped == "family_mismatch":
        adapt_reason = "family_mismatch"
        notes.append(
            f"Re-adapting a {source_format} prompt for {family} ({provider})."
        )
        skipped = None
    if not should:
        used = original if raw else fallback_prompt(original, profile, aspect, family)
        return PromptCompileResult(
            original,
            used,
            profile=None if raw else profile,
            optimize_mode=optimize_mode,
            applied=False,
            skipped_reason=skipped,
            family=family,
            source_format=source_format,
            notes=notes,
        )

    backends = list_optimize_backends(
        family,
        loaded_files,
        allow_missing_preferred=optimize_mode == "on",
        image_provider=provider,
        base_override=getattr(args, "base_url", None),
    )
    if not backends:
        if optimize_mode == "on":
            raise ImageGenError(
                "--optimize on needs a text backend: grok login / XAI_API_KEY, "
                "OPENAI_API_KEY, or GEMINI_API_KEY. It will not launch agy or cursor-agent."
            )
        notes.append("Skipped --optimize auto; no family-matched text backend is available.")
        used = fallback_prompt(original, profile, aspect, family)
        return PromptCompileResult(
            original,
            used,
            profile=profile,
            optimize_mode=optimize_mode,
            applied=False,
            skipped_reason="no_text_backend",
            family=family,
            source_format=source_format,
            adapt_reason=adapt_reason,
            notes=notes,
        )

    preferred = preferred_text_backends(family)[0]
    system, user = build_optimize_messages(
        original,
        family=family,
        edit=bool(images),
        aspect=aspect,
        profile=None if raw else profile,
        image_count=len(images),
    )
    last_error: Optional[str] = None
    last_backend: Optional[Dict[str, str]] = None
    last_model: Optional[str] = None
    for backend in backends:
        last_backend = backend
        if backend["provider"] != preferred:
            notes.append(
                f"Optimize trying {backend['provider']} text; preferred family backend is {preferred}."
            )
        try:
            raw_text, model = invoke_optimize_model(
                backend, family, system, user, getattr(args, "optimize_model", None)
            )
        except ImageGenError as exc:
            last_error = redact_secrets(str(exc))
            last_model = None
            notes.append(f"{backend['provider']} optimize failed: {last_error}")
            continue
        last_model = model
        compiled = sanitize_optimized_prompt(raw_text)
        if compiled:
            return PromptCompileResult(
                original,
                compiled,
                profile=profile,
                optimize_mode=optimize_mode,
                applied=True,
                family=family,
                text_model=model,
                text_provider=backend["provider"],
                source_format=source_format,
                adapt_reason=adapt_reason,
                notes=notes,
            )
        last_error = "compiler output was empty or a refusal"
        notes.append(f"{backend['provider']} optimize returned unusable text.")

    if optimize_mode == "on":
        raise ImageGenError(f"Prompt optimize failed: {last_error or 'no usable text'}")
    notes.append(f"Skipped --optimize auto after text-model errors: {last_error or 'no usable text'}")
    used = fallback_prompt(original, profile, aspect, family)
    return PromptCompileResult(
        original,
        used,
        profile=profile,
        optimize_mode=optimize_mode,
        applied=False,
        skipped_reason="optimize_failed",
        family=family,
        text_model=last_model,
        text_provider=last_backend["provider"] if last_backend else None,
        source_format=source_format,
        adapt_reason=adapt_reason,
        notes=notes,
    )


def job_image_paths(result: Dict[str, Any]) -> List[Path]:
    paths: List[Path] = []
    seen = set()
    for raw in list(result.get("images") or []) + [result.get("image")]:
        if not raw:
            continue
        path = Path(str(raw))
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        paths.append(path)
    return paths


def read_sidecar(path: Path) -> Dict[str, Any]:
    sidecar = path if path.suffix.lower() == ".json" else path.with_suffix(".json")
    if not sidecar.is_file():
        return {}
    try:
        loaded = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def write_aspect_fail_receipt(
    path: Path,
    error: str,
    requested: str,
    size: str,
    actual: str,
) -> Optional[Path]:
    if not path.is_file():
        return None
    existing = read_sidecar(path)
    receipt = {
        **existing,
        "schema": 1,
        "ok": False,
        "created_at": existing.get("created_at") or utc_now_iso(),
        "image": path.name,
        "error": error,
        "aspect_ratio": requested,
        "size": size,
        "actual_aspect": actual,
        "cli": "local-image-gen",
        "version": __version__,
    }
    sidecar = path.with_suffix(".json")
    sidecar.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return sidecar


def write_job_receipt(result: Dict[str, Any]) -> Optional[Path]:
    """Write a sidecar JSON next to each saved image. Prototype primitive."""
    if result.get("dry_run"):
        return None
    if not result.get("success") and not job_image_paths(result):
        return None
    written: Optional[Path] = None
    for path in job_image_paths(result):
        if not path.is_file():
            continue
        receipt = {
            "schema": 1,
            "ok": bool(result.get("success")),
            "created_at": utc_now_iso(),
            "image": path.name,
            "provider": result.get("provider"),
            "auth": result.get("auth"),
            "model": result.get("model"),
            "aspect_ratio": result.get("aspect_ratio"),
            "size": result.get("size"),
            "quality": result.get("quality"),
            "resolution": result.get("resolution"),
            "prompt": result.get("prompt"),
            "notes": result.get("notes"),
            "cli": "local-image-gen",
            "version": __version__,
        }
        sidecar = path.with_suffix(".json")
        sidecar.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written = sidecar
    if written:
        result["receipt"] = str(written)
    return written


def attach_prompt_meta(
    result: Dict[str, Any],
    compiled: PromptCompileResult,
    workspace: Optional[Path],
    notes: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    result["prompt_original"] = compiled.original
    result["prompt_used"] = compiled.used
    result["prompt"] = compiled.as_dict()
    attached = attach_workspace(result, workspace, list(notes or []) + compiled.notes)
    write_job_receipt(attached)
    return attached


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    tokens = list(sys.argv[1:] if argv is None else argv)
    command: Optional[str] = None
    if tokens and tokens[0] in META_COMMANDS:
        command = tokens[0]
        tokens = tokens[1:]
    if command == "update":
        return parse_update_args(tokens)
    if command == "doctor":
        return parse_doctor_args(tokens)
    return parse_job_args(tokens)


def parse_update_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="local-image-gen update",
        description="Fast-forward this git checkout and refresh the CLI wrapper and skill links.",
    )
    parser.add_argument("--version", action="version", version=f"local-image-gen {__version__}")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the git pull and installer steps without changing files.",
    )
    args = parser.parse_args(list(argv))
    args.command = "update"
    args.doctor = False
    args.list_providers = False
    args.list_models = False
    args.prompt = None
    return args


def parse_doctor_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="local-image-gen doctor",
        description="Report backends, optional Dyro detection, and whether this install is behind main.",
    )
    parser.add_argument("--version", action="version", version=f"local-image-gen {__version__}")
    parser.add_argument("--doctor", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(list(argv))
    args.command = "doctor"
    args.doctor = True
    args.list_providers = False
    args.list_models = False
    args.prompt = None
    args.dry_run = False
    return args


def parse_job_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate or edit images via local subscriptions or official API keys.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Tool commands:\n"
            "  local-image-gen doctor            Diagnose backends and install freshness\n"
            "  local-image-gen update            Fast-forward this install\n"
            "  local-image-gen update --dry-run  Show the update steps only\n"
        ),
    )
    parser.add_argument("--version", action="version", version=f"local-image-gen {__version__}")
    parser.add_argument("prompt", nargs="?", help="Image prompt.")
    parser.add_argument("-p", "--prompt-file", type=Path, help="Read the prompt from a UTF-8 file.")
    parser.add_argument("-o", "--output", type=Path, help="Output image path.")
    parser.add_argument("--out-dir", type=Path, help="Output directory when --output is omitted.")
    parser.add_argument("-i", "--image", "--reference-image", action="append", dest="images", default=[], help="Reference/edit image. Repeatable.")
    parser.add_argument("--mask", type=Path, help="PNG mask for OpenAI inpaint. Transparent regions are edited. Only --provider openai.")
    parser.add_argument("--raw", action="store_true", help="Send the prompt verbatim. Skips --prompt-profile and --optimize.")
    parser.add_argument(
        "--prompt-profile",
        choices=PROMPT_PROFILES,
        help="Wrap a short prompt in a deterministic asset template (cover, isometric, infographic, snapshot, ...).",
    )
    parser.add_argument(
        "--optimize",
        choices=OPTIMIZE_MODES,
        default="off",
        help="Compile the prompt for the target image family. Default off. auto rewrites short/generic prompts and remaps a prompt written for a different family.",
    )
    parser.add_argument("--optimize-model", help="Override the text model used by --optimize.")
    parser.add_argument("--provider", choices=PROVIDERS, default="auto")
    parser.add_argument("--model", help="Image model id or alias.")
    parser.add_argument("--aspect-ratio", "--aspect", dest="aspect_ratio", help="Aspect ratio such as 16:9, 9:16, square, landscape, portrait.")
    parser.add_argument("--size", help="Pixel size auto or WIDTHxHEIGHT.")
    parser.add_argument("--quality", choices=QUALITY_CHOICES, default="auto")
    parser.add_argument("--resolution", choices=RESOLUTION_CHOICES, help="Clarity: 1k, 2k, or 4k.")
    parser.add_argument("--n", type=int, default=1, help="Variant count where the backend allows it.")
    parser.add_argument("--api-key-file", type=Path, help="Optional dotenv file containing provider API keys and optional *_BASE_URL values.")
    parser.add_argument(
        "--base-url",
        "--api-base",
        dest="base_url",
        help="API-key path only. Override the official API base. Unofficial hosts are never the default.",
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--list-providers", action="store_true")
    parser.add_argument("--list-models", action="store_true")
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Alias for the doctor command. Prefer: local-image-gen doctor.",
    )
    args = parser.parse_args(list(argv))
    if args.doctor:
        args.command = "doctor"
        return args
    if args.list_providers or args.list_models:
        args.command = "list"
        return args
    if args.prompt and args.prompt_file:
        parser.error("Use either a prompt argument or --prompt-file, not both.")
    args.prompt_from_file = False
    if args.prompt_file:
        args.prompt = args.prompt_file.expanduser().read_text(encoding="utf-8")
        args.prompt_from_file = True
    if not args.prompt or not str(args.prompt).strip():
        parser.error("A prompt is required unless doctor, update, --list-providers, or --list-models is used.")
    args.prompt = str(args.prompt).strip()
    if args.mask:
        args.mask = args.mask.expanduser()
        if not args.mask.is_file():
            parser.error(f"Mask file not found: {args.mask}")
    if args.n < 1 or args.n > 10:
        parser.error("--n must be between 1 and 10.")
    if args.size and args.aspect_ratio:
        parser.error("Use either --size or --aspect-ratio, not both.")
    if args.size and not SIZE_PATTERN.match(args.size):
        parser.error("--size must be auto or WIDTHxHEIGHT.")
    args.command = "generate"
    return args


def attach_workspace(result: Dict[str, Any], workspace: Optional[Path], notes: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    extra = [item for item in (notes or []) if item]
    if extra:
        existing = result.get("notes")
        if isinstance(existing, list):
            result["notes"] = list(existing) + extra
        elif existing:
            result["notes"] = [str(existing), *extra]
        else:
            result["notes"] = extra
    if workspace:
        result["dyro_workspace"] = str(workspace)
    return result


def prepare_output(args: argparse.Namespace) -> Tuple[Path, Optional[Path]]:
    workspace = find_dyro_workspace()
    if args.output:
        path = args.output.expanduser()
        if not path.suffix:
            path = path.with_suffix(".png")
        return path, workspace
    directory, workspace = default_image_dir(args.out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    return default_output_path(args.prompt, directory, "png"), workspace


def run_job(args: argparse.Namespace) -> Dict[str, Any]:
    loaded_files = env_search_files(args.api_key_file)
    model = canonical_model(args.model)
    provider = resolve_provider(args.provider, model, loaded_files)
    if not model:
        model = DEFAULT_MODEL_FOR_PROVIDER.get(provider, "grok-imagine-image-2.0")
        model = canonical_model(model) or model

    aspect = normalize_aspect(args.aspect_ratio) if args.aspect_ratio else None
    if args.size and args.size != "auto" and not aspect:
        aspect = aspect_from_size(args.size)
    if not aspect and not args.size:
        aspect = "1:1"

    notes: List[str] = []
    output, workspace = prepare_output(args)
    images = list(args.images or [])
    mask = getattr(args, "mask", None)
    if mask and provider != "openai":
        raise ImageGenError("--mask is only supported with --provider openai.")
    if mask and not images:
        raise ImageGenError("--mask requires at least one --image.")
    if provider in {"grok", "xai"} and len(images) > GROK_MAX_REFERENCE_IMAGES:
        raise ImageGenError(
            f"Grok Imagine accepts at most {GROK_MAX_REFERENCE_IMAGES} reference images."
        )

    compiled = compile_job_prompt(args, provider, aspect, images, loaded_files)
    prompt = compiled.used

    if provider == "grok":
        grok_quality, grok_resolution, map_notes = map_grok_quality(args.quality, args.resolution)
        notes.extend(map_notes)
        grok_base = GROK_API_BASE
        if grok_auth_available():
            token, auth_mode = (None, "subscription") if args.dry_run else refresh_grok_auth()
            if args.dry_run:
                token, auth_mode = "dry-run", "subscription"
        else:
            key = first_env(ENV_KEY_NAMES["xai"], loaded_files)
            if not key and not args.dry_run:
                raise ImageGenError("Grok login not found and XAI_API_KEY is unset. Run: grok login")
            token, auth_mode = key or "dry-run", "api_key"
            grok_base, _source = resolve_api_base("xai", loaded_files, getattr(args, "base_url", None))
        result = run_grok(
            prompt,
            model,
            aspect,
            grok_quality,
            grok_resolution,
            args.n,
            images,
            token or "",
            auth_mode,
            unique_output_path(output, args.overwrite) if not args.dry_run else output,
            args.overwrite,
            args.dry_run,
            grok_base,
        )
        return attach_prompt_meta(result, compiled, workspace, notes)

    if provider == "codex":
        if not (codex_auth_available() or args.dry_run):
            raise ImageGenError(f"Missing {CODEX_AUTH_PATH}. Run: codex auth login")
        size = nearest_codex_size(aspect, args.size)
        quality = "high" if args.quality == "auto" and args.resolution in {"2k", "4k"} else args.quality
        if quality == "auto":
            quality = "medium"
        return attach_prompt_meta(
            run_codex(
                prompt, model, size, quality, images, output, args.overwrite, args.dry_run, aspect
            ),
            compiled,
            workspace,
            notes,
        )

    if provider == "antigravity":
        image_size = map_gemini_image_size(args.quality, args.resolution)
        return attach_prompt_meta(
            run_antigravity(
                prompt,
                model,
                aspect,
                image_size,
                images,
                output,
                args.overwrite,
                args.dry_run,
            ),
            compiled,
            workspace,
            notes,
        )

    if provider == "cursor":
        image_size = map_gemini_image_size(args.quality, args.resolution)
        return attach_prompt_meta(
            run_cursor(
                prompt,
                model,
                aspect,
                image_size,
                images,
                output,
                args.overwrite,
                args.dry_run,
            ),
            compiled,
            workspace,
            notes,
        )

    if provider == "gemini":
        image_size = map_gemini_image_size(args.quality, args.resolution)
        api_key = first_env(ENV_KEY_NAMES["gemini"], loaded_files)
        if not api_key and not args.dry_run:
            raise ImageGenError(
                "Gemini API key is missing. Use --provider antigravity after `agy` login, or set GEMINI_API_KEY."
            )
        gemini_base, _source = resolve_api_base("gemini", loaded_files, getattr(args, "base_url", None))
        return attach_prompt_meta(
            run_gemini(
                prompt,
                model,
                aspect,
                image_size,
                images,
                api_key or "dry-run",
                output,
                args.overwrite,
                args.dry_run,
                gemini_base,
            ),
            compiled,
            workspace,
            notes,
        )

    if provider in {"openai", "xai"}:
        key_names = ENV_KEY_NAMES[provider]
        api_key = first_env(key_names, loaded_files)
        if not api_key and not args.dry_run:
            raise ImageGenError(f"{provider} requires {key_names[0]}.")
        size = args.size or nearest_codex_size(aspect, None)
        quality = args.quality
        key_base, _source = resolve_api_base(provider, loaded_files, getattr(args, "base_url", None))
        if provider == "xai" and catalog_provider(model) == "grok":
            grok_quality, grok_resolution, map_notes = map_grok_quality(args.quality, args.resolution)
            notes.extend(map_notes)
            token = api_key or "dry-run"
            result = run_grok(
                prompt,
                model,
                aspect,
                grok_quality,
                grok_resolution,
                args.n,
                images,
                token,
                "api_key",
                output,
                args.overwrite,
                args.dry_run,
                key_base,
            )
            result["provider"] = "xai"
            return attach_prompt_meta(result, compiled, workspace, notes)
        return attach_prompt_meta(
            run_openai_compat(
                provider,
                prompt,
                model,
                size,
                quality,
                images,
                args.n,
                api_key or "dry-run",
                key_base,
                output,
                args.overwrite,
                args.dry_run,
                mask if provider == "openai" else None,
            ),
            compiled,
            workspace,
            notes,
        )

    raise ImageGenError(f"Unsupported provider: {provider}")


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    loaded_files = env_search_files(getattr(args, "api_key_file", None))
    if args.list_providers:
        print_json(
            {
                "success": True,
                "harness": detect_harness(),
                "providers": list_provider_status(loaded_files),
            }
        )
        return 0
    if args.list_models:
        print_json({"success": True, "models": list_models_payload()})
        return 0
    if getattr(args, "command", None) == "update":
        try:
            print_json(run_update(dry_run=bool(getattr(args, "dry_run", False))))
        except ImageGenError as exc:
            fail(str(exc))
            return 1
        return 0
    if args.doctor:
        print_json(doctor_payload(loaded_files))
        return 0
    try:
        result = run_job(args)
    except ImageGenError as exc:
        fail(str(exc))
        return 1
    print_json(result)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ImageGenError as exc:
        fail(str(exc))
