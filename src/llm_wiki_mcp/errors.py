"""Typed domain errors raised by storage and tool layers.

Why typed errors: the MCP boundary maps each error class to a structured
tool error with isError=true and a recoverable hint. This lets the calling
LLM distinguish "you tried to write to raw/" (don't retry) from "etag
mismatch" (re-read and try again).
"""

from __future__ import annotations


class WikiError(Exception):
    """Base class for all wiki domain errors."""


class WikiPathError(WikiError):
    """Raised when a path escapes the wiki root or fails containment check.

    Used for: path traversal attempts, absolute paths, symlink escapes
    (CVE-2025-53109 class).
    """

    def __init__(self, message: str, *, attempted_path: str) -> None:
        super().__init__(message)
        self.attempted_path = attempted_path


class WikiPermissionError(WikiError):
    """Raised when the operation targets a protected location.

    Used for: writes to raw/, modifications to immutable regions.
    """

    def __init__(self, message: str, *, target: str) -> None:
        super().__init__(message)
        self.target = target


class WikiNotFoundError(WikiError):
    """Raised when a slug or path does not exist."""

    def __init__(self, message: str, *, slug: str) -> None:
        super().__init__(message)
        self.slug = slug


class WikiConflictError(WikiError):
    """Raised when an etag check fails (optimistic concurrency).

    The caller should re-read the page and retry with a fresh etag.
    """

    def __init__(
        self,
        message: str,
        *,
        slug: str,
        expected_etag: str,
        actual_etag: str,
    ) -> None:
        super().__init__(message)
        self.slug = slug
        self.expected_etag = expected_etag
        self.actual_etag = actual_etag


class WikiSchemaViolationError(WikiError):
    """Raised only for the few format-locked things we DO enforce.

    Currently only used by wiki_log_append for the line-format check
    (Karpathy's `## [YYYY-MM-DD] operation | Title`). Never used for
    frontmatter or category validation — those are per-domain.
    """

    def __init__(self, message: str, *, field: str) -> None:
        super().__init__(message)
        self.field = field
