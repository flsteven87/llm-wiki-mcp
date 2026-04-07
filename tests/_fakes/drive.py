"""In-memory fake of the small slice of google-api-python-client we use.

Supports exactly the call chains GoogleDriveStorage relies on:

    service.files().list(q=..., fields=..., pageSize=...).execute()
    service.files().get_media(fileId=...).execute()
    service.files().update(fileId=..., media_body=..., fields=...).execute()
    service.files().create(body=..., media_body=..., fields=...).execute()

Anything else raises NotImplementedError to keep the surface honest.

Query parser supports the dialect we generate, NOT full Drive query syntax:

    name='X' and 'PARENT' in parents and trashed=false
    'PARENT' in parents and trashed=false
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from googleapiclient.http import MediaInMemoryUpload


class _FakeFile:
    __slots__ = (
        "content",
        "head_revision_id",
        "id",
        "modified_time",
        "name",
        "parents",
    )

    def __init__(
        self,
        *,
        id: str,
        name: str,
        parents: list[str],
        content: bytes,
        head_revision_id: str,
        modified_time: str,
    ) -> None:
        self.id = id
        self.name = name
        self.parents = parents
        self.content = content
        self.head_revision_id = head_revision_id
        self.modified_time = modified_time

    def to_metadata(self) -> dict[str, Any]:
        # We ignore the field projection and return the standard subset; the
        # production code only ever asks for id/headRevisionId/modifiedTime/name.
        return {
            "id": self.id,
            "name": self.name,
            "headRevisionId": self.head_revision_id,
            "modifiedTime": self.modified_time,
        }


class FakeDrive:
    """Minimal in-memory Drive double. Test-only."""

    def __init__(self) -> None:
        self._files: dict[str, _FakeFile] = {}
        self._rev_counter = 0

    # ── Test seeding helpers (not part of Drive API) ───────────────
    def _seed_file(
        self,
        *,
        name: str,
        parents: list[str],
        content: bytes,
    ) -> _FakeFile:
        return self._insert(name=name, parents=parents, content=content)

    def _insert(self, *, name: str, parents: list[str], content: bytes) -> _FakeFile:
        self._rev_counter += 1
        file = _FakeFile(
            id=uuid4().hex,
            name=name,
            parents=list(parents),
            content=content,
            head_revision_id=f"rev{self._rev_counter}",
            modified_time=datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
        )
        self._files[file.id] = file
        return file

    # ── Drive API surface ─────────────────────────────────────────
    def files(self) -> _FakeFilesResource:
        return _FakeFilesResource(self)


class _FakeFilesResource:
    def __init__(self, drive: FakeDrive) -> None:
        self._drive = drive

    def list(
        self,
        *,
        q: str = "",
        fields: str | None = None,
        pageSize: int = 100,
    ) -> _FakeRequest:
        return _FakeRequest(lambda: self._do_list(q))

    def get_media(self, *, fileId: str) -> _FakeRequest:
        return _FakeRequest(lambda: self._drive._files[fileId].content)

    def update(
        self,
        *,
        fileId: str,
        media_body: MediaInMemoryUpload,
        fields: str | None = None,
    ) -> _FakeRequest:
        return _FakeRequest(lambda: self._do_update(fileId, media_body))

    def create(
        self,
        *,
        body: dict[str, Any],
        media_body: MediaInMemoryUpload,
        fields: str | None = None,
    ) -> _FakeRequest:
        return _FakeRequest(lambda: self._do_create(body, media_body))

    # ── Internal handlers ─────────────────────────────────────────
    def _do_list(self, q: str) -> dict[str, Any]:
        name_match = re.search(r"name='([^']*)'", q)
        parent_match = re.search(r"'([^']*)' in parents", q)
        wanted_name = name_match.group(1) if name_match else None
        wanted_parent = parent_match.group(1) if parent_match else None

        files = []
        for f in self._drive._files.values():
            if wanted_name is not None and f.name != wanted_name:
                continue
            if wanted_parent is not None and wanted_parent not in f.parents:
                continue
            files.append(f.to_metadata())
        return {"files": files}

    def _do_update(self, file_id: str, media: MediaInMemoryUpload) -> dict[str, Any]:
        file = self._drive._files[file_id]
        self._drive._rev_counter += 1
        file.content = _read_media_bytes(media)
        file.head_revision_id = f"rev{self._drive._rev_counter}"
        file.modified_time = datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
        return file.to_metadata()

    def _do_create(self, body: dict[str, Any], media: MediaInMemoryUpload) -> dict[str, Any]:
        file = self._drive._insert(
            name=body["name"],
            parents=body.get("parents", []),
            content=_read_media_bytes(media),
        )
        return file.to_metadata()


def _read_media_bytes(media: MediaInMemoryUpload) -> bytes:
    """Drain a MediaInMemoryUpload via its public getbytes() API."""
    return media.getbytes(0, media.size())


class _FakeRequest:
    """Mimics googleapiclient's HttpRequest — only the .execute() method."""

    def __init__(self, thunk):
        self._thunk = thunk

    def execute(self):
        return self._thunk()
