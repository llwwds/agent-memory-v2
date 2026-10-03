"""Migrate agent-memory-skill (v1) SQLite data into MemOS v2 via the /product/add API.

Reads the v1 memory databases (events.db / persona.db / pitfalls.db), groups the
active records into batched add requests, and lets the v2 category pipeline
extract them. Every request carries info["source"]="v1-migration" so migrated
memories are identifiable (and filterable) downstream.

The script is a one-off operational tool: it only calls the HTTP API, never
touches the v2 storage directly, and never writes to the v1 databases.

Usage:
    python3 scripts/migrate_v1_to_v2.py --db-dir ~/Documents/memory \
        --api-base http://127.0.0.1:8000 --user-id llwwds [--batch-size 8] \
        [--dry-run] [--report /tmp/migration_report.json]

The API key is read from the MEMOS_API_KEY environment variable (unset = open
server, local dev default).
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from typing import Any

from urllib import error, request


BATCH_SIZE_DEFAULT = 8
RETRY_MAX = 5
RETRY_BACKOFF_SECONDS = 60


def _cpu_idle_percent() -> float | None:
    """Best-effort host CPU idle probe (macOS top); None when unavailable."""
    import re as _re
    import subprocess as _sp

    try:
        out = _sp.run(["top", "-l", "1", "-n", "0"], capture_output=True, text=True, timeout=15)
        m = _re.search(r"CPU usage: .*?([\d.]+)% idle", out.stdout)
        return float(m.group(1)) if m else None
    except Exception:
        return None


def _wait_for_cpu_headroom(threshold: float, max_wait_seconds: float) -> None:
    """Block until host CPU idle >= threshold (skipped when probe unavailable)."""
    deadline = time.time() + max_wait_seconds
    while time.time() < deadline:
        idle = _cpu_idle_percent()
        if idle is None or idle >= threshold:
            return
        print(f"[migrate] cpu gate: idle={idle}% < {threshold}%, waiting")
        time.sleep(30)


def _connect(db_dir: str, name: str) -> sqlite3.Connection:
    path = os.path.join(db_dir, name)
    if not os.path.exists(path):
        print(f"[migrate] skip missing database: {path}")
        return sqlite3.connect(":memory:")
    return sqlite3.connect(path)


def _load_persona(db_dir: str) -> list[dict[str, Any]]:
    db = _connect(db_dir, "persona.db")
    try:
        rows = db.execute(
            "SELECT id, section, key, content, status, updated_at FROM persona "
            "WHERE status='存在' ORDER BY id"
        ).fetchall()
    finally:
        db.close()
    return [
        {
            "id": r[0],
            "text": f"[v1-persona #{r[0]}][{r[1]}] {r[2]}: {r[3]}",
            "meta": {"v1_source": "persona", "v1_id": r[0]},
        }
        for r in rows
    ]


def _load_pitfalls(db_dir: str) -> list[dict[str, Any]]:
    db = _connect(db_dir, "pitfalls.db")
    try:
        rows = db.execute(
            "SELECT id, scene, stage, problem, root_cause, solution, recur_signal, status "
            "FROM pitfalls WHERE status='存在' ORDER BY id"
        ).fetchall()
    finally:
        db.close()
    items = []
    for r in rows:
        pid, scene, stage, problem, root_cause, solution, recur_signal, _status = r
        text = (
            f"[v1-pitfall #{pid}][{scene}] 阶段: {stage or '未知'}。问题: {problem or ''} "
            f"根因: {root_cause or '未知'}。解决方案: {solution or '未解决'}。"
            f"复发信号: {recur_signal or '无'}。"
        )
        items.append({"id": pid, "text": text, "meta": {"v1_source": "pitfalls", "v1_id": pid}})
    return items


def _load_events(db_dir: str) -> list[dict[str, Any]]:
    db = _connect(db_dir, "events.db")
    try:
        # v1 events use lifecycle statuses ('进行中'/'已完成'/'已废弃'), not the
        # memory-level '存在'; migrate everything except explicit non-existence.
        rows = db.execute(
            "SELECT id, name, overview, milestones, status, updated_at FROM events "
            "WHERE status != '不存在' ORDER BY id"
        ).fetchall()
    finally:
        db.close()
    items = []
    for r in rows:
        eid, name, overview, milestones, status, updated_at = r
        milestone_titles: list[str] = []
        if milestones:
            try:
                parsed = json.loads(milestones)
                if isinstance(parsed, list):
                    for m in parsed[:3]:
                        if isinstance(m, dict):
                            title = m.get("title") or m.get("milestone") or ""
                        else:
                            title = str(m)
                        if title:
                            milestone_titles.append(title[:120])
            except (ValueError, TypeError):
                pass
        text = f"[v1-event #{eid}] {name}（状态: {status}，更新于 {updated_at}）：{overview or ''}"
        if milestone_titles:
            text += " 近期节点: " + "；".join(milestone_titles)
        items.append({"id": eid, "text": text, "meta": {"v1_source": "events", "v1_id": eid}})
    return items


def _post_add(api_base: str, api_key: str | None, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    req = request.Request(
        f"{api_base.rstrip('/')}/product/add", data=body, headers=headers, method="POST"
    )
    with request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _looks_like_fallback(data: list[dict[str, Any]]) -> bool:
    """Detect the upstream LLM-failure fallback shape (raw window as UserMemory).

    When the extraction LLM call fails (e.g. gateway overload), upstream stores
    the raw window text prefixed with "user: [timestamp]:" instead of an
    extracted fact. Such results are garbage for migration purposes.
    """
    return any(
        str(m.get("memory", "")).lstrip().startswith("user: [") for m in data if isinstance(m, dict)
    )


def _post_add_with_retry(
    api_base: str, api_key: str | None, payload: dict[str, Any], label: str
) -> dict[str, Any] | None:
    for attempt in range(1, RETRY_MAX + 1):
        try:
            result = _post_add(api_base, api_key, payload)
            if _looks_like_fallback(result.get("data") or []):
                print(f"[migrate] {label}: fallback raw-node output (LLM failure), retrying")
            else:
                return result
        except error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:200]
            print(f"[migrate] {label}: HTTP {e.code} (attempt {attempt}/{RETRY_MAX}): {body}")
        except Exception as e:
            print(f"[migrate] {label}: error (attempt {attempt}/{RETRY_MAX}): {e}")
        if attempt < RETRY_MAX:
            time.sleep(RETRY_BACKOFF_SECONDS)
    print(f"[migrate] {label}: giving up after {RETRY_MAX} attempts")
    return None


def _migrate_source(
    source_name: str,
    items: list[dict[str, Any]],
    args: argparse.Namespace,
    api_key: str | None,
    report: dict[str, Any],
) -> None:
    total = len(items)
    print(f"[migrate] source={source_name} active_records={total}")
    source_report = {"total": total, "batches": 0, "failed_batches": 0, "memory_ids": []}
    report[source_name] = source_report

    for start in range(0, total, args.batch_size):
        batch = items[start : start + args.batch_size]
        label = f"{source_name} batch {start // args.batch_size + 1}"
        if args.dry_run:
            for item in batch:
                print(f"[dry-run] {label}: {item['text'][:110]}")
            source_report["batches"] += 1
            continue

        payload: dict[str, Any] = {
            "user_id": args.user_id,
            "async_mode": "sync",
            # migration records are already-structured facts; skip the other
            # category extractors to keep the per-batch LLM burst minimal
            "allow_memory_view": ["detail_factual"],
            "info": {"source": "v1-migration", **batch[0]["meta"]},
            "messages": [{"role": "user", "content": item["text"]} for item in batch],
        }
        _wait_for_cpu_headroom(args.cpu_gate_idle, args.cpu_gate_max_wait)
        result = _post_add_with_retry(args.api_base, api_key, payload, label)
        source_report["batches"] += 1
        if result is None:
            source_report["failed_batches"] += 1
            continue
        data = result.get("data") or []
        ids = [m.get("memory_id") for m in data if isinstance(m, dict)]
        source_report["memory_ids"].extend(ids)
        print(f"[migrate] {label}: added {len(ids)} memories")
        time.sleep(args.batch_pause_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-dir", default=os.path.expanduser("~/Documents/memory"))
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--user-id", default="llwwds")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE_DEFAULT)
    parser.add_argument(
        "--batch-pause-seconds", type=int, default=2, help="pause between successful batches"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", default=None, help="optional path for the JSON report")
    parser.add_argument(
        "--cpu-gate-idle", type=float, default=25.0,
        help="wait before each batch until host CPU idle >= this percent (0 disables)",
    )
    parser.add_argument(
        "--cpu-gate-max-wait", type=float, default=900.0,
        help="max seconds to wait at the CPU gate per batch",
    )
    parser.add_argument(
        "--sources", default="persona,pitfalls,events", help="comma-separated sources to migrate"
    )
    args = parser.parse_args()

    api_key = os.getenv("MEMOS_API_KEY", "").strip() or None
    loaders = {
        "persona": _load_persona,
        "pitfalls": _load_pitfalls,
        "events": _load_events,
    }
    report: dict[str, Any] = {"args": vars(args), "sources": {}}

    for name in [s.strip() for s in args.sources.split(",") if s.strip()]:
        loader = loaders.get(name)
        if loader is None:
            print(f"[migrate] unknown source '{name}', skipping")
            continue
        items = loader(args.db_dir)
        _migrate_source(name, items, args, api_key, report)

    failed = sum(s.get("failed_batches", 0) for s in report["sources"].values())
    total_batches = sum(s.get("batches", 0) for s in report["sources"].values())
    added = sum(len(s.get("memory_ids", [])) for s in report["sources"].values())
    print(f"[migrate] done: batches={total_batches} failed={failed} memories_added={added}")

    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"[migrate] report written to {args.report}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
