"""Storage package — WikiStorage Protocol + PageRead return type.

The Protocol defines the contract that any storage backend must satisfy
in order to back the 4 MCP tools. LocalFilesystemStorage is the first
implementor; GoogleDriveStorage will follow in Phase 2B.

Design notes:

- Only methods actually called by the tools appear here. No getters for
  wiki_root / page_dir — those are implementation detail of Local and
  must NOT leak into tool code (this was the inventory layer-leak bug).
- read_page returns PageRead so callers never have to stat() files to
  get mtime. Inventory needs mtime for its snapshot; read_page is the
  single authoritative source.
- etag is an opaque string. Local uses sha256-prefix + mtime_ns; GDrive
  will use revisionId. Callers treat it as an opaque CAS token.
- write_raw_file is part of the Protocol even though every backend is
  expected to refuse it — its presence in the interface makes "raw is
  immutable" a first-class contract rather than a Local quirk.
"""

from __future__ import annotations

from datetime import datetime
from typing import NamedTuple, Protocol, runtime_checkable

from llm_wiki_mcp.log_format import LogEntry


class PageRead(NamedTuple):
    """Return value of WikiStorage.read_page.

    body: full page text including any frontmatter block (round-trippable).
    etag: opaque CAS token; backend-defined shape.
    mtime: last modification time, timezone-aware UTC.
    """

    body: str
    etag: str
    mtime: datetime


@runtime_checkable
class WikiStorage(Protocol):
    """The contract every storage backend implements for the 4 MCP tools."""

    async def read_page(self, slug: str) -> PageRead: ...

    async def write_page(
        self,
        slug: str,
        body: str,
        expected_etag: str | None = None,
    ) -> str: ...

    async def list_pages(self) -> list[str]: ...

    async def append_log(self, entry: LogEntry) -> None: ...

    async def read_log(self) -> str: ...

    async def write_raw_file(self, name: str, data: bytes) -> None: ...
