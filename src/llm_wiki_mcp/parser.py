"""Markdown parser: frontmatter pass-through and Obsidian wikilink extraction.

Frontmatter is YAML, parsed into a plain dict and returned unchanged. We
never enforce schema on the dict — that's the user's per-domain choice and
lives in their wiki/CLAUDE.md, not in MCP.

Link extraction is currently Obsidian-only ([[slug]] and [[slug|alias]]).
Multi-syntax detection (Markdown []()) is intentionally deferred until a
real user needs it; YAGNI.
"""

from __future__ import annotations

import re
from typing import Any

import frontmatter

from llm_wiki_mcp.slug import is_valid_slug

# [[ slug ]] or [[ slug | alias ]] — capture the slug only.
_LINK_RE = re.compile(r"\[\[([^\[\]|]+?)(?:\|[^\[\]]*)?\]\]")


def parse_page(text: str) -> tuple[dict[str, Any], str, list[str]]:
    """Split a page into (frontmatter, body, outgoing_links).

    `frontmatter` is the raw parsed YAML dict, unchanged. Empty if no
    frontmatter block. `body` is everything after the frontmatter block (or
    the full text if no frontmatter). `outgoing_links` is the dedup-in-order
    list of valid slugs found inside [[...]].
    """
    post = frontmatter.loads(text)
    fm: dict[str, Any] = dict(post.metadata)
    body: str = post.content
    return fm, body, extract_links(body)


def extract_links(body: str) -> list[str]:
    """Return unique-in-order list of slugs found in [[wikilinks]].

    Items that don't pass slug regex are silently dropped (they're probably
    not real link targets).
    """
    seen: set[str] = set()
    out: list[str] = []
    for m in _LINK_RE.finditer(body):
        candidate = m.group(1).strip()
        if not is_valid_slug(candidate):
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        out.append(candidate)
    return out
