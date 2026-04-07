"""Log line format — the only format Karpathy explicitly locks.

Karpathy gist: `## [YYYY-MM-DD] operation | Title`
                grep "^## \\[" log.md | tail -5
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
This is the only format string in the entire gist. We enforce the SHAPE
(not the operation name — that's per-domain).
"""

from datetime import date

import pytest

from llm_wiki_mcp.errors import WikiSchemaViolationError
from llm_wiki_mcp.log_format import LogEntry, parse_log_entries, serialize_log_entry


def test_serialize_minimal_entry():
    entry = LogEntry(
        timestamp=date(2026, 4, 7),
        operation="ingest",
        title="Attention Is All You Need",
    )
    assert serialize_log_entry(entry) == "## [2026-04-07] ingest | Attention Is All You Need"


def test_serialize_entry_with_extra_lines():
    entry = LogEntry(
        timestamp=date(2026, 4, 7),
        operation="ingest",
        title="Attention Is All You Need",
        extra_lines=[
            "Pages written: attention-is-all-you-need",
            "Pages updated: transformer, self-attention",
        ],
    )
    expected = (
        "## [2026-04-07] ingest | Attention Is All You Need\n"
        "Pages written: attention-is-all-you-need\n"
        "Pages updated: transformer, self-attention"
    )
    assert serialize_log_entry(entry) == expected


def test_operation_must_not_be_empty():
    with pytest.raises(WikiSchemaViolationError) as ei:
        LogEntry(timestamp=date(2026, 4, 7), operation="", title="x")
    assert ei.value.field == "operation"


def test_operation_must_not_contain_pipe_or_bracket():
    """Operation must not contain characters that break the line format."""
    for bad in ["foo|bar", "foo[bar", "foo]bar", "foo bar"]:
        with pytest.raises(WikiSchemaViolationError):
            LogEntry(timestamp=date(2026, 4, 7), operation=bad, title="x")


def test_title_must_not_contain_newline():
    with pytest.raises(WikiSchemaViolationError):
        LogEntry(timestamp=date(2026, 4, 7), operation="ingest", title="line1\nline2")


def test_parse_round_trip():
    text = (
        "## [2026-04-01] ingest | First Source\n"
        "Pages written: first-source\n"
        "\n"
        "## [2026-04-02] lint | Health check\n"
        "0 errors, 1 warning\n"
        "\n"
        "## [2026-04-03] query | What is attention?\n"
    )
    entries = parse_log_entries(text)
    assert len(entries) == 3
    assert entries[0].operation == "ingest"
    assert entries[0].title == "First Source"
    assert entries[0].extra_lines == ["Pages written: first-source"]
    assert entries[1].operation == "lint"
    assert entries[2].operation == "query"
    assert entries[2].extra_lines == []


def test_parse_skips_non_entry_lines():
    text = (
        "# Log\n"
        "Some preamble.\n"
        "\n"
        "## [2026-04-01] ingest | Hello\n"
        "Random comment that is not an entry header\n"
        "## [2026-04-02] query | World\n"
    )
    entries = parse_log_entries(text)
    assert len(entries) == 2
    assert entries[0].extra_lines == ["Random comment that is not an entry header"]
