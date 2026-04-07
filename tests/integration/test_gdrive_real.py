"""Real-Drive smoke test for GoogleDriveStorage.

Skipped unless both env vars are set:
  LLM_WIKI_GDRIVE_TEST_FOLDER_ID    - root folder id (must contain wiki/pages/)
  LLM_WIKI_GDRIVE_TEST_CREDENTIALS  - path to service account JSON key

Run manually:
  uv run pytest tests/integration/test_gdrive_real.py -v -s

Mocks lie about network behavior. This test is the only thing that
proves the adapter works against real Drive — never delete it without
replacing with something that hits the real API.
"""

from __future__ import annotations

import os
from datetime import date

import pytest

from llm_wiki_mcp.errors import WikiNotFoundError

pytest.importorskip("googleapiclient")

_FOLDER_ID = os.environ.get("LLM_WIKI_GDRIVE_TEST_FOLDER_ID")
_CREDS = os.environ.get("LLM_WIKI_GDRIVE_TEST_CREDENTIALS")

pytestmark = pytest.mark.skipif(
    not (_FOLDER_ID and _CREDS),
    reason=(
        "real-Drive smoke test requires LLM_WIKI_GDRIVE_TEST_FOLDER_ID "
        "and LLM_WIKI_GDRIVE_TEST_CREDENTIALS"
    ),
)


@pytest.fixture
def storage():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    from llm_wiki_mcp.storage.gdrive import GoogleDriveStorage

    creds = service_account.Credentials.from_service_account_file(
        _CREDS,
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    return GoogleDriveStorage.from_root_folder(
        service=service,
        root_folder_id=_FOLDER_ID,
    )


async def test_round_trip_against_real_drive(storage):
    from llm_wiki_mcp.log_format import LogEntry

    slug = "smoke-test-page"
    body = "---\ntitle: Smoke\n---\nHello from gdrive smoke test.\n"

    # Clean slate: try to read; if exists, write with its etag.
    try:
        existing = await storage.read_page(slug)
    except WikiNotFoundError:
        etag = await storage.write_page(slug, body)
    else:
        etag = await storage.write_page(slug, body, expected_etag=existing.etag)

    page = await storage.read_page(slug)
    assert page.body == body
    assert page.etag == etag

    slugs = await storage.list_pages()
    assert slug in slugs

    await storage.append_log(
        LogEntry(timestamp=date(2026, 4, 7), operation="ingest", title="Smoke")
    )
    log_text = await storage.read_log()
    assert "ingest | Smoke" in log_text
