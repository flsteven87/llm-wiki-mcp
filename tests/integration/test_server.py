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
from tests._fakes.drive import FakeDrive


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


def test_build_server_uses_local_when_wiki_root_given(tmp_path):
    server = build_server(wiki_root=tmp_path)
    assert server is not None


def test_build_server_uses_gdrive_when_gdrive_args_given():
    drive = FakeDrive()
    wiki = drive._seed_file(name="wiki", parents=["rootABC"], content=b"")
    drive._seed_file(name="pages", parents=[wiki.id], content=b"")

    server = build_server(gdrive_service=drive, gdrive_root_folder_id="rootABC")
    assert server is not None


def test_build_server_rejects_both_backends(tmp_path):
    with pytest.raises(ValueError, match="exactly one"):
        build_server(wiki_root=tmp_path, gdrive_root_folder_id="r")


def test_build_server_rejects_neither_backend():
    with pytest.raises(ValueError, match="exactly one"):
        build_server()
