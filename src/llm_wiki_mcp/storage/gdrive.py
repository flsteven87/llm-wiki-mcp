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
- Both must already exist; we do NOT auto-create. Document this in CLI help.

Per-request methods (added in later tasks):
- All Drive calls are wrapped in `await anyio.to_thread.run_sync(...)` so
  the async Protocol is honored without blocking the event loop.

Concurrency:
- An instance-scoped `asyncio.Lock` serializes log appends within a single
  MCP server process. Cross-process concurrent appends are racy and out
  of scope for Phase 2B (documented as a known limitation).
"""

from __future__ import annotations

import asyncio
from typing import Any

from llm_wiki_mcp.errors import WikiNotFoundError


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

    @classmethod
    def from_root_folder(
        cls,
        *,
        service: Any,
        root_folder_id: str,
    ) -> GoogleDriveStorage:
        """Resolve the wiki/pages folder structure under root_folder_id.

        Raises WikiNotFoundError if either folder is missing. We do NOT
        create them — Phase 2B requires pre-existing structure.
        """
        wiki_id = _find_child_folder_id(service, parent_id=root_folder_id, name="wiki")
        if wiki_id is None:
            raise WikiNotFoundError(
                f"no 'wiki' folder under root {root_folder_id}",
                slug="wiki",
            )
        pages_id = _find_child_folder_id(service, parent_id=wiki_id, name="pages")
        if pages_id is None:
            raise WikiNotFoundError(
                f"no 'pages' folder under wiki {wiki_id}",
                slug="pages",
            )
        return cls(
            service=service,
            wiki_folder_id=wiki_id,
            pages_folder_id=pages_id,
        )


def _find_child_folder_id(service: Any, *, parent_id: str, name: str) -> str | None:
    """Sync Drive query: find a folder named `name` directly under `parent_id`.

    Returns the folder id, or None if not found. Raises if multiple matches
    (ambiguity is a user-side mistake we should surface, not silently pick).
    """
    q = f"name='{name}' and '{parent_id}' in parents and trashed=false"
    result = service.files().list(q=q, fields="files(id,name)", pageSize=10).execute()
    files = result.get("files", [])
    if not files:
        return None
    if len(files) > 1:
        ids = ", ".join(f["id"] for f in files)
        raise WikiNotFoundError(
            f"ambiguous: multiple {name!r} folders under {parent_id} (ids: {ids})",
            slug=name,
        )
    return files[0]["id"]
