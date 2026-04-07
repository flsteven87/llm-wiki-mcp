"""wiki_inventory tool — full graph snapshot in one call.

This is the lint and backlink-audit killer feature. Replaces N file reads
+ LLM parsing with a single deterministic call.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_wiki_mcp.storage.local import LocalFilesystemStorage
from llm_wiki_mcp.tools.inventory import wiki_inventory
from llm_wiki_mcp.tools.log_append import wiki_log_append
from llm_wiki_mcp.tools.write_page import wiki_write_page


@pytest.fixture
async def populated(tmp_path: Path) -> LocalFilesystemStorage:
    root = tmp_path / "wiki-root"
    root.mkdir()
    storage = LocalFilesystemStorage(wiki_root=root)

    await wiki_write_page(
        storage,
        slug="transformer",
        body=(
            "---\n"
            "title: Transformer\n"
            "tags: [model, paper]\n"
            "---\n"
            "Introduced in [[attention-is-all-you-need]]. Uses [[self-attention]].\n"
        ),
    )
    await wiki_write_page(
        storage,
        slug="self-attention",
        body=("---\ntitle: Self-attention\n---\nMechanism used by the [[transformer]].\n"),
    )
    await wiki_write_page(
        storage,
        slug="orphan-page",
        body="---\ntitle: Lonely\n---\nNo links in or out.\n",
    )
    await wiki_log_append(
        storage,
        operation="ingest",
        title="Transformer paper",
    )
    return storage


async def test_inventory_returns_all_pages(populated: LocalFilesystemStorage):
    inv = await wiki_inventory(populated)
    slugs = {p.slug for p in inv.pages}
    assert slugs == {"transformer", "self-attention", "orphan-page"}


async def test_inventory_computes_inbound_links(populated: LocalFilesystemStorage):
    inv = await wiki_inventory(populated)
    by_slug = {p.slug: p for p in inv.pages}

    # transformer is linked from self-attention
    assert "self-attention" in by_slug["transformer"].links_in
    # self-attention is linked from transformer
    assert "transformer" in by_slug["self-attention"].links_in
    # orphan has no inbound
    assert by_slug["orphan-page"].links_in == []


async def test_inventory_links_out_match_extracted(
    populated: LocalFilesystemStorage,
):
    inv = await wiki_inventory(populated)
    by_slug = {p.slug: p for p in inv.pages}
    assert set(by_slug["transformer"].links_out) == {
        "attention-is-all-you-need",
        "self-attention",
    }


async def test_inventory_includes_log_entries(populated: LocalFilesystemStorage):
    inv = await wiki_inventory(populated)
    assert len(inv.log_entries) == 1
    assert inv.log_entries[0].operation == "ingest"


async def test_inventory_scan_for_finds_mentions(
    populated: LocalFilesystemStorage,
):
    """The killer wiki-ingest step 7 use case: find pages that mention an
    entity in plain text without yet linking to it."""
    inv = await wiki_inventory(populated, scan_for=["mechanism"])
    found = {(m.slug, m.term) for m in inv.mentions}
    assert ("self-attention", "mechanism") in found


async def test_inventory_scan_for_is_case_insensitive(
    populated: LocalFilesystemStorage,
):
    inv = await wiki_inventory(populated, scan_for=["TRANSFORMER"])
    slugs = {m.slug for m in inv.mentions}
    # transformer mention appears in self-attention's body
    assert "self-attention" in slugs


async def test_inventory_no_scan_returns_empty_mentions(
    populated: LocalFilesystemStorage,
):
    inv = await wiki_inventory(populated)
    assert inv.mentions == []
