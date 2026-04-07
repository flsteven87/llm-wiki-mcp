"""MCP-facing domain models.

Deliberately minimal. The cardinal rule (the North Star of this project):
**MCP enforces behaviors, not schemas.** So:

- `frontmatter` is `dict[str, Any]` — we parse YAML and pass it through.
- `links_out` is a list of slug strings — we extract via regex but don't
  validate that they resolve to real pages (that's a lint concern).
- There is NO `page_type` enum, NO `category` enum, NO required frontmatter
  fields. Karpathy is explicit these are per-domain co-evolved choices.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from llm_wiki_mcp.log_format import LogEntry


class Page(BaseModel):
    """A single wiki page as returned by wiki_read."""

    model_config = ConfigDict(frozen=True)

    slug: str
    body: str
    etag: str
    frontmatter: dict[str, Any]
    links_out: list[str]


class InventoryItem(BaseModel):
    """One row in the wiki inventory."""

    model_config = ConfigDict(frozen=True)

    slug: str
    frontmatter: dict[str, Any]
    body_length: int
    mtime: datetime
    etag: str
    links_out: list[str]
    links_in: list[str]


class Mention(BaseModel):
    """A plain-text mention of a search term inside a page body.

    Returned by wiki_inventory(scan_for=...) so wiki-ingest can do the
    backlink audit Karpathy points out LLMs always skip.
    """

    model_config = ConfigDict(frozen=True)

    slug: str
    line: int
    term: str


class Inventory(BaseModel):
    """Full wiki snapshot. One call replaces N file reads + parsing."""

    model_config = ConfigDict(frozen=True)

    pages: list[InventoryItem]
    log_entries: list[LogEntry]
    mentions: list[Mention] = []
