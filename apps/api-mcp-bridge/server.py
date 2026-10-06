"""MemOS API MCP bridge (agent-memory-v3 own module, not an upstream file).

Stdio MCP server that forwards tool calls to the local MemOS `/product` HTTP API.

Why a bridge instead of upstream `memos.api.mcp_serve`: the upstream MCP server
instantiates a full in-process MOS and bypasses the FastAPI pipeline entirely.
v2 develops the category-extraction / view-dispatch pipeline in the API layer,
so the MCP entry must hit the API to exercise it (see the v2 development plan).

Runs as a container alongside the memos stack (host has zero install);
Codex launches it via `docker run -i`.
"""

import os
import sys

import httpx
from fastmcp import FastMCP

API_BASE = os.getenv("MEMOS_API_BASE", "http://memos:8000").rstrip("/")
API_KEY = os.getenv("MEMOS_API_KEY", "")
DEFAULT_USER_ID = os.getenv("MEMOS_DEFAULT_USER_ID", "llwwds")
TIMEOUT = float(os.getenv("MEMOS_API_TIMEOUT", "120"))

mcp = FastMCP(
    "memos",
    instructions=(
        "Long-term memory for the user across sessions. "
        "Use remember() to store durable facts/preferences/decisions/events from the conversation. "
        "Use recall() to retrieve relevant memories before answering questions about the user's "
        "past, preferences, projects or toolchain."
    ),
)


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    return headers


def _post(path: str, payload: dict) -> dict:
    resp = httpx.post(f"{API_BASE}{path}", json=payload, headers=_headers(), timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


@mcp.tool
def remember(content: str, user_id: str = "") -> str:
    """Store information worth keeping long-term into memory.

    Pass a self-contained statement (or a short exchange). Use for durable facts,
    preferences, decisions, events and tool/skill experience — not transient chatter.
    Returns the API result including the async processing status.
    """
    payload = {
        "user_id": user_id or DEFAULT_USER_ID,
        "messages": [{"role": "user", "content": content}],
    }
    result = _post("/product/add", payload)
    return str({"status": result.get("status"), "data": result.get("data")})


@mcp.tool
def recall(query: str, user_id: str = "") -> str:
    """Search long-term memory and return the most relevant records.

    Use before answering anything about the user's history, preferences, ongoing
    projects, toolchain or previously made decisions.
    """
    payload = {"query": query, "user_id": user_id or DEFAULT_USER_ID}
    result = _post("/product/search", payload)
    data = result.get("data") or {}
    # v2 category views: prefer the cloud-shaped *_detail_list fields
    views = {
        field: data[field]
        for field in (
            "memory_detail_list",
            "preference_detail_list",
            "event_detail_list",
            "tool_memory_detail_list",
            "skill_detail_list",
        )
        if data.get(field)
    }
    return str(views or data.get("memory_detail_list") or result)


def main() -> int:
    mcp.run(transport="stdio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
