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


async def test_inventory_scan_for_matches_cjk_term_embedded_in_cjk_prose(
    tmp_path: Path,
):
    """Regression: Phase G.2 dogfood discovered that scan_for under-reports
    CJK mentions when the term is surrounded by other CJK characters.

    Root cause: `re.compile(rf"\\b{term}\\b", re.IGNORECASE)` uses word
    boundaries. Python's Unicode regex treats CJK characters as word chars
    (\\w), so `\\b載板\\b` can only match when 載板 is preceded/followed by
    non-word chars (punctuation, whitespace, ASCII). Inside continuous CJK
    prose like "與載板設備" or "與載板。" the boundary doesn't fire and the
    mention is silently dropped.

    This broke the backlink-audit "killer feature" on zh-tw / zh-cn / ja
    / ko wikis in practice.
    """
    root = tmp_path / "wiki-root"
    root.mkdir()
    storage = LocalFilesystemStorage(wiki_root=root)

    await wiki_write_page(
        storage,
        slug="zhen-ding",
        body=(
            "---\ntitle: 臻鼎-KY\n---\n同時布局 AI 伺服器與載板設備，載板業務是第二條腿。\n"  # noqa: RUF001
        ),
    )

    inv = await wiki_inventory(storage, scan_for=["載板"])
    hits = [m for m in inv.mentions if m.slug == "zhen-ding" and m.term == "載板"]
    assert len(hits) >= 1, f"Expected 載板 mention on zhen-ding, got: {inv.mentions}"


async def test_inventory_scan_for_matches_ascii_term_without_word_boundary(
    tmp_path: Path,
):
    """Complement to the CJK fix: ensure ASCII terms still match when
    embedded in CJK (which they always were, pre-fix) AND when embedded
    mid-word (which they weren't, pre-fix — but that's fine for mention
    discovery; partial matches are the desired semantics here).
    """
    root = tmp_path / "wiki-root"
    root.mkdir()
    storage = LocalFilesystemStorage(wiki_root=root)

    await wiki_write_page(
        storage,
        slug="optical",
        body="---\ntitle: Optical\n---\n800G 與 1.6T 光模組於 2026 年量產。\n",
    )

    inv = await wiki_inventory(storage, scan_for=["800G", "1.6T"])
    terms = {m.term for m in inv.mentions if m.slug == "optical"}
    assert terms == {"800G", "1.6T"}
