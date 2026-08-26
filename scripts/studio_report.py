"""Privacy-preserving local Studio dogfood metrics."""

from __future__ import annotations

import datetime as dt
import json
import math
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,99}$")
_BATCH_STATUSES = ("done", "failed", "interrupted", "running", "queued", "unknown")
_JOB_STATUSES = ("done", "failed", "interrupted", "running", "queued", "unknown")


def _timestamp(value: Any) -> Optional[float]:
    try:
        stamp = float(value)
    except (TypeError, ValueError):
        return None
    return stamp if math.isfinite(stamp) and stamp >= 0 else None


def _safe_name(value: Any) -> str:
    text = str(value or "").strip()
    return text if _SAFE_NAME.fullmatch(text) else "other"


def _known_status(value: Any, allowed: Sequence[str]) -> str:
    text = str(value or "").strip().lower()
    return text if text in allowed else "unknown"


def _rate(numerator: int, denominator: int) -> Optional[float]:
    return round(numerator / denominator, 4) if denominator else None


def _percentile(values: Sequence[int], percentile: int) -> Optional[int]:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil((percentile / 100) * len(ordered)) - 1)
    return int(ordered[index])


def _latency_summary(values: Iterable[int]) -> Dict[str, Optional[int]]:
    rows = sorted(max(0, int(value)) for value in values)
    return {
        "samples": len(rows),
        "min": rows[0] if rows else None,
        "p50": _percentile(rows, 50),
        "p95": _percentile(rows, 95),
        "max": rows[-1] if rows else None,
    }


def _job_provider(job: Dict[str, Any]) -> str:
    result = job.get("result") if isinstance(job.get("result"), dict) else {}
    return _safe_name(result.get("provider") or job.get("provider"))


def _job_model(job: Dict[str, Any]) -> str:
    result = job.get("result") if isinstance(job.get("result"), dict) else {}
    return _safe_name(result.get("model") or job.get("model"))


def _batch_scope(record: Dict[str, Any]) -> str:
    providers = [_job_provider(job) for job in record.get("jobs") or [] if isinstance(job, dict)]
    known = [provider for provider in providers if provider != "other"]
    if known and all(provider == "fixture" for provider in known):
        return "fixture"
    if any(provider != "fixture" for provider in known):
        return "live"
    return "unknown"


def _iso(stamp: float) -> str:
    return dt.datetime.fromtimestamp(stamp, tz=dt.timezone.utc).isoformat().replace("+00:00", "Z")


def load_batch_records(batch_dir: Path) -> List[Dict[str, Any]]:
    root = batch_dir.expanduser().resolve()
    if not root.is_dir():
        return []
    records: List[Dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        try:
            if path.is_symlink() or path.stat().st_size > 4 * 1024 * 1024:
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records


def build_dogfood_report(
    records: Sequence[Dict[str, Any]],
    *,
    days: int = 7,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    if days < 1 or days > 3650:
        raise ValueError("days must be between 1 and 3650")
    generated = float(time.time() if now is None else now)
    since = generated - (days * 86400)
    recent = [
        record
        for record in records
        if isinstance(record, dict)
        and (_timestamp(record.get("started")) is not None)
        and float(record["started"]) >= since
        and float(record["started"]) <= generated
    ]

    batch_status = {status: 0 for status in _BATCH_STATUSES}
    batch_scope = {scope: 0 for scope in ("live", "fixture", "unknown")}
    live_batch_status = {status: 0 for status in _BATCH_STATUSES}
    job_status = {status: 0 for status in _JOB_STATUSES}
    live_job_status = {status: 0 for status in _JOB_STATUSES}
    provider_rows: Dict[tuple[str, str], Dict[str, Any]] = {}
    batch_latencies: List[int] = []
    first_image_latencies: List[int] = []
    successful_live_results = 0
    with_actual_pixels = 0
    with_actual_mime = 0
    complete_actual_facts = 0
    with_requested_resolution = 0

    for record in recent:
        status = _known_status(record.get("status"), _BATCH_STATUSES)
        scope = _batch_scope(record)
        batch_status[status] += 1
        batch_scope[scope] += 1
        if scope == "live":
            live_batch_status[status] += 1
            started = _timestamp(record.get("started"))
            finished = _timestamp(record.get("finished"))
            if started is not None and finished is not None and finished >= started:
                batch_latencies.append(round((finished - started) * 1000))

        first_success: Optional[float] = None
        for job in record.get("jobs") or []:
            if not isinstance(job, dict):
                continue
            current_status = _known_status(job.get("status"), _JOB_STATUSES)
            if status == "interrupted" and current_status in {"running", "queued"}:
                current_status = "interrupted"
            job_status[current_status] += 1
            if scope != "live":
                continue
            live_job_status[current_status] += 1
            provider = _job_provider(job)
            model = _job_model(job)
            key = (provider, model)
            row = provider_rows.setdefault(
                key,
                {
                    "provider": provider,
                    "model": model,
                    "jobs": 0,
                    "done": 0,
                    "failed": 0,
                    "interrupted": 0,
                },
            )
            row["jobs"] += 1
            if current_status in {"done", "failed", "interrupted"}:
                row[current_status] += 1

            result = job.get("result") if isinstance(job.get("result"), dict) else {}
            if current_status == "done" and result.get("success") is not False:
                successful_live_results += 1
                width = result.get("actual_width")
                height = result.get("actual_height")
                has_pixels = isinstance(width, int) and width > 0 and isinstance(height, int) and height > 0
                has_mime = str(result.get("actual_mime") or "").startswith("image/")
                if has_pixels:
                    with_actual_pixels += 1
                if has_mime:
                    with_actual_mime += 1
                if has_pixels and has_mime:
                    complete_actual_facts += 1
                if result.get("resolution_requested"):
                    with_requested_resolution += 1
                finished_at = _timestamp(job.get("finished_at"))
                if finished_at is not None and (first_success is None or finished_at < first_success):
                    first_success = finished_at

        if scope == "live":
            started = _timestamp(record.get("started"))
            if started is not None and first_success is not None and first_success >= started:
                first_image_latencies.append(round((first_success - started) * 1000))

    batch_terminal = sum(batch_status[key] for key in ("done", "failed", "interrupted"))
    live_batch_terminal = sum(live_batch_status[key] for key in ("done", "failed", "interrupted"))
    live_job_terminal = sum(live_job_status[key] for key in ("done", "failed", "interrupted"))
    providers = sorted(provider_rows.values(), key=lambda row: (row["provider"], row["model"]))
    for row in providers:
        row["success_rate"] = _rate(row["done"], row["jobs"])

    return {
        "success": True,
        "schema": 1,
        "generated_at": _iso(generated),
        "period_days": days,
        "since": _iso(since),
        "privacy": "aggregate-only; prompts, paths, filenames, batch ids, and failure text are excluded",
        "batches": {
            "total": len(recent),
            **batch_scope,
            "status": batch_status,
            "completion_rate": _rate(batch_status["done"], batch_terminal),
            "live_completion_rate": _rate(live_batch_status["done"], live_batch_terminal),
        },
        "jobs": {
            "total": sum(job_status.values()),
            "status": job_status,
            "live_status": live_job_status,
            "live_success_rate": _rate(live_job_status["done"], live_job_terminal),
        },
        "latency_ms": {
            "batch": _latency_summary(batch_latencies),
            "first_image": _latency_summary(first_image_latencies),
        },
        "truth": {
            "successful_live_results": successful_live_results,
            "with_actual_pixels": with_actual_pixels,
            "with_actual_mime": with_actual_mime,
            "complete_actual_facts": complete_actual_facts,
            "missing_actual_facts": successful_live_results - complete_actual_facts,
            "actual_fact_coverage": _rate(complete_actual_facts, successful_live_results),
            "with_requested_resolution": with_requested_resolution,
        },
        "providers": providers,
    }


def dogfood_report(batch_dir: Path, *, days: int = 7, now: Optional[float] = None) -> Dict[str, Any]:
    return build_dogfood_report(load_batch_records(batch_dir), days=days, now=now)
