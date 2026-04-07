"""wiki_read tool — single-page read with frontmatter parse + link extract."""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_wiki_mcp.errors import WikiNotFoundError
from llm_wiki_mcp.storage.local import LocalFilesystemStorage
from llm_wiki_mcp.tools.read import wiki_read


@pytest.fixture
def storage_with_page(tmp_path: Path) -> LocalFilesystemStorage:
    root = tmp_path / "wiki-root"
    root.mkdir()
    (root / "wiki" / "pages").mkdir(parents=True)
    (root / "wiki" / "pages" / "hello.md").write_text(
        "---\ntitle: Hello\ntags: [greet]\n---\nBody with [[other-page]] link.\n"
    )
    return LocalFilesystemStorage(wiki_root=root)


async def test_read_returns_page_with_frontmatter_and_links(
    storage_with_page: LocalFilesystemStorage,
):
    page = await wiki_read(storage_with_page, slug="hello")
    assert page.slug == "hello"
    assert page.frontmatter == {"title": "Hello", "tags": ["greet"]}
    assert page.links_out == ["other-page"]
    assert "Body with" in page.body
    assert page.etag  # non-empty


async def test_read_missing_page_raises(storage_with_page: LocalFilesystemStorage):
    with pytest.raises(WikiNotFoundError):
        await wiki_read(storage_with_page, slug="nope")
