"""GoogleDriveStorage — Drive-backed implementation of WikiStorage."""

from __future__ import annotations

from datetime import datetime

import pytest

from llm_wiki_mcp.errors import WikiNotFoundError, WikiPathError
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
