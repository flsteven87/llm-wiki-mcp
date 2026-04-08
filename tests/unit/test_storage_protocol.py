"""WikiStorage Protocol + PageRead NamedTuple tests.

The Protocol is the contract between tool code and any storage backend.
Today LocalFilesystemStorage is the only implementor.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from llm_wiki_mcp.storage import PageRead, WikiStorage
from llm_wiki_mcp.storage.local import LocalFilesystemStorage


def test_local_storage_satisfies_protocol(tmp_path: Path):
    """LocalFilesystemStorage must be a structural subtype of WikiStorage."""
    storage = LocalFilesystemStorage(wiki_root=tmp_path)
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
