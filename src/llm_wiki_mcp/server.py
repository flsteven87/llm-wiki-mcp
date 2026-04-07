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
from llm_wiki_mcp.storage.gdrive import GoogleDriveStorage
from llm_wiki_mcp.storage.local import LocalFilesystemStorage
from llm_wiki_mcp.tools.inventory import wiki_inventory as _wiki_inventory
from llm_wiki_mcp.tools.log_append import wiki_log_append as _wiki_log_append
from llm_wiki_mcp.tools.read import wiki_read as _wiki_read
from llm_wiki_mcp.tools.write_page import wiki_write_page as _wiki_write_page


def build_server(
    *,
    wiki_root: Path | None = None,
    gdrive_service: Any = None,
    gdrive_root_folder_id: str | None = None,
) -> FastMCP:
    """Construct a FastMCP server bound to either a Local or GDrive backend.

    Exactly one backend must be specified:
      - Local:  pass `wiki_root`
      - GDrive: pass both `gdrive_service` and `gdrive_root_folder_id`
    """
    any_local = wiki_root is not None
    any_gdrive = gdrive_service is not None or gdrive_root_folder_id is not None
    if any_local == any_gdrive:
        raise ValueError(
            "build_server requires exactly one backend: wiki_root OR "
            "(gdrive_service + gdrive_root_folder_id)"
        )

    storage: WikiStorage
    if any_local:
        storage = LocalFilesystemStorage(wiki_root=wiki_root)
    else:
        if gdrive_service is None or gdrive_root_folder_id is None:
            raise ValueError(
                "GDrive backend requires both gdrive_service and gdrive_root_folder_id"
            )
        storage = GoogleDriveStorage.from_root_folder(
            service=gdrive_service,
            root_folder_id=gdrive_root_folder_id,
        )

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
        """Append an entry to wiki/log.md in Karpathy's format-locked line shape."""
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


def main() -> None:
    parser = argparse.ArgumentParser(prog="llm-wiki-mcp")
    backend_group = parser.add_mutually_exclusive_group(required=True)
    backend_group.add_argument(
        "--wiki-root",
        type=Path,
        help="Path to the local wiki root directory (Local backend).",
    )
    backend_group.add_argument(
        "--gdrive-root-folder",
        type=str,
        help=(
            "Google Drive folder id for the wiki root (GDrive backend). "
            "The folder must contain a 'wiki/pages/' subfolder shared with "
            "the service account."
        ),
    )
    parser.add_argument(
        "--gdrive-credentials",
        type=Path,
        help="Path to a Google service account JSON key (required with --gdrive-root-folder).",
    )
    args = parser.parse_args()

    if args.wiki_root is not None:
        server = build_server(wiki_root=args.wiki_root)
    else:
        if args.gdrive_credentials is None:
            parser.error("--gdrive-credentials is required when using --gdrive-root-folder")
        from google.oauth2 import service_account
        from googleapiclient.discovery import build as build_drive

        creds = service_account.Credentials.from_service_account_file(
            str(args.gdrive_credentials),
            scopes=["https://www.googleapis.com/auth/drive"],
        )
        drive_service = build_drive("drive", "v3", credentials=creds, cache_discovery=False)
        server = build_server(
            gdrive_service=drive_service,
            gdrive_root_folder_id=args.gdrive_root_folder,
        )

    server.run()  # FastMCP defaults to stdio transport


if __name__ == "__main__":
    main()
