"""Public API surface — what `from llm_wiki_mcp import X` is allowed to mean.

This test file is the contract. Adding something to `__all__` at the
package root means committing to its stability; removing it is a
breaking change that requires a major version bump.

Three categories of public API today:

1. **Storage Protocol seam** — so a third party can write their own
   `WikiStorage` implementation (SQLite, Notion, GDrive v2, test fake)
   without depending on internal module paths. This includes `LogEntry`
   because the Protocol's `append_log` signature takes one.

2. **Typed errors** — so callers can catch domain-specific failures
   (`WikiConflictError` vs `WikiNotFoundError`) at the boundary of
   their own code without re-importing from `llm_wiki_mcp.errors`.

3. **`__version__`** — resolved from installed package metadata.

The server entry (`build_server`) is NOT part of the package-root API
today — it lives at `llm_wiki_mcp.server` and is covered by the server
smoke tests.
"""

from __future__ import annotations


def test_wikistorage_and_pageread_importable_from_package_root():
    from llm_wiki_mcp import PageRead, WikiStorage

    # Protocol is runtime_checkable — concrete impls must satisfy isinstance
    assert WikiStorage is not None
    assert PageRead is not None


def test_logentry_importable_from_package_root():
    """LogEntry is part of the Protocol surface (`append_log(entry: LogEntry)`),
    so downstream WikiStorage implementations must be able to import it from
    the package root without reaching into `llm_wiki_mcp.log_format`.
    """
    from llm_wiki_mcp import LogEntry

    entry = LogEntry(operation="test", title="smoke")
    assert entry.operation == "test"
    assert entry.title == "smoke"


def test_version_exposed():
    import llm_wiki_mcp

    assert isinstance(llm_wiki_mcp.__version__, str)
    assert llm_wiki_mcp.__version__  # non-empty


def test_errors_importable_from_package_root():
    from llm_wiki_mcp import (
        WikiConflictError,
        WikiError,
        WikiNotFoundError,
        WikiPathError,
        WikiPermissionError,
        WikiSchemaViolationError,
    )

    # All derive from the base
    for cls in (
        WikiPathError,
        WikiPermissionError,
        WikiNotFoundError,
        WikiConflictError,
        WikiSchemaViolationError,
    ):
        assert issubclass(cls, WikiError)


def test_local_backend_satisfies_public_protocol():
    """The first-party backend is what the Protocol is modeled on, so
    isinstance(Local, WikiStorage) is both a sanity check and a
    regression guard against accidentally drifting the Protocol.
    """
    from pathlib import Path

    from llm_wiki_mcp import WikiStorage
    from llm_wiki_mcp.storage.local import LocalFilesystemStorage

    storage = LocalFilesystemStorage(wiki_root=Path("/tmp/doesnotmatter"))
    assert isinstance(storage, WikiStorage)
