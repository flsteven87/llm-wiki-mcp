"""wiki_log_append tool — append a Karpathy-formatted entry to log.md.

Annotations (set by server.py at registration time):
  readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False
"""

from __future__ import annotations

from datetime import date

from llm_wiki_mcp.log_format import LogEntry
from llm_wiki_mcp.storage import WikiStorage


async def wiki_log_append(
    storage: WikiStorage,
    *,
    operation: str,
    title: str,
    timestamp: date | None = None,
    extra_lines: list[str] | None = None,
) -> LogEntry:
    """Append one entry to log.md.

    Format-locks the line via LogEntry validation. Operation may be any
    non-empty token without whitespace, brackets, or pipes — we do NOT
    enforce a fixed enum because Karpathy doesn't.
    """
    fields: dict[str, object] = {"operation": operation, "title": title}
    if timestamp is not None:
        fields["timestamp"] = timestamp
    if extra_lines is not None:
        fields["extra_lines"] = extra_lines
    entry = LogEntry.model_validate(fields)
    await storage.append_log(entry)
    return entry
