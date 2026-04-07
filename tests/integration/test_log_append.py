"""wiki_log_append tool — Karpathy's format-locked log append.

Why this tool exists at all (justification under the North Star):
- O_APPEND is true append-only; LLMs trying to do read-modify-write would
  lose entries under concurrency.
- The line format `## [YYYY-MM-DD] op | Title` is the ONE format Karpathy
  explicitly locks. Filesystem MCP cannot enforce it; we can.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from llm_wiki_mcp.errors import WikiSchemaViolationError
from llm_wiki_mcp.storage.local import LocalFilesystemStorage
from llm_wiki_mcp.tools.log_append import wiki_log_append


@pytest.fixture
def storage(tmp_path: Path) -> LocalFilesystemStorage:
    root = tmp_path / "wiki-root"
    root.mkdir()
    (root / "wiki").mkdir()
    return LocalFilesystemStorage(wiki_root=root)


async def test_append_minimal(storage: LocalFilesystemStorage):
    result = await wiki_log_append(
        storage,
        operation="ingest",
        title="Attention Is All You Need",
        timestamp=date(2026, 4, 7),
    )
    assert result.operation == "ingest"
    assert result.title == "Attention Is All You Need"

    text = await storage.read_log()
    assert "## [2026-04-07] ingest | Attention Is All You Need" in text


async def test_append_with_extra_lines(storage: LocalFilesystemStorage):
    result = await wiki_log_append(
        storage,
        operation="ingest",
        title="X",
        timestamp=date(2026, 4, 7),
        extra_lines=["Pages written: x", "Pages updated: a, b"],
    )
    assert result.extra_lines == ["Pages written: x", "Pages updated: a, b"]


async def test_append_rejects_bad_operation(storage: LocalFilesystemStorage):
    with pytest.raises(WikiSchemaViolationError):
        await wiki_log_append(
            storage,
            operation="bad op with spaces",
            title="X",
            timestamp=date(2026, 4, 7),
        )


async def test_append_accepts_any_operation_word(storage: LocalFilesystemStorage):
    """We do NOT enum-lock operation. Karpathy listed examples; users
    co-evolve their own."""
    for op in ["ingest", "query", "lint", "init", "update", "digest", "graph"]:
        await wiki_log_append(storage, operation=op, title=f"t-{op}", timestamp=date(2026, 4, 7))
