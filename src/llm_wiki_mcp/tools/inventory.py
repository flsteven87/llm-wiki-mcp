"""wiki_inventory tool — full wiki graph snapshot.

Annotations: readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False

What it returns:
- All pages with frontmatter dict, body length, mtime, etag, outgoing
  links, and computed inbound links (via reverse edge construction).
- All log entries parsed from log.md.
- Optionally: plain-text mention positions for caller-supplied search terms
  (the wiki-ingest backlink audit killer feature).

What it does NOT do:
- It does not return full bodies (memory/token cost). Use wiki_read for body.
- It does not validate frontmatter shape.
- It does not enforce link target existence (that's a lint judgment).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, NamedTuple

import anyio

from llm_wiki_mcp.log_format import parse_log_entries
from llm_wiki_mcp.models import Inventory, InventoryItem, Mention
from llm_wiki_mcp.parser import parse_page
from llm_wiki_mcp.storage.local import LocalFilesystemStorage


class _RawPage(NamedTuple):
    body: str
    frontmatter: dict[str, Any]
    links_out: list[str]
    etag: str


async def wiki_inventory(
    storage: LocalFilesystemStorage,
    *,
    scan_for: list[str] | None = None,
) -> Inventory:
    """Snapshot the wiki. One call replaces walking + parsing N files.

    `scan_for` is a list of plain-text terms to locate in page bodies.
    Returns Mention(slug, line, term) tuples for each occurrence. Used by
    wiki-ingest's backlink audit step.
    """
    slugs = await storage.list_pages()

    raw: dict[str, _RawPage] = {}
    for slug in slugs:
        body_text, etag = await storage.read_page(slug)
        fm, _stripped, links_out = parse_page(body_text)
        raw[slug] = _RawPage(body_text, fm, links_out, etag)

    inbound: dict[str, list[str]] = {s: [] for s in slugs}
    for src_slug, page in raw.items():
        for tgt in page.links_out:
            if tgt in inbound:
                inbound[tgt].append(src_slug)

    # NOTE: reaches into storage.wiki_root/page_dir for mtime — layer leak
    # to be cleaned up when the Storage Protocol is extracted in Phase 2
    # (read_page should return mtime alongside etag).
    page_dir_path = storage.wiki_root / storage.page_dir
    items: list[InventoryItem] = []
    for slug, page in raw.items():
        stat = await anyio.Path(page_dir_path / f"{slug}.md").stat()
        items.append(
            InventoryItem(
                slug=slug,
                frontmatter=page.frontmatter,
                body_length=len(page.body),
                mtime=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                etag=page.etag,
                links_out=page.links_out,
                links_in=sorted(set(inbound[slug])),
            )
        )

    log_entries = parse_log_entries(await storage.read_log())

    mentions = _scan_mentions({s: p.body for s, p in raw.items()}, scan_for) if scan_for else []

    return Inventory(
        pages=sorted(items, key=lambda i: i.slug),
        log_entries=log_entries,
        mentions=mentions,
    )


def _scan_mentions(bodies: dict[str, str], terms: list[str]) -> list[Mention]:
    """Word-boundary, case-insensitive plain-text scan over page bodies."""
    compiled = [(term, re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)) for term in terms]
    mentions: list[Mention] = []
    for slug, body_text in bodies.items():
        for line_no, line in enumerate(body_text.splitlines(), start=1):
            for term, pat in compiled:
                if pat.search(line):
                    mentions.append(Mention(slug=slug, line=line_no, term=term))
    return mentions
