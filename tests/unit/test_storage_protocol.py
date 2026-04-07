"""WikiStorage Protocol + PageRead NamedTuple tests.

The Protocol is the contract between tool code and any storage backend.
LocalFilesystemStorage must satisfy it; so will GoogleDriveStorage in Phase 2.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from llm_wiki_mcp.storage import PageRead, WikiStorage
from llm_wiki_mcp.storage.gdrive import GoogleDriveStorage
from llm_wiki_mcp.storage.local import LocalFilesystemStorage
from tests._fakes.drive import FakeDrive


def test_local_storage_satisfies_protocol(tmp_path: Path):
    """LocalFilesystemStorage must be a structural subtype of WikiStorage."""
    storage = LocalFilesystemStorage(wiki_root=tmp_path)
    assert isinstance(storage, WikiStorage)


def test_gdrive_storage_satisfies_protocol():
    """GoogleDriveStorage must be a structural subtype of WikiStorage."""
    drive = FakeDrive()
    wiki = drive._seed_file(name="wiki", parents=["root"], content=b"")
    pages = drive._seed_file(name="pages", parents=[wiki.id], content=b"")
    storage = GoogleDriveStorage(
        service=drive,
        wiki_folder_id=wiki.id,
        pages_folder_id=pages.id,
    )
    assert isinstance(storage, WikiStorage)


def test_page_read_is_namedtuple_with_three_fields():
    """PageRead is (body, etag, mtime). Attribute access + tuple unpacking both work."""
    pr = PageRead(body="hello", etag="abc-123", mtime=datetime(2026, 4, 7, tzinfo=UTC))
    assert pr.body == "hello"
    assert pr.etag == "abc-123"
    assert pr.mtime == datetime(2026, 4, 7, tzinfo=UTC)
    # Tuple semantics preserved
    body, etag, _mtime = pr
    assert body == "hello"
    assert etag == "abc-123"
