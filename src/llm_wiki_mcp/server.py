"""FastMCP server entry for llm-wiki-mcp.

Wires the 4 tools into a FastMCP server, sets explicit tool annotations
(MCP spec 2025-03-26+), and exposes a `main()` CLI for stdio transport.

Why annotations are set explicitly: per MCP spec, the default for an
unannotated tool is `destructive=true, readOnly=false, idempotent=false,
openWorld=true` — i.e., the most dangerous classification. Clients use
these hints to decide whether to prompt the user before invocation. We
declare every tool's true behavior so users get accurate prompts.
"""

from __future__ import annotations

import argparse
from datetime import date as date_cls
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from llm_wiki_mcp.storage import WikiStorage
from llm_wiki_mcp.storage.local import LocalFilesystemStorage
from llm_wiki_mcp.tools.inventory import wiki_inventory as _wiki_inventory
from llm_wiki_mcp.tools.log_append import wiki_log_append as _wiki_log_append
from llm_wiki_mcp.tools.read import wiki_read as _wiki_read
from llm_wiki_mcp.tools.write_page import wiki_write_page as _wiki_write_page


def create_server(*, storage: WikiStorage) -> FastMCP:
    """Construct a FastMCP server bound to any WikiStorage backend.

    This is the composition-root entry point. Pass in a fully-constructed
    storage implementation (LocalFilesystemStorage, a test fake, a
    third-party SQLite/Notion/GDrive adapter — anything satisfying the
    `WikiStorage` Protocol) and get back a FastMCP server with the four
    wiki tools wired in.

    For the common case of "give me a server for this local path",
    `build_server(wiki_root=...)` is a thin wrapper that constructs
    `LocalFilesystemStorage` for you.
    """
    mcp = FastMCP("llm-wiki-mcp")

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        )
    )
    async def wiki_read(slug: str) -> dict[str, Any]:
        """Read one wiki page. Returns frontmatter, body, outgoing links, and etag."""
        page = await _wiki_read(storage, slug=slug)
        return page.model_dump()

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=True,
            openWorldHint=False,
        )
    )
    async def wiki_write_page(slug: str, body: str, etag: str | None = None) -> str:
        """Write a wiki page atomically. Use etag for safe updates; omit etag only when creating."""
        return await _wiki_write_page(storage, slug=slug, body=body, etag=etag)

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        )
    )
    async def wiki_log_append(
        operation: str,
        title: str,
        timestamp: date_cls | None = None,
        extra_lines: list[str] | None = None,
    ) -> dict[str, Any]:
        """Append an entry to log.md in Karpathy's format-locked line shape."""
        entry = await _wiki_log_append(
            storage,
            operation=operation,
            title=title,
            timestamp=timestamp,
            extra_lines=extra_lines,
        )
        return entry.model_dump()

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        )
    )
    async def wiki_inventory(scan_for: list[str] | None = None) -> dict[str, Any]:
        """Return the full wiki graph.

        Includes pages, frontmatter, link edges, log entries, and optional
        plain-text mentions for the given search terms.
        """
        inv = await _wiki_inventory(storage, scan_for=scan_for)
        return inv.model_dump()

    return mcp


def build_server(*, wiki_root: Path) -> FastMCP:
    """Construct a FastMCP server bound to a local filesystem wiki root.

    Thin convenience wrapper over `create_server` for the common case —
    external consumers who want to plug their own storage backend should
    call `create_server(storage=...)` directly.
    """
    return create_server(storage=LocalFilesystemStorage(wiki_root=wiki_root))


def main() -> None:
    parser = argparse.ArgumentParser(prog="llm-wiki-mcp")
    parser.add_argument(
        "--wiki-root",
        type=Path,
        required=True,
        help="Path to the local wiki root directory.",
    )
    args = parser.parse_args()

    server = build_server(wiki_root=args.wiki_root)
    server.run()  # FastMCP defaults to stdio transport


if __name__ == "__main__":
    main()
