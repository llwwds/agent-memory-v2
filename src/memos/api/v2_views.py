"""Category view dispatch for API responses (agent-memory-v2 own module).

Read-side half of the v2 pipeline: derives the cloud-shaped per-category
detail lists (`memory_detail_list`, `preference_detail_list`, ...) from the
bucketed search/get results, without touching the legacy buckets.

Contract per record (common fields): id / conversation_id / status / relativity,
plus per-category fields aligned with the v2 development plan:
- memory_detail_list:      memory_key / memory_value / memory_type
- preference_detail_list:  preference / preference_type (explicit|implicit) / reasoning
- event_detail_list:       event_key / event_value / event_time / event_location / event_roles (M2)
- tool_memory_detail_list: tool_type / tool_value / tool_used_status / experience (M3)
- skill_detail_list:       skill_value / skill_url / skill_type (M4)
"""

import json

from typing import Any

from memos.log import get_logger


logger = get_logger(__name__)

# category key -> response view field (mirrors mem_reader.category_extract registry;
# duplicated here so the API layer does not depend on the reader package)
VIEW_FIELDS: dict[str, str] = {
    "detail_factual": "memory_detail_list",
    "preference": "preference_detail_list",
    "event": "event_detail_list",
    "tool_memory": "tool_memory_detail_list",
    "skill": "skill_detail_list",
}

_FACT_MEMORY_TYPES = {"WorkingMemory", "LongTermMemory", "UserMemory"}
_TOOL_MEMORY_TYPES = {"ToolSchemaMemory", "ToolTrajectoryMemory"}
_SKILL_MEMORY_TYPES = {"SkillMemory"}
_PREFERENCE_MEMORY_TYPES = {"PreferenceMemory"}


def _pref_type(raw: Any) -> str:
    value = str(raw or "").strip().lower()
    if value in {"explicit", "explicit_preference", "显式"}:
        return "explicit"
    if value in {"implicit", "implicit_preference", "隐式"}:
        return "implicit"
    return "implicit"


def _common_fields(mem: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": mem.get("id") or meta.get("id"),
        "conversation_id": meta.get("session_id"),
        "status": meta.get("status"),
        "relativity": meta.get("relativity"),
    }


def _memory_detail(mem: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    detail = _common_fields(mem, meta)
    detail.update(
        {
            "memory_key": meta.get("key"),
            "memory_value": mem.get("memory"),
            "memory_type": meta.get("memory_type"),
            "create_time": meta.get("created_at"),
            "update_time": meta.get("updated_at"),
            "tags": meta.get("tags") or [],
        }
    )
    return detail


def _preference_detail(mem: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    detail = _common_fields(mem, meta)
    detail.update(
        {
            "preference": meta.get("preference") or mem.get("memory"),
            "preference_type": _pref_type(meta.get("preference_type")),
            "reasoning": meta.get("reasoning"),
            "memory_value": mem.get("memory"),
            "create_time": meta.get("created_at"),
            "update_time": meta.get("updated_at"),
        }
    )
    return detail


def _normalize_tool_used_status(raw: Any) -> list[dict[str, Any]]:
    """Normalize tool_used_status to a list of objects.

    Upstream LLM output occasionally double-encodes entries as JSON strings;
    parse them so the view always exposes the contract object shape.
    """
    normalized: list[dict[str, Any]] = []
    for entry in raw if isinstance(raw, list) else []:
        if isinstance(entry, str):
            try:
                entry = json.loads(entry)
            except (ValueError, TypeError):
                entry = {"tool_experience": entry} if entry.strip() else None
        if isinstance(entry, dict):
            normalized.append(entry)
        elif isinstance(entry, str) and entry.strip():
            normalized.append({"tool_experience": entry})
    return normalized


def _tool_memory_detail(mem: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    detail = _common_fields(mem, meta)
    detail.update(
        {
            "tool_type": meta.get("memory_type"),
            "tool_value": meta.get("tool_value") or mem.get("memory"),
            "tool_used_status": _normalize_tool_used_status(meta.get("tool_used_status")),
            "experience": meta.get("experience"),
            "correctness": meta.get("correctness"),
            "create_time": meta.get("created_at"),
            "update_time": meta.get("updated_at"),
        }
    )
    return detail


def _skill_detail(mem: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    detail = _common_fields(mem, meta)
    # upstream SkillMemory nodes carry name/description/procedure/experience/
    # preference/examples on metadata; assemble the cloud-shaped skill_value object
    skill_value_obj = {
        key: meta.get(key)
        for key in ("name", "description", "procedure", "experience", "preference", "examples")
        if meta.get(key)
    }
    detail.update(
        {
            "skill_value": meta.get("skill_value") or (skill_value_obj or mem.get("memory")),
            "skill_url": meta.get("skill_url") or meta.get("url"),
            "skill_type": meta.get("skill_type") or "procedural",
            "create_time": meta.get("created_at"),
            "update_time": meta.get("updated_at"),
        }
    )
    return detail


def _event_detail(mem: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    detail = _common_fields(mem, meta)
    detail.update(
        {
            "event_key": meta.get("key") or meta.get("event_key"),
            "event_value": meta.get("event_value") or mem.get("memory"),
            "event_time": meta.get("event_time"),
            "event_location": meta.get("event_location"),
            "event_roles": meta.get("event_roles") or [],
            "create_time": meta.get("created_at"),
            "update_time": meta.get("updated_at"),
        }
    )
    return detail


_DETAIL_BUILDERS = {
    "memory_detail_list": _memory_detail,
    "preference_detail_list": _preference_detail,
    "event_detail_list": _event_detail,
    "tool_memory_detail_list": _tool_memory_detail,
    "skill_detail_list": _skill_detail,
}


def _route_view_field(meta: dict[str, Any]) -> str | None:
    """Map one memory's metadata to its response view field."""
    memory_type = meta.get("memory_type")

    # event routing: explicit form marker wins over the storage type (M2)
    if meta.get("memory_form") == "event":
        return "event_detail_list"

    if memory_type in _FACT_MEMORY_TYPES:
        return "memory_detail_list"
    if memory_type in _PREFERENCE_MEMORY_TYPES:
        return "preference_detail_list"
    if memory_type in _TOOL_MEMORY_TYPES:
        return "tool_memory_detail_list"
    if memory_type in _SKILL_MEMORY_TYPES:
        return "skill_detail_list"
    return None


def _iter_bucket_memories(results: dict[str, Any]):
    """Yield (memory_dict, metadata_dict) from every bucket in the results dict."""
    for value in results.values():
        if not isinstance(value, list):
            continue
        for bucket in value:
            if not isinstance(bucket, dict):
                continue
            for mem in bucket.get("memories") or []:
                if not isinstance(mem, dict):
                    continue
                meta = mem.get("metadata")
                if not isinstance(meta, dict):
                    continue
                yield mem, meta


def build_category_views(results: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Derive per-category detail lists from a bucketed results dict."""
    views: dict[str, list[dict[str, Any]]] = {field: [] for field in VIEW_FIELDS.values()}

    seen: set[str] = set()
    for mem, meta in _iter_bucket_memories(results):
        view_field = _route_view_field(meta)
        if view_field is None:
            continue
        mem_id = str(mem.get("id") or meta.get("id") or "")
        if mem_id and mem_id in seen:
            continue
        if mem_id:
            seen.add(mem_id)
        try:
            views[view_field].append(_DETAIL_BUILDERS[view_field](mem, meta))
        except Exception:
            logger.warning("[v2_views] failed to build detail for memory %s", mem_id, exc_info=True)

    return views


def apply_memory_views(
    results: dict[str, Any], include_views: list[str] | None = None
) -> dict[str, Any]:
    """Augment a results dict with the category view fields, in place.

    include_views takes category keys (e.g. ['preference']); None includes all
    views. Legacy buckets (text_mem/pref_mem/...) are never modified.
    """
    views = build_category_views(results)

    if include_views is None:
        included = set(VIEW_FIELDS)
    else:
        included = {v for v in include_views if v in VIEW_FIELDS}

    for category, field in VIEW_FIELDS.items():
        if category in included:
            results[field] = views[field]

    logger.info(
        "[v2_views] applied views: included=%s counts=%s",
        sorted(included),
        {field: len(views[field]) for field in VIEW_FIELDS.values()},
    )
    return results
