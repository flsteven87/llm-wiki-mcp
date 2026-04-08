"""llm-wiki-mcp — an MCP server for Karpathy-style LLM wikis.

Public API (stable across patch / minor versions):

- `WikiStorage` — the Protocol that any storage backend must satisfy to
  back the four MCP tools. Implement this if you want to plug a
  different backend (SQLite, Notion, GDrive, a test fake) into an
  `llm_wiki_mcp`-based server.

- `PageRead` — the NamedTuple returned by `WikiStorage.read_page`:
  `(body, etag, mtime)`.

- `LogEntry` — the Pydantic model accepted by `WikiStorage.append_log`.
  Format-locked to Karpathy's `## [YYYY-MM-DD] operation | Title` line
  shape. Part of the Protocol surface, therefore part of the public API.

- Typed domain errors — `WikiError` and its subclasses. Catch these at
  the boundary of your own code; the MCP tool layer catches each and
  re-raises as a FastMCP `ToolError` so the client LLM sees a
  structured, recoverable message.

Composition root (`llm_wiki_mcp.server.create_server`) is exported from
its own module rather than the package root because it's the one piece
that expects a fully-constructed backend and wires a FastMCP server —
it's better discovered than implicitly imported.
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

from llm_wiki_mcp.errors import (
    WikiConflictError,
    WikiError,
    WikiNotFoundError,
    WikiPathError,
    WikiPermissionError,
    WikiSchemaViolationError,
)
from llm_wiki_mcp.log_format import LogEntry
from llm_wiki_mcp.storage import PageRead, WikiStorage

try:
    __version__ = _pkg_version("llm-wiki-mcp")
except PackageNotFoundError:  # pragma: no cover — only hit if package not installed
    __version__ = "0.0.0+unknown"

__all__ = [
    "LogEntry",
    "PageRead",
    "WikiConflictError",
    "WikiError",
    "WikiNotFoundError",
    "WikiPathError",
    "WikiPermissionError",
    "WikiSchemaViolationError",
    "WikiStorage",
    "__version__",
]
