"""Pour the frozen v1 memory snapshot into MemOS v2 via the /product/add API.

Design (approved 2026-10-04): the v1 records are already-atomic structured
memories, so the migration skips LLM extraction entirely — every record is one
`/product/add` request with a pure text item, `async_mode="sync"`, `mode="fast"`.
The reader's fast path stores the text verbatim as a LongTermMemory node
(embedding via local Ollama, no LLM gateway involvement).

Markers: info={"v1_source", "v1_id", "v1_status"} survives upstream filtering
(non-reserved keys) and lands as flat node properties, enabling per-source
filtering, idempotent re-runs and precise rollback.

Scope: persona (all) + pitfalls (all statuses) + events (except 不存在) +
tools (存在 only). conversations (L0) and _tag_pool vocabularies are not
migrated. The source is a frozen snapshot directory; the live memory/ DBs and
the v2 store are never read-modified by this script beyond the API calls.

Usage:
    python3 scripts/pour_v1_snapshot.py \
        --snapshot "/Users/llwwds/Documents/memory 快照备份/2026.10.4 新版记忆系统第一次注入前/memory" \
        --api-base http://127.0.0.1:8000 --user-id llwwds \
        [--skip-ids-file /tmp/poured_ids.json] [--report /tmp/pour_report.json]
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


RETRY_MAX = 3
RETRY_BACKOFF_SECONDS = 20
INTER_ADD_PAUSE_SECONDS = 0.2
EVENT_OVERVIEW_MAX = 1200
TOOL_FIELD_MAX = 800
MILESTONE_MAX = 3
MILESTONE_TITLE_MAX = 120


def _connect(db_dir: str, name: str) -> sqlite3.Connection | None:
    path = os.path.join(db_dir, name)
    if not os.path.exists(path):
        print(f"[pour] missing database: {path}")
        return None
    return sqlite3.connect(path)


def _load_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return [str(x) for x in parsed] if isinstance(parsed, list) else []
    except (ValueError, TypeError):
        return []


def _clip(text: str | None, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


# ---------------------------------------------------------------- loaders


def load_persona(db_dir: str) -> list[dict[str, Any]]:
    db = _connect(db_dir, "persona.db")
    if db is None:
        return []
    rows = db.execute(
        "SELECT id, section, key, content, status FROM persona ORDER BY id"
    ).fetchall()
    db.close()
    items = []
    for pid, section, key, content, status in rows:
        text = f"[v1-persona #{pid}][{section}] {key}: {content}"
        items.append(
            {
                "id": pid,
                "text": text,
                "meta": {"v1_source": "persona", "v1_id": str(pid), "v1_status": status},
            }
        )
    return items


def load_pitfalls(db_dir: str) -> list[dict[str, Any]]:
    db = _connect(db_dir, "pitfalls.db")
    if db is None:
        return []
    rows = db.execute(
        "SELECT id, scene, stage, problem, root_cause, solution, recur_signal, event, device, status "
        "FROM pitfalls ORDER BY id"
    ).fetchall()
    db.close()
    items = []
    for pid, scene, stage, problem, root_cause, solution, recur_signal, event, device, status in rows:
        parts = [f"[v1-pitfall #{pid}][{scene or '未分类'}]（v1状态: {status}）"]
        if stage:
            parts.append(f"阶段: {stage}")
        if problem:
            parts.append(f"问题: {problem}")
        if root_cause:
            parts.append(f"根因: {root_cause}")
        if solution:
            parts.append(f"解决: {solution}")
        if recur_signal:
            parts.append(f"复发信号: {recur_signal}")
        events = _load_json_list(event)
        devices = _load_json_list(device)
        if events:
            parts.append(f"事件标签: {', '.join(events)}")
        if devices:
            parts.append(f"设备: {', '.join(devices)}")
        items.append(
            {
                "id": pid,
                "text": "\n".join(parts),
                "meta": {"v1_source": "pitfalls", "v1_id": str(pid), "v1_status": status},
            }
        )
    return items


def load_events(db_dir: str) -> list[dict[str, Any]]:
    db = _connect(db_dir, "events.db")
    if db is None:
        return []
    rows = db.execute(
        "SELECT id, name, overview, milestones, status, updated_at FROM events "
        "WHERE status != '不存在' ORDER BY id"
    ).fetchall()
    db.close()
    items = []
    for eid, name, overview, milestones, status, updated_at in rows:
        text = f"[v1-event #{eid}] {name}（v1状态: {status}，更新于 {updated_at}）：{_clip(overview, EVENT_OVERVIEW_MAX)}"
        titles: list[str] = []
        if milestones:
            try:
                parsed = json.loads(milestones)
                if isinstance(parsed, list):
                    for m in parsed:
                        if len(titles) >= MILESTONE_MAX:
                            break
                        title = (
                            (m.get("title") or m.get("milestone") or "")
                            if isinstance(m, dict)
                            else str(m)
                        )
                        if title:
                            titles.append(_clip(title, MILESTONE_TITLE_MAX))
            except (ValueError, TypeError):
                pass
        if titles:
            text += "\n近期节点: " + "；".join(titles)
        items.append(
            {
                "id": eid,
                "text": text,
                "meta": {"v1_source": "events", "v1_id": str(eid), "v1_status": status},
            }
        )
    return items


def load_tools(db_dir: str) -> list[dict[str, Any]]:
    db = _connect(db_dir, "tools.db")
    if db is None:
        return []
    rows = db.execute(
        "SELECT id, name, device, event, overview, usage_guide, tech_manual, status FROM tools "
        "WHERE status = '存在' ORDER BY id"
    ).fetchall()
    db.close()
    items = []
    for tid, name, device, event, overview, usage_guide, tech_manual, status in rows:
        parts = [f"[v1-tool #{tid}] {name}（v1状态: {status}）"]
        if overview:
            parts.append(f"概述: {_clip(overview, TOOL_FIELD_MAX)}")
        devices = _load_json_list(device)
        events = _load_json_list(event)
        tags = []
        if devices:
            tags.append(f"设备: {', '.join(devices)}")
        if events:
            tags.append(f"事件: {', '.join(events)}")
        if tags:
            parts.append("；".join(tags))
        if usage_guide:
            parts.append(f"使用指南: {_clip(usage_guide, TOOL_FIELD_MAX)}")
        if tech_manual:
            parts.append(f"技术手册: {_clip(tech_manual, TOOL_FIELD_MAX)}")
        items.append(
            {
                "id": tid,
                "text": "\n".join(parts),
                "meta": {"v1_source": "tools", "v1_id": str(tid), "v1_status": status},
            }
        )
    return items


# ---------------------------------------------------------------- api


def _post_json(api_base: str, path: str, payload: dict[str, Any], api_key: str | None, timeout: int = 120) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    req = request.Request(f"{api_base.rstrip('/')}{path}", data=body, headers=headers, method="POST")
    with request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def pour_one(api_base: str, api_key: str | None, user_id: str, item: dict[str, Any]) -> tuple[str | None, str | None]:
    """Add one record; returns (memory_id, error)."""
    payload = {
        "user_id": user_id,
        "async_mode": "sync",
        "mode": "fast",
        "info": item["meta"],
        "messages": [{"type": "text", "text": item["text"]}],
    }
    for attempt in range(1, RETRY_MAX + 1):
        try:
            result = _post_json(api_base, "/product/add", payload, api_key)
            data = result.get("data") or []
            if result.get("code") == 200 and data:
                mem = data[0]
                # fast path echoes the record verbatim; anything else is a red flag
                if str(mem.get("memory", "")).strip() == item["text"].strip():
                    return mem.get("memory_id"), None
                return None, f"echo mismatch: {str(mem.get('memory', ''))[:80]}"
            return None, f"unexpected response: code={result.get('code')} {str(result)[:120]}"
        except error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:150]
            err = f"HTTP {e.code}: {body}"
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        if attempt < RETRY_MAX:
            time.sleep(RETRY_BACKOFF_SECONDS)
    return None, err


# ---------------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, help="frozen snapshot directory containing the 5 v1 .db files")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--user-id", default="llwwds")
    parser.add_argument("--pause", type=float, default=INTER_ADD_PAUSE_SECONDS)
    parser.add_argument("--skip-ids-file", default=None, help="JSON file of already-poured v1 ids ('source:id' keys) to skip")
    parser.add_argument("--report", default=None)
    parser.add_argument("--sources", default="persona,pitfalls,events,tools")
    args = parser.parse_args()

    api_key = os.getenv("MEMOS_API_KEY", "").strip() or None

    skip: set[str] = set()
    if args.skip_ids_file and os.path.exists(args.skip_ids_file):
        with open(args.skip_ids_file, encoding="utf-8") as f:
            skip = set(json.load(f))
        print(f"[pour] skipping {len(skip)} already-poured records")

    loaders = {
        "persona": load_persona,
        "pitfalls": load_pitfalls,
        "events": load_events,
        "tools": load_tools,
    }
    report: dict[str, Any] = {"snapshot": args.snapshot, "sources": {}}
    poured_keys: list[str] = list(skip)
    exit_code = 0

    for name in [s.strip() for s in args.sources.split(",") if s.strip()]:
        items = loaders[name](args.snapshot)
        src_report: dict[str, Any] = {
            "total": len(items),
            "poured": 0,
            "skipped": 0,
            "failed": 0,
            "failures": [],
            "memory_ids": [],
        }
        report["sources"][name] = src_report
        print(f"[pour] source={name} records={len(items)}")
        for item in items:
            key = f"{name}:{item['id']}"
            if key in skip:
                src_report["skipped"] += 1
                continue
            mem_id, err = pour_one(args.api_base, api_key, args.user_id, item)
            if mem_id:
                src_report["poured"] += 1
                src_report["memory_ids"].append(mem_id)
                poured_keys.append(key)
            else:
                src_report["failed"] += 1
                src_report["failures"].append({"id": item["id"], "error": err})
                print(f"[pour] FAIL {key}: {err}")
            time.sleep(args.pause)
        print(f"[pour] source={name} done: poured={src_report['poured']} skipped={src_report['skipped']} failed={src_report['failed']}")

    total_poured = sum(s["poured"] for s in report["sources"].values())
    total_failed = sum(s["failed"] for s in report["sources"].values())
    print(f"[pour] ALL DONE: poured={total_poured} failed={total_failed}")
    if total_failed:
        exit_code = 1

    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"[pour] report written to {args.report}")

    skip_path = args.skip_ids_file or "/tmp/poured_ids.json"
    with open(skip_path, "w", encoding="utf-8") as f:
        json.dump(sorted(set(poured_keys)), f)
    print(f"[pour] poured-keys written to {skip_path}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
