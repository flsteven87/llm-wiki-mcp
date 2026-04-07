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
from pathlib import Path

from llm_wiki_mcp.log_format import parse_log_entries
from llm_wiki_mcp.models import Inventory, InventoryItem, Mention
from llm_wiki_mcp.parser import parse_page
from llm_wiki_mcp.storage.local import LocalFilesystemStorage


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

    # First pass: read every page, extract frontmatter + outgoing links.
    raw: dict[str, tuple[str, dict, list[str], int, str]] = {}
    for slug in slugs:
        body_text, etag = await storage.read_page(slug)
        fm, _stripped_body, links_out = parse_page(body_text)
        body_len = len(body_text)
        raw[slug] = (body_text, fm, links_out, body_len, etag)

    # Second pass: build reverse-edge index.
    inbound: dict[str, list[str]] = {s: [] for s in slugs}
    for src_slug, (_b, _fm, links_out, _bl, _e) in raw.items():
        for tgt in links_out:
            if tgt in inbound:
                inbound[tgt].append(src_slug)

    # Build InventoryItems.
    page_dir_path = Path(storage.wiki_root) / storage.page_dir
    items: list[InventoryItem] = []
    for slug, (_b, fm, links_out, body_len, etag) in raw.items():
        stat = (page_dir_path / f"{slug}.md").stat()
        items.append(
            InventoryItem(
                slug=slug,
                frontmatter=fm,
                body_length=body_len,
                mtime=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                etag=etag,
                links_out=links_out,
                links_in=sorted(set(inbound[slug])),
            )
        )

    # Parse log entries.
    log_text = await storage.read_log()
    log_entries = parse_log_entries(log_text)

    # Optional plain-text mention scan.
    bodies = {slug: tup[0] for slug, tup in raw.items()}
    mentions = _scan_mentions(bodies, scan_for) if scan_for else []

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
