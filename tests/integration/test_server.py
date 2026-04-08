"""FastMCP server smoke test.

We use FastMCP's in-memory client to drive the server end-to-end without
spawning a subprocess. This validates that:
- All 4 tools are registered
- Each tool has the correct annotations
- A round-trip write → read → inventory works through the MCP boundary
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastmcp import Client

from llm_wiki_mcp.server import build_server
from llm_wiki_mcp.storage.local import LocalFilesystemStorage


@pytest.fixture
def server(tmp_path: Path):
    root = tmp_path / "wiki-root"
    root.mkdir()
    return build_server(storage=LocalFilesystemStorage(wiki_root=root))


async def test_all_four_tools_registered(server):
    async with Client(server) as client:
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert names == {
            "wiki_read",
            "wiki_write_page",
            "wiki_log_append",
            "wiki_inventory",
        }


async def test_annotations_set_explicitly(server):
    async with Client(server) as client:
        tools = await client.list_tools()
        by_name = {t.name: t for t in tools}

        # wiki_read: read-only, idempotent
        assert by_name["wiki_read"].annotations.readOnlyHint is True
        assert by_name["wiki_read"].annotations.idempotentHint is True
        assert by_name["wiki_read"].annotations.destructiveHint is False
        assert by_name["wiki_read"].annotations.openWorldHint is False

        # wiki_inventory: read-only, idempotent
        assert by_name["wiki_inventory"].annotations.readOnlyHint is True
        assert by_name["wiki_inventory"].annotations.idempotentHint is True

        # wiki_write_page: destructive but idempotent (CAS)
        assert by_name["wiki_write_page"].annotations.readOnlyHint is False
        assert by_name["wiki_write_page"].annotations.destructiveHint is True
        assert by_name["wiki_write_page"].annotations.idempotentHint is True

        # wiki_log_append: not destructive (only appends), not idempotent
        assert by_name["wiki_log_append"].annotations.readOnlyHint is False
        assert by_name["wiki_log_append"].annotations.destructiveHint is False
        assert by_name["wiki_log_append"].annotations.idempotentHint is False


async def test_round_trip_write_read_inventory(server):
    async with Client(server) as client:
        await client.call_tool(
            "wiki_write_page",
            {"slug": "pg", "body": "---\ntitle: P\n---\nbody [[other]]"},
        )
        read = await client.call_tool("wiki_read", {"slug": "pg"})
        assert "pg" in str(read)

        inv = await client.call_tool("wiki_inventory", {})
        assert "pg" in str(inv)


async def test_build_server_with_injected_storage(tmp_path: Path):
    """The composition-root DI boundary: external consumers construct
    their own WikiStorage impl (LocalFilesystemStorage today, or a third
    party SQLite/Notion/GDrive adapter / test fake tomorrow) and hand
    it to `build_server` to get a fully-wired FastMCP server back.
    """
    storage = LocalFilesystemStorage(wiki_root=tmp_path)
    server = build_server(storage=storage)

    async with Client(server) as client:
        await client.call_tool(
            "wiki_write_page",
            {"slug": "pg", "body": "---\ntitle: P\n---\nhello"},
        )
        inv = await client.call_tool("wiki_inventory", {})
        assert "pg" in str(inv)
