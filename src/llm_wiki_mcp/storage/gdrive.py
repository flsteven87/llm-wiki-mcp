"""GoogleDriveStorage — WikiStorage Protocol implementation backed by Drive.

Auth model: service account. The caller constructs a googleapiclient
service via `googleapiclient.discovery.build("drive", "v3", credentials=...)`
where the credentials come from `google.oauth2.service_account`. The user
shares the root wiki folder with the service account email.

Folder layout (mirrors Local):
    <root_folder_id>/wiki/pages/<slug>.md
    <root_folder_id>/wiki/log.md

Init (synchronous, one-shot at server startup):
- `from_root_folder` resolves the `wiki` then `pages` subfolders by name.
- Both must already exist; we do NOT auto-create.

Per-request methods:
- All Drive calls are wrapped in `await anyio.to_thread.run_sync(...)` so
  the async Protocol is honored without blocking the event loop.

Concurrency:
- An instance-scoped `asyncio.Lock` serializes log appends within a single
  MCP server process. Cross-process concurrent appends are not supported.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import anyio
from googleapiclient.http import MediaInMemoryUpload

from llm_wiki_mcp.errors import (
    WikiConflictError,
    WikiNotFoundError,
    WikiPermissionError,
)
from llm_wiki_mcp.log_format import LogEntry, serialize_log_entry
from llm_wiki_mcp.slug import validate_slug
from llm_wiki_mcp.storage import PageRead

_WIKI_FOLDER_NAME = "wiki"
_PAGES_FOLDER_NAME = "pages"
_LOG_FILE_NAME = "log.md"
_PAGE_SUFFIX = ".md"
_MARKDOWN_MIME = "text/markdown"
_PAGE_FIELDS = "files(id,name,headRevisionId,modifiedTime)"
_NAME_ONLY_FIELDS = "files(id,name)"


class GoogleDriveStorage:
    def __init__(
        self,
        *,
        service: Any,
        wiki_folder_id: str,
        pages_folder_id: str,
    ) -> None:
        self._service = service
        self._wiki_folder_id = wiki_folder_id
        self._pages_folder_id = pages_folder_id
        self._log_lock = asyncio.Lock()
        self._log_file_id: str | None = None  # cached after first resolve/create

    @classmethod
    def from_root_folder(
        cls,
        *,
        service: Any,
        root_folder_id: str,
    ) -> GoogleDriveStorage:
        """Resolve wiki/pages under root_folder_id; raise if either is missing.

        Phase 2B does not auto-create folders — surfaces user setup mistakes
        loudly instead of leaking phantom hierarchies.
        """
        wiki_meta = _find_unique_child(
            service,
            parent_id=root_folder_id,
            name=_WIKI_FOLDER_NAME,
            fields=_NAME_ONLY_FIELDS,
        )
        if wiki_meta is None:
            raise WikiNotFoundError(
                f"no {_WIKI_FOLDER_NAME!r} folder under root {root_folder_id}",
                slug=_WIKI_FOLDER_NAME,
            )
        pages_meta = _find_unique_child(
            service,
            parent_id=wiki_meta["id"],
            name=_PAGES_FOLDER_NAME,
            fields=_NAME_ONLY_FIELDS,
        )
        if pages_meta is None:
            raise WikiNotFoundError(
                f"no {_PAGES_FOLDER_NAME!r} folder under wiki {wiki_meta['id']}",
                slug=_PAGES_FOLDER_NAME,
            )
        return cls(
            service=service,
            wiki_folder_id=wiki_meta["id"],
            pages_folder_id=pages_meta["id"],
        )

    # ───── Page operations ─────────────────────────────────────────

    async def read_page(self, slug: str) -> PageRead:
        """Find <slug>.md under pages_folder_id and return PageRead."""
        validate_slug(slug)
        meta = await anyio.to_thread.run_sync(self._find_page_metadata_sync, slug)
        if meta is None:
            raise WikiNotFoundError(f"page not found: {slug}", slug=slug)
        content = await anyio.to_thread.run_sync(self._download_sync, meta["id"])
        return PageRead(
            body=content.decode("utf-8"),
            etag=meta["headRevisionId"],
            mtime=datetime.fromisoformat(meta["modifiedTime"]),
        )

    def _find_page_metadata_sync(self, slug: str) -> dict[str, Any] | None:
        return _find_unique_child(
            self._service,
            parent_id=self._pages_folder_id,
            name=f"{slug}{_PAGE_SUFFIX}",
            fields=_PAGE_FIELDS,
        )

    def _download_sync(self, file_id: str) -> bytes:
        return self._service.files().get_media(fileId=file_id).execute()

    async def list_pages(self) -> list[str]:
        """Return all slugs present under pages_folder_id, sorted."""
        names = await anyio.to_thread.run_sync(self._list_page_names_sync)
        return sorted(
            name.removesuffix(_PAGE_SUFFIX) for name in names if name.endswith(_PAGE_SUFFIX)
        )

    def _list_page_names_sync(self) -> list[str]:
        """Drain `files.list` across all pages via nextPageToken."""
        q = f"'{self._pages_folder_id}' in parents and trashed=false"
        names: list[str] = []
        page_token: str | None = None
        while True:
            result = (
                self._service.files()
                .list(
                    q=q,
                    fields="nextPageToken, files(name)",
                    pageSize=100,
                    pageToken=page_token,
                )
                .execute()
            )
            names.extend(f["name"] for f in result.get("files", []))
            page_token = result.get("nextPageToken")
            if not page_token:
                return names

    async def write_page(
        self,
        slug: str,
        body: str,
        expected_etag: str | None = None,
    ) -> str:
        """Drive-side CAS via headRevisionId compare-and-swap.

        Etag semantics mirror Local exactly:
          - expected_etag is None and file missing → create
          - expected_etag is None and file exists  → WikiConflictError (anti-clobber)
          - expected_etag matches headRevisionId   → update
          - expected_etag set but file missing OR mismatch → WikiConflictError

        Same TOCTOU window as Local (read-then-write); acceptable for
        single-process MCP. Drive has no native If-Match header on update.
        """
        validate_slug(slug)
        body_bytes = body.encode("utf-8")
        return await anyio.to_thread.run_sync(
            self._write_page_sync, slug, body_bytes, expected_etag
        )

    def _write_page_sync(
        self,
        slug: str,
        body_bytes: bytes,
        expected_etag: str | None,
    ) -> str:
        meta = self._find_page_metadata_sync(slug)
        media = MediaInMemoryUpload(body_bytes, mimetype=_MARKDOWN_MIME)

        if meta is None:
            if expected_etag is not None:
                raise WikiConflictError(
                    f"page does not exist but caller passed expected_etag for {slug}",
                    slug=slug,
                    expected_etag=expected_etag,
                    actual_etag=None,
                )
            created = (
                self._service.files()
                .create(
                    body={
                        "name": f"{slug}{_PAGE_SUFFIX}",
                        "parents": [self._pages_folder_id],
                    },
                    media_body=media,
                    fields="id,headRevisionId,modifiedTime",
                )
                .execute()
            )
            return created["headRevisionId"]

        if expected_etag != meta["headRevisionId"]:
            raise WikiConflictError(
                f"etag mismatch for {slug}",
                slug=slug,
                expected_etag=expected_etag,
                actual_etag=meta["headRevisionId"],
            )
        updated = (
            self._service.files()
            .update(
                fileId=meta["id"],
                media_body=media,
                fields="id,headRevisionId,modifiedTime",
            )
            .execute()
        )
        return updated["headRevisionId"]

    # ───── Log operations ──────────────────────────────────────────

    async def read_log(self) -> str:
        """Return wiki/log.md as text, or empty string if missing."""
        meta = await anyio.to_thread.run_sync(self._find_log_metadata_sync)
        if meta is None:
            return ""
        self._log_file_id = meta["id"]
        content = await anyio.to_thread.run_sync(self._download_sync, meta["id"])
        return content.decode("utf-8")

    async def append_log(self, entry: LogEntry) -> None:
        """Read-modify-write append, serialized within this process by a lock.

        Drive has no atomic append; cross-process appends are not supported.
        """
        addition = (serialize_log_entry(entry) + "\n\n").encode("utf-8")
        async with self._log_lock:
            await anyio.to_thread.run_sync(self._append_log_sync, addition)

    def _find_log_metadata_sync(self) -> dict[str, Any] | None:
        return _find_unique_child(
            self._service,
            parent_id=self._wiki_folder_id,
            name=_LOG_FILE_NAME,
            fields=_NAME_ONLY_FIELDS,
            raise_on_multiple=False,
        )

    def _append_log_sync(self, addition: bytes) -> None:
        file_id = self._log_file_id
        if file_id is None:
            meta = self._find_log_metadata_sync()
            if meta is None:
                media = MediaInMemoryUpload(addition, mimetype=_MARKDOWN_MIME)
                created = (
                    self._service.files()
                    .create(
                        body={
                            "name": _LOG_FILE_NAME,
                            "parents": [self._wiki_folder_id],
                        },
                        media_body=media,
                        fields="id",
                    )
                    .execute()
                )
                self._log_file_id = created["id"]
                return
            file_id = meta["id"]
            self._log_file_id = file_id

        existing = self._service.files().get_media(fileId=file_id).execute()
        new_body = existing + addition
        media = MediaInMemoryUpload(new_body, mimetype=_MARKDOWN_MIME)
        self._service.files().update(
            fileId=file_id,
            media_body=media,
            fields="id",
        ).execute()

    # ───── Raw layer (read-only) ───────────────────────────────────

    async def write_raw_file(self, name: str, data: bytes) -> None:
        """Always raises. raw/ is immutable per Karpathy."""
        raise WikiPermissionError(
            "writes to raw/ are not allowed; raw sources are immutable",
            target=f"raw/{name}",
        )


def _find_unique_child(
    service: Any,
    *,
    parent_id: str,
    name: str,
    fields: str,
    raise_on_multiple: bool = True,
) -> dict[str, Any] | None:
    """Find a single child named `name` directly under `parent_id`.

    Returns the file metadata dict, or None if not found. When multiple
    matches exist:
      - raise_on_multiple=True (folder/page lookups): raise WikiNotFoundError
        with an "ambiguous" message — surfaces user setup mistakes loudly.
      - raise_on_multiple=False (log lookup): silently return the first.
    """
    q = f"name='{name}' and '{parent_id}' in parents and trashed=false"
    result = service.files().list(q=q, fields=fields, pageSize=2).execute()
    files = result.get("files", [])
    if not files:
        return None
    if raise_on_multiple and len(files) > 1:
        ids = ", ".join(f["id"] for f in files)
        raise WikiNotFoundError(
            f"ambiguous: multiple {name!r} entries under {parent_id} (ids: {ids})",
            slug=name,
        )
    return files[0]
