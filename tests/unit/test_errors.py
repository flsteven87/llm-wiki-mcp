"""Domain errors for wiki operations.

Why these exist as a dedicated module: every storage and tool layer raises
the same set of typed errors. The MCP layer maps them to FastMCP tool errors
with isError=true. By keeping them in one place, we never confuse a security
violation with a missing file with an etag mismatch.
"""

from llm_wiki_mcp.errors import (
    WikiConflictError,
    WikiError,
    WikiNotFoundError,
    WikiPathError,
    WikiPermissionError,
    WikiSchemaViolationError,
)


def test_all_errors_inherit_from_wiki_error():
    for cls in (
        WikiPathError,
        WikiPermissionError,
        WikiNotFoundError,
        WikiConflictError,
        WikiSchemaViolationError,
    ):
        assert issubclass(cls, WikiError)
        assert issubclass(cls, Exception)


def test_conflict_error_carries_etag_context():
    err = WikiConflictError(
        "etag mismatch",
        slug="my-page",
        expected_etag="abc",
        actual_etag="def",
    )
    assert err.slug == "my-page"
    assert err.expected_etag == "abc"
    assert err.actual_etag == "def"
    assert "etag mismatch" in str(err)


def test_path_error_carries_attempted_path():
    err = WikiPathError("path escapes wiki root", attempted_path="../etc/passwd")
    assert err.attempted_path == "../etc/passwd"
