"""llm-wiki-mcp — an MCP server for Karpathy-style LLM wikis.

Public API (stable across patch / minor versions):

- `WikiStorage` — the Protocol that any storage backend must satisfy to
  back the four MCP tools. Implement this if you want to plug a
  different backend (SQLite, Notion, GDrive, a test fake) into an
  `llm_wiki_mcp`-based server.

- `PageRead` — the NamedTuple returned by `WikiStorage.read_page`:
  `(body, etag, mtime)`.

- Typed domain errors — `WikiError` and its subclasses. Catch these at
  the boundary of your own code; the MCP tool layer maps each to a
  structured error response for the client LLM.

Composition root (`llm_wiki_mcp.server.create_server`) is exported from
its own module rather than the package root because it's the one piece
that expects a fully-constructed backend and wires a FastMCP server —
it's better discovered than implicitly imported.
"""

from llm_wiki_mcp.errors import (
    WikiConflictError,
    WikiError,
    WikiNotFoundError,
    WikiPathError,
    WikiPermissionError,
    WikiSchemaViolationError,
)
from llm_wiki_mcp.storage import PageRead, WikiStorage

__version__ = "0.0.0"

__all__ = [
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
