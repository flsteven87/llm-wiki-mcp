"""FastMCP server entry for llm-wiki-mcp.

Public surface:
- `build_server(*, storage: WikiStorage) -> FastMCP` — composition root.
- `main()` — CLI entry; constructs `LocalFilesystemStorage` from
  `--wiki-root` and hands it to `build_server`.

Wires the 4 tools into a FastMCP server, sets explicit tool annotations
(MCP spec 2025-03-26+), and exposes a `main()` CLI for stdio transport.

Why annotations are set explicitly: per MCP spec, the default for an
unannotated tool is `destructive=true, readOnly=false, idempotent=false,
openWorld=true` — i.e., the most dangerous classification. Clients use
these hints to decide whether to prompt the user before invocation. We
declare every tool's true behavior so users get accurate prompts.

Why every tool wrapper catches `WikiError`: domain errors (etag conflict,
path escape, missing slug, raw/ write) are recoverable signals the
client LLM needs to react to. We map each to a FastMCP `ToolError` so
it surfaces as a structured, message-bearing error on the client side
instead of a generic crash. Unexpected exceptions are masked by
`mask_error_details=True` and show up as a generic internal error — the
boundary between "you did something wrong, retry differently" and "the
server itself broke" is load-bearing.
"""

from __future__ import annotations

import argparse
from datetime import date as date_cls
from pathlib import Path
from typing import Annotated, Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from llm_wiki_mcp import __version__
from llm_wiki_mcp.errors import WikiError
from llm_wiki_mcp.storage import WikiStorage
from llm_wiki_mcp.storage.local import LocalFilesystemStorage
from llm_wiki_mcp.tools.inventory import wiki_inventory as _wiki_inventory
from llm_wiki_mcp.tools.log_append import wiki_log_append as _wiki_log_append
from llm_wiki_mcp.tools.read import wiki_read as _wiki_read
from llm_wiki_mcp.tools.write_page import wiki_write_page as _wiki_write_page


def build_server(*, storage: WikiStorage) -> FastMCP:
    """Construct a FastMCP server bound to any WikiStorage backend.

    This is the composition root. Pass a fully-constructed storage
    implementation (LocalFilesystemStorage, a test fake, a third-party
    SQLite/Notion/GDrive adapter — anything satisfying the `WikiStorage`
    Protocol) and get back a FastMCP server with the four wiki tools
    wired in.

    For the common "I just want a local-filesystem server" case, the CLI
    `main()` does the construction itself:

        storage = LocalFilesystemStorage(wiki_root=path)
        server = build_server(storage=storage)
    """
    mcp = FastMCP(
        "llm-wiki-mcp",
        version=__version__,
        # Any exception that is NOT a ToolError becomes a generic "internal
        # error" on the client side. We always wrap WikiError → ToolError
        # below so recoverable signals still reach the LLM; unexpected
        # bugs are hidden from the network surface.
        mask_error_details=True,
    )

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        )
    )
    async def wiki_read(
        slug: Annotated[
            str,
            Field(
                description=(
                    "Kebab-case page identifier (2-64 chars, a-z 0-9 and "
                    "hyphens, must start and end with alphanumeric). "
                    "Matches the filename under `pages/` without the `.md` "
                    "extension."
                ),
            ),
        ],
    ) -> dict[str, Any]:
        """Read one wiki page — frontmatter, body, outgoing links, and etag.

        Call this when you need the full text of a specific page to answer
        a question, extend an existing page, or supply concrete context
        for another tool. Prefer `wiki_inventory` first if you don't yet
        know which page to read; it returns the whole graph without page
        bodies so you can pick targets cheaply.
        """
        try:
            page = await _wiki_read(storage, slug=slug)
        except WikiError as e:
            raise ToolError(f"{type(e).__name__}: {e}") from e
        return page.model_dump()

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=True,
            openWorldHint=False,
        )
    )
    async def wiki_write_page(
        slug: Annotated[
            str,
            Field(
                description=(
                    "Kebab-case page identifier. Creates `pages/<slug>.md` "
                    "if it does not exist; overwrites it under etag CAS "
                    "if it does."
                ),
            ),
        ],
        body: Annotated[
            str,
            Field(
                description=(
                    "Full page body as markdown, including any YAML "
                    "frontmatter block. Stored verbatim — the server does "
                    "NOT validate frontmatter shape, page type, or "
                    "category. Co-evolve those conventions in your wiki's "
                    "own `CLAUDE.md`."
                ),
            ),
        ],
        etag: Annotated[
            str | None,
            Field(
                description=(
                    "Optimistic-concurrency token from `wiki_read` or a "
                    "previous `wiki_write_page`. Required when updating an "
                    "existing page. Pass null only when creating a brand "
                    "new page — the write will fail if the slug already "
                    "exists, preventing accidental clobbers."
                ),
            ),
        ] = None,
    ) -> str:
        """Atomically create or update one wiki page. Returns the new etag.

        Call this to persist a page you have authored or edited. Use the
        etag you last read for the page to detect conflicting writes; if
        the etag has changed underfoot you will get `WikiConflictError`
        — re-read the page, merge, and retry with the fresh etag.
        """
        try:
            return await _wiki_write_page(storage, slug=slug, body=body, etag=etag)
        except WikiError as e:
            raise ToolError(f"{type(e).__name__}: {e}") from e

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        )
    )
    async def wiki_log_append(
        operation: Annotated[
            str,
            Field(
                description=(
                    "Short verb naming the kind of wiki session (e.g. "
                    "`ingest`, `query`, `lint`, `init`). Must be non-empty "
                    "and contain no whitespace, brackets, or pipes — "
                    "anything that would break the Karpathy-locked line "
                    "format."
                ),
            ),
        ],
        title: Annotated[
            str,
            Field(
                description=(
                    "Single-line human-readable description of what happened in this session."
                ),
            ),
        ],
        timestamp: Annotated[
            date_cls | None,
            Field(
                description="ISO date for the entry. Defaults to today's date if omitted.",
            ),
        ] = None,
        extra_lines: Annotated[
            list[str] | None,
            Field(
                description=(
                    "Optional follow-up lines under the entry header, "
                    "stored verbatim. Useful for brief notes about what "
                    "was read, filed, or left open."
                ),
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Append one entry to `log.md` in Karpathy's locked line format.

        Call this at the END of any wiki session (ingest/query/lint/etc.)
        to leave an audit trail of what was done. The entry header is
        always `## [YYYY-MM-DD] <operation> | <title>` — the server
        guarantees this shape so later `grep '^## \\['` still works.
        """
        try:
            entry = await _wiki_log_append(
                storage,
                operation=operation,
                title=title,
                timestamp=timestamp,
                extra_lines=extra_lines,
            )
        except WikiError as e:
            raise ToolError(f"{type(e).__name__}: {e}") from e
        return entry.model_dump()

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        )
    )
    async def wiki_inventory(
        scan_for: Annotated[
            list[str] | None,
            Field(
                description=(
                    "Optional list of plain-text terms to locate inside "
                    "page bodies. Each occurrence is returned as a "
                    "Mention(slug, line, term) — used by wiki-ingest to "
                    "audit backlinks an LLM would otherwise miss. Matches "
                    "are case-insensitive substring, not word-boundary "
                    "(safe for CJK)."
                ),
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Return the full wiki graph in one call — pages, links, log, mentions.

        Call this as the first step of almost any wiki workflow: it tells
        you which pages exist, their frontmatter, their outgoing and
        incoming links, and the full session log, without loading page
        bodies. Use `wiki_read` afterwards for the specific pages you
        actually need the body of.
        """
        try:
            inv = await _wiki_inventory(storage, scan_for=scan_for)
        except WikiError as e:
            raise ToolError(f"{type(e).__name__}: {e}") from e
        return inv.model_dump()

    return mcp


def main() -> None:
    parser = argparse.ArgumentParser(prog="llm-wiki-mcp")
    parser.add_argument(
        "--wiki-root",
        type=Path,
        required=True,
        help="Path to the local wiki root directory.",
    )
    args = parser.parse_args()

    storage = LocalFilesystemStorage(wiki_root=args.wiki_root)
    server = build_server(storage=storage)
    # show_banner=False suppresses FastMCP's startup banner. The banner
    # goes to stderr (never stdout, so it cannot corrupt JSON-RPC) but
    # it adds noise to clients that tail the server's stderr, and for a
    # tool-only server the banner's framework metadata is not useful.
    server.run(show_banner=False)


if __name__ == "__main__":
    main()
