"""GoogleDriveStorage — Drive-backed implementation of WikiStorage."""

from __future__ import annotations

import asyncio
from datetime import date, datetime

import pytest

from llm_wiki_mcp.errors import WikiConflictError, WikiNotFoundError, WikiPathError
from llm_wiki_mcp.log_format import LogEntry
from llm_wiki_mcp.storage.gdrive import GoogleDriveStorage
from tests._fakes.drive import FakeDrive


def _make_storage_with_folders(drive: FakeDrive) -> GoogleDriveStorage:
    """Helper: seed wiki/pages folder structure and return a storage bound to it."""
    wiki = drive._seed_file(name="wiki", parents=["root"], content=b"")
    pages = drive._seed_file(name="pages", parents=[wiki.id], content=b"")
    return GoogleDriveStorage(
        service=drive,
        wiki_folder_id=wiki.id,
        pages_folder_id=pages.id,
    )


def test_from_root_folder_resolves_wiki_and_pages():
    drive = FakeDrive()
    wiki = drive._seed_file(name="wiki", parents=["root123"], content=b"")
    drive._seed_file(name="pages", parents=[wiki.id], content=b"")

    storage = GoogleDriveStorage.from_root_folder(service=drive, root_folder_id="root123")
    assert storage._wiki_folder_id == wiki.id


def test_from_root_folder_raises_if_wiki_missing():
    drive = FakeDrive()
    with pytest.raises(WikiNotFoundError, match="wiki"):
        GoogleDriveStorage.from_root_folder(service=drive, root_folder_id="root123")


def test_from_root_folder_raises_if_pages_missing():
    drive = FakeDrive()
    drive._seed_file(name="wiki", parents=["root123"], content=b"")
    with pytest.raises(WikiNotFoundError, match="pages"):
        GoogleDriveStorage.from_root_folder(service=drive, root_folder_id="root123")


async def test_read_page_returns_pageread_with_body_etag_mtime():
    drive = FakeDrive()
    storage = _make_storage_with_folders(drive)
    drive._seed_file(
        name="transformer.md",
        parents=[storage._pages_folder_id],
        content=b"# Transformer\n",
    )

    page = await storage.read_page("transformer")
    assert page.body == "# Transformer\n"
    assert page.etag.startswith("rev")  # FakeDrive uses revN
    assert isinstance(page.mtime, datetime)
    assert page.mtime.tzinfo is not None


async def test_read_page_missing_raises():
    drive = FakeDrive()
    storage = _make_storage_with_folders(drive)
    with pytest.raises(WikiNotFoundError):
        await storage.read_page("nope")


async def test_read_page_validates_slug():
    drive = FakeDrive()
    storage = _make_storage_with_folders(drive)
    with pytest.raises(WikiPathError):
        await storage.read_page("Bad Slug!")


async def test_list_pages_returns_sorted_slugs():
    drive = FakeDrive()
    storage = _make_storage_with_folders(drive)
    for name in ["banana.md", "apple.md", "cherry.md"]:
        drive._seed_file(name=name, parents=[storage._pages_folder_id], content=b"")

    slugs = await storage.list_pages()
    assert slugs == ["apple", "banana", "cherry"]


async def test_list_pages_empty_when_no_files():
    drive = FakeDrive()
    storage = _make_storage_with_folders(drive)
    assert await storage.list_pages() == []


async def test_list_pages_ignores_non_md_files():
    drive = FakeDrive()
    storage = _make_storage_with_folders(drive)
    drive._seed_file(name="page.md", parents=[storage._pages_folder_id], content=b"")
    drive._seed_file(name="notes.txt", parents=[storage._pages_folder_id], content=b"")

    assert await storage.list_pages() == ["page"]


async def test_write_page_creates_new_file_when_no_etag_and_missing():
    drive = FakeDrive()
    storage = _make_storage_with_folders(drive)
    new_etag = await storage.write_page("hello", "# Hello\n")
    page = await storage.read_page("hello")
    assert page.body == "# Hello\n"
    assert page.etag == new_etag


async def test_write_page_no_etag_existing_file_raises_conflict():
    drive = FakeDrive()
    storage = _make_storage_with_folders(drive)
    await storage.write_page("hello", "# Hello\n")
    with pytest.raises(WikiConflictError):
        await storage.write_page("hello", "# Goodbye\n")


async def test_write_page_with_correct_etag_updates():
    drive = FakeDrive()
    storage = _make_storage_with_folders(drive)
    e1 = await storage.write_page("pg", "v1")
    e2 = await storage.write_page("pg", "v2", expected_etag=e1)
    assert e1 != e2
    page = await storage.read_page("pg")
    assert page.body == "v2"
    assert page.etag == e2


async def test_write_page_with_stale_etag_raises():
    drive = FakeDrive()
    storage = _make_storage_with_folders(drive)
    e1 = await storage.write_page("pg", "v1")
    await storage.write_page("pg", "v2", expected_etag=e1)
    with pytest.raises(WikiConflictError):
        await storage.write_page("pg", "v3", expected_etag=e1)


async def test_write_page_etag_for_missing_file_raises():
    drive = FakeDrive()
    storage = _make_storage_with_folders(drive)
    with pytest.raises(WikiConflictError):
        await storage.write_page("nope", "x", expected_etag="rev1")


async def test_read_log_empty_when_missing():
    drive = FakeDrive()
    storage = _make_storage_with_folders(drive)
    assert await storage.read_log() == ""


async def test_append_log_creates_file_on_first_call():
    drive = FakeDrive()
    storage = _make_storage_with_folders(drive)
    entry = LogEntry(timestamp=date(2026, 4, 7), operation="ingest", title="A")
    await storage.append_log(entry)
    text = await storage.read_log()
    assert "ingest | A" in text


async def test_append_log_appends_to_existing_file():
    drive = FakeDrive()
    storage = _make_storage_with_folders(drive)
    e1 = LogEntry(timestamp=date(2026, 4, 7), operation="ingest", title="A")
    e2 = LogEntry(timestamp=date(2026, 4, 8), operation="lint", title="B")
    await storage.append_log(e1)
    await storage.append_log(e2)
    text = await storage.read_log()
    assert text.index("ingest | A") < text.index("lint | B")


async def test_concurrent_appends_serialized_by_lock():
    """20 concurrent appends → 20 entries visible, no losses.

    The asyncio.Lock guarantees this even though Drive has no native
    atomic append. Cross-process safety is explicitly out of scope.
    """
    drive = FakeDrive()
    storage = _make_storage_with_folders(drive)
    entries = [
        LogEntry(timestamp=date(2026, 4, 7), operation=f"op{i}", title=f"t{i}") for i in range(20)
    ]
    await asyncio.gather(*(storage.append_log(e) for e in entries))
    text = await storage.read_log()
    for i in range(20):
        assert f"op{i} | t{i}" in text
