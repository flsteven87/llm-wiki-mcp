"""wiki_write_page tool — atomic write with etag CAS."""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_wiki_mcp.errors import WikiConflictError, WikiPathError
from llm_wiki_mcp.storage.local import LocalFilesystemStorage
from llm_wiki_mcp.tools.read import wiki_read
from llm_wiki_mcp.tools.write_page import wiki_write_page


@pytest.fixture
def storage(tmp_path: Path) -> LocalFilesystemStorage:
    root = tmp_path / "wiki-root"
    root.mkdir()
    return LocalFilesystemStorage(wiki_root=root)


async def test_write_new_page(storage: LocalFilesystemStorage):
    new_etag = await wiki_write_page(storage, slug="my-page", body="# Hi\n")
    assert new_etag

    page = await wiki_read(storage, slug="my-page")
    assert "# Hi" in page.body


async def test_write_with_correct_etag_succeeds(storage: LocalFilesystemStorage):
    await wiki_write_page(storage, slug="pg", body="v1")
    page = await wiki_read(storage, slug="pg")
    new_etag = await wiki_write_page(storage, slug="pg", body="v2", etag=page.etag)
    assert new_etag != page.etag


async def test_write_with_stale_etag_fails(storage: LocalFilesystemStorage):
    await wiki_write_page(storage, slug="pg", body="v1")
    page = await wiki_read(storage, slug="pg")
    await wiki_write_page(storage, slug="pg", body="v2", etag=page.etag)
    with pytest.raises(WikiConflictError):
        await wiki_write_page(storage, slug="pg", body="v3", etag=page.etag)


async def test_write_invalid_slug_rejected(storage: LocalFilesystemStorage):
    with pytest.raises(WikiPathError):
        await wiki_write_page(storage, slug="../escape", body="x")
