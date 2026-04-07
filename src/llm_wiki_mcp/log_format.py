"""LogEntry model + (de)serialization for the Karpathy-locked log line format.

Karpathy explicitly specifies (gist, "Indexing and logging"):

    ## [YYYY-MM-DD] operation | Title

with the property that `grep "^## \\[" log.md` extracts all entry headers.
This module enforces the LINE SHAPE only. The operation name is a free
string — Karpathy listed `ingest`, `query`, `lint` as examples but did not
restrict it. Users may co-evolve their own operations (e.g., "init",
"update", "digest") and we accept any string that doesn't break the format.
"""

from __future__ import annotations

import re
from datetime import date
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from llm_wiki_mcp.errors import WikiSchemaViolationError

# A LINE that starts a new entry: ## [YYYY-MM-DD] <op> | <title>
_HEADER_RE = re.compile(r"^## \[(?P<date>\d{4}-\d{2}-\d{2})\] (?P<op>\S+) \| (?P<title>.+)$")


class LogEntry(BaseModel):
    """One entry in `log.md`. Format-locked, content-free.

    `extra_lines` are everything between this header and the next header
    (or end of file). They are stored verbatim. We do not interpret them.
    """

    model_config = ConfigDict(frozen=True)

    timestamp: date = Field(default_factory=date.today)
    operation: str
    title: str
    extra_lines: list[str] = Field(default_factory=list)

    # Characters that would break the single-line header format.
    _BAD_OP_CHARS: ClassVar[str] = "|[] \t\n\r"

    @field_validator("operation")
    @classmethod
    def _check_operation(cls, v: str) -> str:
        if not v:
            raise WikiSchemaViolationError("operation must not be empty", field="operation")
        if any(c in v for c in cls._BAD_OP_CHARS):
            raise WikiSchemaViolationError(
                f"operation must not contain any of {cls._BAD_OP_CHARS!r}: {v!r}",
                field="operation",
            )
        return v

    @field_validator("title")
    @classmethod
    def _check_title(cls, v: str) -> str:
        if not v:
            raise WikiSchemaViolationError("title must not be empty", field="title")
        if "\n" in v or "\r" in v:
            raise WikiSchemaViolationError("title must be single-line", field="title")
        return v


def serialize_log_entry(entry: LogEntry) -> str:
    """Render a LogEntry as the canonical Karpathy format."""
    header = f"## [{entry.timestamp.isoformat()}] {entry.operation} | {entry.title}"
    if not entry.extra_lines:
        return header
    return header + "\n" + "\n".join(entry.extra_lines)


def parse_log_entries(text: str) -> list[LogEntry]:
    """Parse log.md content into LogEntry list.

    Lines that don't start a new entry are appended to the current entry's
    `extra_lines`. Blank lines are skipped (not preserved). Anything before
    the first header is discarded (allows preamble like a top-level # Log).
    """
    entries: list[LogEntry] = []
    current_header_match: re.Match[str] | None = None
    current_extras: list[str] = []

    def flush() -> None:
        if current_header_match is None:
            return
        entries.append(
            LogEntry(
                timestamp=date.fromisoformat(current_header_match["date"]),
                operation=current_header_match["op"],
                title=current_header_match["title"],
                extra_lines=list(current_extras),
            )
        )

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        m = _HEADER_RE.match(line)
        if m:
            flush()
            current_header_match = m
            current_extras = []
        elif current_header_match is not None and line:
            current_extras.append(line)

    flush()
    return entries
