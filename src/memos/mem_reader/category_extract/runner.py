"""Category extraction runner (agent-memory-v2 own module).

Executes per-category LLM extraction over the fast-mode windows. Called from
the reader's fine-extraction stage in place of (or alongside) upstream
extractors; each enabled category contributes its own nodes.

Contract:
    run_category_extraction(fast_items, info, llm, embedder,
                            categories=None, **kwargs) -> list[TextualMemoryItem]

`categories` carries the request-level allow-list (allow_memory_view); None
means "whatever the registry enables". Errors in one category/item never abort
the run — they are logged and skipped, mirroring upstream extractor behaviour.
"""

from concurrent.futures import as_completed
from typing import TYPE_CHECKING, Any

from memos.context.context import ContextThreadPoolExecutor
from memos.log import get_logger
from memos.mem_reader.category_extract.prompts import PREFERENCE_PROMPTS
from memos.mem_reader.category_extract.registry import enabled_categories
from memos.mem_reader.read_multi_modal import detect_lang
from memos.mem_reader.utils import derive_key, parse_json_result
from memos.memories.textual.item import TextualMemoryItem, TreeNodeTextualMemoryMetadata


if TYPE_CHECKING:
    from memos.types.general_types import UserContext


logger = get_logger(__name__)

_PREFERENCE_TYPE_ALIASES = {
    "explicit": "explicit",
    "explicit_preference": "explicit",
    "implicit": "implicit",
    "implicit_preference": "implicit",
    "显式": "explicit",
    "隐式": "implicit",
}


def _normalize_preference_type(raw: Any) -> str | None:
    value = str(raw or "").strip().lower()
    return _PREFERENCE_TYPE_ALIASES.get(value)


def _build_preference_node(
    record: dict[str, Any],
    fast_item: TextualMemoryItem,
    info: dict[str, Any],
    embedder: Any,
    **kwargs,
) -> TextualMemoryItem | None:
    preference = str(record.get("preference") or "").strip()
    if not preference:
        return None

    preference_type = _normalize_preference_type(record.get("preference_type")) or "implicit"
    reasoning = str(record.get("reasoning") or "").strip()
    context_summary = str(record.get("context_summary") or "").strip() or preference

    info_ = info.copy() if isinstance(info, dict) else {}
    info_.pop("user_id", None)
    info_.pop("session_id", None)

    user_context: UserContext | None = kwargs.get("user_context")
    extra: dict[str, Any] = {}
    if user_context:
        if user_context.manager_user_id:
            extra["manager_user_id"] = user_context.manager_user_id
        if user_context.project_id:
            extra["project_id"] = user_context.project_id

    embedding = None
    if embedder is not None:
        try:
            embedding = embedder.embed([context_summary])[0]
        except Exception as e:
            logger.warning(f"[CategoryExtract] preference embedding failed: {e}")

    sources = getattr(fast_item.metadata, "sources", None)

    return TextualMemoryItem(
        memory=context_summary,
        metadata=TreeNodeTextualMemoryMetadata(
            memory_type="PreferenceMemory",
            status="activated",
            tags=["category:preference"],
            key=derive_key(preference),
            embedding=embedding,
            usage=[],
            sources=sources,
            background="",
            confidence=0.99,
            type="chat",
            info=info_,
            # preference-specific contract fields (metadata is extra=allow)
            preference=preference,
            preference_type=preference_type,
            reasoning=reasoning,
            **extra,
        ),
    )


def _extract_preference_items(
    fast_items: list[TextualMemoryItem],
    info: dict[str, Any],
    llm: Any,
    embedder: Any,
    **kwargs,
) -> list[TextualMemoryItem]:
    """One LLM call per window; returns preference nodes for the whole request."""
    nodes: list[TextualMemoryItem] = []
    seen_preferences: set[str] = set()

    for fast_item in fast_items:
        mem_str = (fast_item.memory or "").strip()
        if not mem_str:
            continue

        lang = detect_lang(mem_str)
        prompt = PREFERENCE_PROMPTS[lang].replace("${conversation}", mem_str)
        try:
            raw = llm.generate([{"role": "user", "content": prompt}])
        except Exception as e:
            logger.error(f"[CategoryExtract] preference LLM call failed: {e}")
            continue
        if not raw:
            continue

        parsed = parse_json_result(raw)
        records = parsed.get("preference list", []) if isinstance(parsed, dict) else []
        if not isinstance(records, list):
            continue

        for record in records:
            if not isinstance(record, dict):
                continue
            node = _build_preference_node(record, fast_item, info, embedder, **kwargs)
            if node is None:
                continue
            dedupe_key = node.metadata.preference.strip().lower()
            if dedupe_key in seen_preferences:
                # windows overlap by design; keep the first occurrence
                continue
            seen_preferences.add(dedupe_key)
            nodes.append(node)

    if nodes:
        logger.info(f"[CategoryExtract] preference extracted {len(nodes)} nodes")
    return nodes


_EXTRACTORS = {
    "preference": _extract_preference_items,
}


def run_category_extraction(
    fast_items: list[TextualMemoryItem],
    info: dict[str, Any],
    llm: Any,
    embedder: Any,
    categories: list[str] | None = None,
    **kwargs,
) -> list[TextualMemoryItem]:
    """Run all enabled categories over the fast windows, in parallel.

    Args:
        fast_items: fast-mode window items (memory text + sources)
        info: request info dict (user_id/session_id already required upstream)
        llm: extractor LLM (reader's preference_extractor_llm / general_llm)
        embedder: reader embedder
        categories: request-level allow-list (allow_memory_view); None = registry default
    """
    if categories is None:
        category_keys = enabled_categories()
    else:
        category_keys = enabled_categories(allow=categories)
    if not category_keys or not fast_items:
        return []

    nodes: list[TextualMemoryItem] = []
    with ContextThreadPoolExecutor(max_workers=min(10, len(category_keys))) as executor:
        futures = {}
        for key in category_keys:
            extractor = _EXTRACTORS.get(key)
            if extractor is None:
                logger.warning(f"[CategoryExtract] no extractor registered for '{key}'")
                continue
            futures[executor.submit(extractor, fast_items, info, llm, embedder, **kwargs)] = key

        for future in as_completed(list(futures)):
            key = futures[future]
            try:
                nodes.extend(future.result())
            except Exception as e:
                logger.error(f"[CategoryExtract] category '{key}' failed: {e}", exc_info=True)

    return nodes
