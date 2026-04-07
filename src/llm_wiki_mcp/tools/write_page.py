"""wiki_write_page tool — atomic page write with etag CAS.

Annotations: readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False

Note on idempotency: with a correct etag, this is idempotent (CAS). Without
an etag, repeated calls would each fail with WikiConflictError after the
first succeeds — also effectively idempotent.

This tool does NOT validate frontmatter, page type, or category. The body
is whatever the LLM produces, including any frontmatter block. Per the
North Star: behaviors not schemas.
"""

from __future__ import annotations

from llm_wiki_mcp.storage.local import LocalFilesystemStorage


async def wiki_write_page(
    storage: LocalFilesystemStorage,
    *,
    slug: str,
    body: str,
    etag: str | None = None,
) -> str:
    """Atomic page write. Returns the new etag.

    `etag` semantics:
    - None: assert the page does not exist; fails if it does (anti-clobber).
    - str: must match the current etag; fails otherwise (CAS for updates).
    """
    return await storage.write_page(slug, body, expected_etag=etag)
