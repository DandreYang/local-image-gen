#!/usr/bin/env python3
"""Local studio for local-image-gen. Stdlib only. Default bind is loopback."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import mimetypes
import os
import re
import struct
import subprocess
import sys
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlparse

from director import look_at_image, revise_turn
from job import brief as build_brief
import local_image_gen as cli

WORKSPACE = Path(__file__).resolve().parents[1]
CLI = WORKSPACE / "scripts" / "local_image_gen.py"
STATIC = Path(__file__).resolve().parent / "static"
OUTPUTS = WORKSPACE / "outputs"
IMAGE_DIR = OUTPUTS / "images"
INBOX = IMAGE_DIR / "inbox"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
HOST = "127.0.0.1"
DEFAULT_PORT = 8765


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


def run_cli(args: List[str], timeout: int = 300, *, skip_update_check: bool = True) -> Dict[str, Any]:
    env = os.environ.copy()
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
            "error": f"CLI timed out after {timeout}s. Codex/Grok jobs often take 1–3 minutes; retry or check the process.",
            "exit_code": None,
        }
    payload = parse_cli_json(proc.stdout) or parse_cli_json(proc.stderr)
    if payload is None:
        detail = (proc.stderr or proc.stdout or "CLI returned no JSON").strip()[:800]
        return {"success": False, "error": detail, "exit_code": proc.returncode}
    payload.setdefault("success", proc.returncode == 0)
    payload["exit_code"] = proc.returncode
    return attach_saved_artifact(payload)


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


def read_sidecar(path: Path) -> Dict[str, Any]:
    sidecar = path if path.suffix.lower() == ".json" else path.with_suffix(".json")
    if not sidecar.is_file():
        return {}
    try:
        loaded = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def merge_sidecar(path: Path, fields: Dict[str, Any]) -> Path:
    sidecar = path.with_suffix(".json")
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
    sidecar.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
            "auth": payload.get("auth"),
            "model": payload.get("model"),
            "aspect_ratio": payload.get("aspect_ratio"),
            "quality": payload.get("quality"),
            "resolution": payload.get("resolution"),
            "size": payload.get("size"),
            "cropped_from": payload.get("cropped_from"),
            "notes": payload.get("notes"),
            "prompt": prompt,
            "cli": "local-image-gen",
            "studio": True,
            "version": getattr(cli, "__version__", None),
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
    if job_provider and job_provider != "auto" and not _nonzero(result.get("provider")):
        result["provider"] = job_provider
    if job.get("model") and not _nonzero(result.get("model")):
        result["model"] = job.get("model")
    if job.get("quality") and not _nonzero(result.get("quality")):
        result["quality"] = job.get("quality")
    if job.get("resolution") and not _nonzero(result.get("resolution")):
        result["resolution"] = job.get("resolution")
    aspect = job.get("aspect") or result.get("aspect_ratio")
    if aspect:
        result["aspect_ratio"] = aspect
    prompt = result.get("prompt") if isinstance(result.get("prompt"), dict) else {}
    if used:
        result["prompt"] = {
            "original": prompt.get("original") or used,
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
                "quality": result.get("quality"),
                "resolution": result.get("resolution"),
                "prompt": prompt_parts(result),
                "notes": result.get("notes"),
            },
        )


def finalize_generated(result: Dict[str, Any], job: Dict[str, Any], used: str) -> Dict[str, Any]:
    result = stamp_job_meta(result, job, used)
    aspect = str(job.get("aspect") or "")
    if result.get("saved_but_failed") and aspect:
        result = recover_aspect(result, aspect)
    persist_result_receipts(result)
    return result


def is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


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
    if crop_match:
        aspect = f"{crop_match.group(1)}:{crop_match.group(2)}"
    elif isinstance(raw_aspect, str) and raw_aspect and " or " not in raw_aspect:
        aspect = raw_aspect
    pixels = peek_png_size(path)
    if not aspect and pixels:
        aspect = cli.describe_dimensions(*pixels)
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
        "model": (receipt or {}).get("model"),
        "aspect_ratio": aspect,
        "quality": (receipt or {}).get("quality"),
        "resolution": (receipt or {}).get("resolution") or size,
        "size": size,
        "auth": (receipt or {}).get("auth"),
        "created_at": created,
        "prompt_original": original,
        "prompt_used": used,
        "has_receipt": receipt is not None,
        "cropped_from": cropped_from,
        "notes": (receipt or {}).get("notes"),
        "receipt": receipt,
    }


def list_library() -> List[Dict[str, Any]]:
    if not OUTPUTS.is_dir():
        return []
    items: List[Dict[str, Any]] = []
    for path in OUTPUTS.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if path.name.startswith("."):
            continue
        items.append(media_item(path))
    items.sort(key=lambda item: item["mtime"], reverse=True)
    return items


def compile_job(job: Dict[str, Any]) -> Dict[str, Any]:
    args = [
        str(job.get("prompt") or ""),
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


def attach_compiled_drafts(payload: Dict[str, Any]) -> Dict[str, Any]:
    jobs = payload.get("jobs")
    if not isinstance(jobs, list):
        return payload
    warnings = list(payload.get("warnings") or [])
    for job in jobs:
        if not isinstance(job, dict):
            continue
        compiled = compile_job(job)
        prompt_meta = compiled.get("prompt") if isinstance(compiled.get("prompt"), dict) else {}
        used = str(prompt_meta.get("used") or "").strip()
        job["draft"] = used or str(job.get("prompt") or "")
        optimize = prompt_meta.get("optimize") if isinstance(prompt_meta.get("optimize"), dict) else {}
        job["family"] = optimize.get("family")
        if compiled.get("success") is False:
            job["compile_error"] = compiled.get("error")
            warnings.append("终稿编译失败，下面是未按家族改写的任务说明，可先改再出图。")
        elif job.get("family") == "gpt_image" and "Use case:" not in job["draft"]:
            warnings.append("Codex / gpt-image-2 终稿里没有 $imagegen 标签，请改稿或换官方 OpenAI。")
    payload["warnings"] = warnings
    return payload


def generate_compiled(job: Dict[str, Any], used: str) -> Dict[str, Any]:
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
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    args.extend(["--out-dir", str(IMAGE_DIR)])
    for raw in job.get("images") or []:
        path = Path(str(raw))
        if not path.is_absolute():
            path = (OUTPUTS / path).resolve()
        if path.is_file() and is_under(path, OUTPUTS):
            args.extend(["-i", str(path)])
    return run_cli(args, timeout=320)


def run_confirm_generate(body: Dict[str, Any]) -> Dict[str, Any]:
    jobs = body.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        raise ValueError("jobs required")
    results: List[Dict[str, Any]] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        used = str(job.get("draft") or job.get("prompt") or "").strip()
        generated = generate_compiled(job, used)
        generated = finalize_generated(generated, job, used)
        results.append(generated)
    ok = all(item.get("success") for item in results) if results else False
    return {"success": ok, "results": results}


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
    return look_at_image(
        path,
        draft=str(body.get("draft") or ""),
        brief=str(body.get("brief") or ""),
    )


def run_revise(body: Dict[str, Any]) -> Dict[str, Any]:
    image = str(body.get("image") or "").strip()
    last_image = ""
    if image:
        resolved = resolve_library_image(image)
        last_image = str(resolved.resolve().relative_to(OUTPUTS.resolve()).as_posix())
    payload = revise_turn(
        str(body.get("message") or ""),
        draft=str(body.get("draft") or ""),
        brief=str(body.get("brief") or ""),
        critique=body.get("critique") if isinstance(body.get("critique"), dict) else None,
        last_image=last_image,
    )
    if payload.get("success") and payload.get("mode") == "edit" and last_image:
        payload["images"] = [last_image]
    return payload


def parse_generate(body: Dict[str, Any]) -> List[str]:
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("prompt is required")
    args = [prompt]
    provider = str(body.get("provider") or "auto").strip()
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
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    args.extend(["--out-dir", str(IMAGE_DIR)])
    for raw in body.get("images") or []:
        path = Path(str(raw))
        if not path.is_absolute():
            path = (OUTPUTS / path).resolve()
        if not path.is_file() or not is_under(path, OUTPUTS):
            raise ValueError(f"reference image is outside the library: {raw}")
        args.extend(["-i", str(path)])
    if body.get("dry_run"):
        args.append("--dry-run")
    return args


class Handler(BaseHTTPRequestHandler):
    server_version = "local-studio/0.1"

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write("studio: " + (format % args) + "\n")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        payload = json.loads(raw.decode("utf-8") or "{}")
        if not isinstance(payload, dict):
            raise ValueError("JSON object required")
        return payload

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path == "/favicon.ico":
            self._send(204, b"", "image/x-icon")
            return
        if path in {"/", "/index.html"}:
            target = STATIC / "index.html"
            self._send(200, target.read_bytes(), "text/html; charset=utf-8")
            return
        if path.startswith("/static/"):
            target = (STATIC / path[len("/static/") :]).resolve()
            if not is_under(target, STATIC) or not target.is_file():
                self._send(*json_bytes({"error": "not found"}, 404))
                return
            mime = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            self._send(200, target.read_bytes(), mime)
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
            self._send(*json_bytes(run_cli(["doctor"], timeout=20)))
            return
        if path == "/api/version":
            payload = run_cli(["doctor"], timeout=25, skip_update_check=False)
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
            self._send(*json_bytes(run_cli(["--list-models"], timeout=15)))
            return
        if path == "/api/library":
            self._send(*json_bytes({"success": True, "items": list_library()}))
            return
        self._send(*json_bytes({"error": "not found"}, 404))

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/brief":
            try:
                body = self._read_json()
                payload = build_brief(
                    str(body.get("prompt") or ""),
                    provider=str(body.get("provider") or "auto"),
                    template_id=str(body.get("template") or ""),
                    aspect=str(body.get("aspect") or ""),
                    quality=str(body.get("quality") or "high"),
                    resolution=str(body.get("resolution") or "2k"),
                    model=str(body.get("model") or ""),
                    images=list(body.get("images") or []),
                )
                if payload.get("success"):
                    payload = attach_compiled_drafts(payload)
            except Exception as exc:  # noqa: BLE001
                self._send(*json_bytes({"success": False, "error": str(exc)}, 400))
                return
            self._send(*json_bytes(payload))
            return
        if path == "/api/confirm-generate":
            try:
                body = self._read_json()
                payload = run_confirm_generate(body)
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
                prompt_meta = payload.get("prompt") if isinstance(payload.get("prompt"), dict) else {}
                used = str(prompt_meta.get("used") or body.get("prompt") or "")
                payload = finalize_generated(payload, body, used)
            except (ValueError, json.JSONDecodeError) as exc:
                self._send(*json_bytes({"success": False, "error": str(exc)}, 400))
                return
            self._send(*json_bytes(payload))
            return
        if path == "/api/upload":
            self._send(*json_bytes(self._save_upload()))
            return
        self._send(*json_bytes({"error": "not found"}, 404))

    def _save_upload(self) -> Dict[str, Any]:
        content_type = self.headers.get("Content-Type") or ""
        if "multipart/form-data" not in content_type:
            return {"success": False, "error": "multipart/form-data required"}
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > 20 * 1024 * 1024:
            return {"success": False, "error": "upload too large or empty"}
        payload = self.rfile.read(length)
        boundary = None
        for part in content_type.split(";"):
            part = part.strip()
            if part.startswith("boundary="):
                boundary = part.split("=", 1)[1].strip().strip('"')
        if not boundary:
            return {"success": False, "error": "missing multipart boundary"}
        marker = b"--" + boundary.encode("ascii", "replace")
        chunks = payload.split(marker)
        saved: List[str] = []
        INBOX.mkdir(parents=True, exist_ok=True)
        for chunk in chunks:
            header_end = chunk.find(b"\r\n\r\n")
            if header_end < 0:
                continue
            header = chunk[:header_end].decode("utf-8", "replace")
            if "filename=" not in header:
                continue
            name = header.split("filename=", 1)[1].split("\r\n", 1)[0].strip().strip('"')
            suffix = Path(name).suffix.lower()
            if suffix not in IMAGE_SUFFIXES:
                continue
            body = chunk[header_end + 4 :]
            if body.endswith(b"\r\n"):
                body = body[:-2]
            target = INBOX / f"{uuid.uuid4().hex[:10]}{suffix}"
            target.write_bytes(body)
            saved.append(str(target.resolve().relative_to(OUTPUTS.resolve())))
        if not saved:
            return {"success": False, "error": "no image part found"}
        return {"success": True, "items": saved}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Local studio for local-image-gen.")
    parser.add_argument("--host", default=HOST, help="Bind address. Default 127.0.0.1. Use 0.0.0.0 for LAN.")
    parser.add_argument("--lan", action="store_true", help="Bind 0.0.0.0 so other devices on the LAN can connect.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    host = "0.0.0.0" if args.lan else args.host
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((host, args.port), Handler)
    if host in {"0.0.0.0", "::"}:
        print(f"local studio  http://127.0.0.1:{args.port}", flush=True)
        print(f"LAN          http://<this-machine-ip>:{args.port}", flush=True)
        print("warning: LAN bind shares this machine's image backends with the network.", flush=True)
    else:
        print(f"local studio  http://{host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
