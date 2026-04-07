"""LocalFilesystemStorage adapter tests.

Behavioral invariants under test:
- atomic write (no partial files visible)
- etag changes on every write, etag is content-stable
- raw/ writes are rejected with WikiPermissionError
- log appends are real O_APPEND (concurrent appends interleave entry-wise)
- read of missing file → WikiNotFoundError
- write with stale etag → WikiConflictError
- path containment via slug.resolve_under_root (covered by security suite)
"""

from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path

import pytest

from llm_wiki_mcp.errors import (
    WikiConflictError,
    WikiNotFoundError,
    WikiPermissionError,
)
from llm_wiki_mcp.log_format import LogEntry
from llm_wiki_mcp.storage.local import LocalFilesystemStorage


@pytest.fixture
def wiki(tmp_path: Path) -> Path:
    root = tmp_path / "wiki-root"
    root.mkdir()
    (root / "raw").mkdir()
    (root / "wiki").mkdir()
    (root / "wiki" / "log.md").write_text("# Log\n")
    (root / "wiki" / "index.md").write_text("# Index\n")
    return root


@pytest.fixture
def storage(wiki: Path) -> LocalFilesystemStorage:
    return LocalFilesystemStorage(wiki_root=wiki)


async def test_write_then_read_round_trip(storage: LocalFilesystemStorage):
    new_etag = await storage.write_page("hello", "# Hello\n")
    body, etag = await storage.read_page("hello")
    assert body == "# Hello\n"
    assert etag == new_etag


async def test_etag_changes_on_each_write(storage: LocalFilesystemStorage):
    e1 = await storage.write_page("pg", "v1")
    e2 = await storage.write_page("pg", "v2", expected_etag=e1)
    assert e1 != e2


async def test_stale_etag_rejected(storage: LocalFilesystemStorage):
    e1 = await storage.write_page("pg", "v1")
    await storage.write_page("pg", "v2", expected_etag=e1)
    with pytest.raises(WikiConflictError):
        await storage.write_page("pg", "v3", expected_etag=e1)


async def test_no_etag_allows_create_only(storage: LocalFilesystemStorage):
    """Calling write_page with expected_etag=None on an existing page must fail.

    Why: the only safe semantics for "no etag provided" is "I'm creating a
    new page and assert it doesn't exist yet". Otherwise we'd silently
    clobber concurrent edits, which is the entire bug class etag exists to
    prevent.
    """
    await storage.write_page("pg", "v1")
    with pytest.raises(WikiConflictError):
        await storage.write_page("pg", "v2")  # no etag, but page exists


async def test_read_missing_page_raises(storage: LocalFilesystemStorage):
    with pytest.raises(WikiNotFoundError):
        await storage.read_page("nope")


async def test_raw_write_rejected(wiki: Path):
    """Storage configured with raw_dir='raw' must reject any write into it.

    Karpathy: "Raw sources... are immutable — the LLM reads from them but
    never modifies them."
    """
    storage = LocalFilesystemStorage(wiki_root=wiki, raw_dir="raw")
    with pytest.raises(WikiPermissionError):
        await storage.write_raw_file("source.pdf", b"...")


async def test_log_append_atomic(storage: LocalFilesystemStorage):
    e1 = LogEntry(timestamp=date(2026, 4, 1), operation="ingest", title="A")
    e2 = LogEntry(timestamp=date(2026, 4, 2), operation="lint", title="B")
    await storage.append_log(e1)
    await storage.append_log(e2)

    text = await storage.read_log()
    assert "ingest | A" in text
    assert "lint | B" in text
    assert text.index("ingest | A") < text.index("lint | B")


async def test_concurrent_log_appends_do_not_lose_entries(
    storage: LocalFilesystemStorage,
):
    """O_APPEND guarantees: N concurrent appends → N entries visible.

    A naive read-modify-write implementation would lose entries here. This
    test exists to make sure we never regress to that.
    """
    entries = [
        LogEntry(timestamp=date(2026, 4, 7), operation=f"op{i}", title=f"t{i}") for i in range(20)
    ]
    await asyncio.gather(*(storage.append_log(e) for e in entries))
    text = await storage.read_log()
    for i in range(20):
        assert f"op{i} | t{i}" in text


async def test_atomic_write_no_partial_file(storage: LocalFilesystemStorage, wiki: Path):
    """If a write crashes mid-flight, the original file remains intact.

    We can't easily inject a crash, so we instead assert that the temp file
    used during write does not survive a successful write (i.e. we use
    rename, not copy-then-delete).
    """
    await storage.write_page("pg", "v1")
    e1 = await storage.read_page("pg")
    await storage.write_page("pg", "v2-much-longer-content", expected_etag=e1[1])
    # Walk the page dir; nothing should match *.tmp.*
    page_dir = wiki / "wiki" / "pages"
    leftovers = list(page_dir.glob("*.tmp.*"))
    assert leftovers == []
