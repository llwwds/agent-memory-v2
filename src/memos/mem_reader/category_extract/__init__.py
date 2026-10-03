"""Category extraction framework (agent-memory-v2 own module, not an upstream file).

Implements the cloud-edition `custom_extract_prompt` contract shape on the OSS
codebase: extraction prompts organised as a per-category-key registry, executed
in parallel over the fine-extraction windows, each category producing memory
nodes whose `memory_type` routes them into the corresponding response view
(`*_detail_list`) on the read path.

M1 carries `preference` (framework-run) and registers `detail_factual`
(delegated to the upstream string-fine extractor). M2-M4 add event / tool_memory
/ skill categories on the same registry.
"""

from memos.mem_reader.category_extract.registry import (
    CATEGORY_REGISTRY,
    CategorySpec,
    enabled_categories,
    framework_enabled,
)
from memos.mem_reader.category_extract.runner import run_category_extraction


__all__ = [
    "CATEGORY_REGISTRY",
    "CategorySpec",
    "enabled_categories",
    "framework_enabled",
    "run_category_extraction",
]
