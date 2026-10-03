"""Category registry for the v2 extraction pipeline (agent-memory-v2 own module).

Each entry mirrors a cloud category key and the response view field it feeds.
`detail_factual` is registered for contract mapping but its extraction is
delegated to the upstream string-fine extractor (it owns merge/conflict
handling), so it carries no framework prompt of its own in M1.
"""

from dataclasses import dataclass, field

import os


FRAMEWORK_ENV = "MEMOS_CATEGORY_EXTRACT"


@dataclass(frozen=True)
class CategorySpec:
    """Declarative description of one extraction category."""

    key: str  # cloud category key, e.g. "preference"
    view_field: str  # response field this category feeds, e.g. "preference_detail_list"
    memory_types: tuple[str, ...]  # node memory_type(s) produced by this category
    env_flag: str | None = None  # per-category enable env var, None = always on when framework on
    has_extractor: bool = True  # False = delegated to an upstream extractor (M1: detail_factual)


CATEGORY_REGISTRY: dict[str, CategorySpec] = {
    "detail_factual": CategorySpec(
        key="detail_factual",
        view_field="memory_detail_list",
        memory_types=("WorkingMemory", "LongTermMemory", "UserMemory"),
        has_extractor=False,  # extracted by the upstream string-fine path
    ),
    "preference": CategorySpec(
        key="preference",
        view_field="preference_detail_list",
        memory_types=("PreferenceMemory",),
        env_flag="MEMOS_CAT_PREFERENCE",
    ),
    # M2: event -> event_detail_list
    # M3: tool_memory -> tool_memory_detail_list
    # M4: skill -> skill_detail_list
}


def framework_enabled() -> bool:
    """Master switch for the v2 category framework (default on).

    When off, the reader falls back to pure upstream behaviour, including the
    ENABLE_PREFERENCE_MEMORY-gated upstream preference pipeline.
    """
    return os.getenv(FRAMEWORK_ENV, "on").strip().lower() not in {"0", "false", "no", "off"}


def enabled_categories(allow: list[str] | None = None) -> list[str]:
    """Return category keys that should run for this request.

    Order of filters (all must pass):
    - framework master switch (empty list when off)
    - per-category env flag (default on)
    - request-level `allow_memory_view` allow-list (None = no request-level restriction)
    """
    if not framework_enabled():
        return []

    enabled: list[str] = []
    for key, spec in CATEGORY_REGISTRY.items():
        if not spec.has_extractor:
            continue
        if spec.env_flag and os.getenv(spec.env_flag, "on").strip().lower() in {
            "0",
            "false",
            "no",
            "off",
        }:
            continue
        if allow is not None and key not in allow:
            continue
        enabled.append(key)
    return enabled
