"""wiki_read tool — single-page read returning Page model.

Annotations: readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
"""

from __future__ import annotations

from llm_wiki_mcp.models import Page
from llm_wiki_mcp.parser import parse_page
from llm_wiki_mcp.storage.local import LocalFilesystemStorage


async def wiki_read(storage: LocalFilesystemStorage, *, slug: str) -> Page:
    """Read one page; return parsed frontmatter, body, links, and etag."""
    raw_text, etag = await storage.read_page(slug)
    fm, _stripped_body, links = parse_page(raw_text)
    return Page(
        slug=slug,
        body=raw_text,  # full original including frontmatter, for round-trip writes
        etag=etag,
        frontmatter=fm,
        links_out=links,
    )
