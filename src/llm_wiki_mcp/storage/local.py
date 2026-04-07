"""LocalFilesystemStorage — concrete adapter for filesystem-backed wikis.

Behavioral guarantees:

- read_page / write_page are sandboxed under wiki_root via slug.resolve_under_root
  (CVE-2025-53109 hardened).
- write_page is atomic: write to a unique tmp file, fsync, atomic rename.
- write_page enforces optimistic concurrency via etag. Writing without an
  expected_etag is allowed only when the target does not yet exist.
- append_log uses O_APPEND with a single write() call; this is atomic for
  small writes (<PIPE_BUF, ~4KB on Linux/macOS) and concurrent appends
  cannot interleave bytes within an entry.
- write_raw_file always raises WikiPermissionError. (Method exists so the
  rejection is testable, not so writes are possible.)

We deliberately do NOT define a Storage Protocol abstract base in this
plan. Concretion first; the Protocol shape gets locked when the second
backend (GoogleDriveStorage) forces it in a future plan.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import anyio

from llm_wiki_mcp.errors import (
    WikiConflictError,
    WikiNotFoundError,
    WikiPermissionError,
)
from llm_wiki_mcp.log_format import LogEntry, serialize_log_entry
from llm_wiki_mcp.slug import resolve_under_root, validate_slug
from llm_wiki_mcp.storage import PageRead

_DEFAULT_PAGE_DIR = "wiki/pages"
_DEFAULT_LOG_FILE = "wiki/log.md"
_DEFAULT_RAW_DIR = "raw"


def _compute_etag(body: bytes, mtime_ns: int) -> str:
    """Etag = first 16 hex chars of sha256(body) || `-` || mtime_ns.

    Content hash gives stability under whitespace-equivalent edits.
    mtime_ns disambiguates two writes that happen to produce identical
    bytes. Together they form a cheap, opaque CAS token.
    """
    h = hashlib.sha256(body).hexdigest()[:16]
    return f"{h}-{mtime_ns}"


class LocalFilesystemStorage:
    def __init__(
        self,
        *,
        wiki_root: Path | str,
        page_dir: str = _DEFAULT_PAGE_DIR,
        log_file: str = _DEFAULT_LOG_FILE,
        raw_dir: str = _DEFAULT_RAW_DIR,
    ) -> None:
        self.wiki_root = Path(wiki_root).resolve()
        self.page_dir = page_dir
        self.log_file = log_file
        self.raw_dir = raw_dir
        # Eagerly ensure page_dir exists; log file may be created lazily.
        (self.wiki_root / self.page_dir).mkdir(parents=True, exist_ok=True)

    # ───── Page operations ─────────────────────────────────────────

    def _page_path(self, slug: str) -> Path:
        validate_slug(slug)
        rel = f"{self.page_dir}/{slug}.md"
        return resolve_under_root(self.wiki_root, rel)

    async def read_page(self, slug: str) -> PageRead:
        """Return PageRead(body, etag, mtime) for the given slug."""
        path = self._page_path(slug)
        apath = anyio.Path(path)
        try:
            body_bytes = await apath.read_bytes()
        except FileNotFoundError as e:
            raise WikiNotFoundError(f"page not found: {slug}", slug=slug) from e
        stat = await apath.stat()
        etag = _compute_etag(body_bytes, stat.st_mtime_ns)
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
        return PageRead(body=body_bytes.decode("utf-8"), etag=etag, mtime=mtime)

    async def write_page(
        self,
        slug: str,
        body: str,
        expected_etag: str | None = None,
    ) -> str:
        """Atomic write with optimistic concurrency. Returns the new etag."""
        path = self._page_path(slug)
        body_bytes = body.encode("utf-8")
        apath = anyio.Path(path)

        try:
            current = await apath.read_bytes()
        except FileNotFoundError:
            if expected_etag is not None:
                raise WikiConflictError(
                    f"page does not exist but caller passed expected_etag for {slug}",
                    slug=slug,
                    expected_etag=expected_etag,
                    actual_etag=None,
                ) from None
        else:
            stat = await apath.stat()
            current_etag = _compute_etag(current, stat.st_mtime_ns)
            if expected_etag != current_etag:
                raise WikiConflictError(
                    f"etag mismatch for {slug}",
                    slug=slug,
                    expected_etag=expected_etag,
                    actual_etag=current_etag,
                )

        # Atomic write: tmp + fsync + rename.
        tmp = path.with_name(f"{path.name}.tmp.{uuid.uuid4().hex}")
        try:
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            try:
                os.write(fd, body_bytes)
                os.fsync(fd)
            finally:
                os.close(fd)
            tmp.replace(path)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

        stat = await anyio.Path(path).stat()
        return _compute_etag(body_bytes, stat.st_mtime_ns)

    # ───── Log operations ──────────────────────────────────────────

    def _log_path(self) -> Path:
        return resolve_under_root(self.wiki_root, self.log_file)

    async def append_log(self, entry: LogEntry) -> None:
        """O_APPEND single write. Concurrent-safe under POSIX small writes."""
        path = self._log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        serialized = serialize_log_entry(entry) + "\n\n"
        data = serialized.encode("utf-8")

        # Single os.write() under O_APPEND is atomic on POSIX for sizes
        # below PIPE_BUF (~4KB). A typical log entry is well under that.
        # If the entry exceeds PIPE_BUF, we still get correct ordering at
        # the entry-block level — concurrent writers may interleave between
        # entries but never within a single os.write call.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, data)
        finally:
            os.close(fd)

    async def read_log(self) -> str:
        path = self._log_path()
        if not path.exists():
            return ""
        return await anyio.Path(path).read_text()

    # ───── Raw layer (read-only) ───────────────────────────────────

    async def write_raw_file(self, name: str, data: bytes) -> None:
        """Always raises. raw/ is immutable per Karpathy."""
        raise WikiPermissionError(
            "writes to raw/ are not allowed; raw sources are immutable",
            target=f"{self.raw_dir}/{name}",
        )

    async def list_pages(self) -> list[str]:
        """Return all slugs present under page_dir, sorted."""
        page_dir_path = self.wiki_root / self.page_dir
        if not page_dir_path.exists():
            return []
        return sorted(p.stem for p in page_dir_path.glob("*.md") if p.is_file())
