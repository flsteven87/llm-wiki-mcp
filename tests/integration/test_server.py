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


@pytest.fixture
def server(tmp_path: Path):
    root = tmp_path / "wiki-root"
    root.mkdir()
    return build_server(wiki_root=root)


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


def test_build_server_constructs_local_backend(tmp_path):
    server = build_server(wiki_root=tmp_path)
    assert server is not None


async def test_create_server_accepts_injected_storage(tmp_path: Path):
    """The new composition-root DI boundary: external consumers pass
    their own WikiStorage impl (SQLite / Notion / GDrive v2 / test fake)
    and get a fully-wired FastMCP server back without touching tool code.
    """
    from llm_wiki_mcp.server import create_server
    from llm_wiki_mcp.storage.local import LocalFilesystemStorage

    storage = LocalFilesystemStorage(wiki_root=tmp_path)
    server = create_server(storage=storage)

    async with Client(server) as client:
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert names == {
            "wiki_read",
            "wiki_write_page",
            "wiki_log_append",
            "wiki_inventory",
        }


async def test_build_server_is_thin_wrapper_over_create_server(tmp_path: Path):
    """build_server must keep working as the "give me a server for this
    filesystem path" convenience — but internally go through create_server
    so both paths exercise the same code.
    """
    server = build_server(wiki_root=tmp_path)
    async with Client(server) as client:
        await client.call_tool(
            "wiki_write_page",
            {"slug": "pg", "body": "---\ntitle: P\n---\nhello"},
        )
        inv = await client.call_tool("wiki_inventory", {})
        assert "pg" in str(inv)
