# Changelog

All notable changes to `llm-wiki-mcp` are documented here. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
this project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.1] — 2026-04-08

### Added

- **MCP Registry ownership marker** in `README.md` — adds the hidden
  `mcp-name: io.github.flsteven87/llm-wiki-mcp` comment so the
  registry's PyPI ownership proof passes. No functional changes; this
  is the forward-fix release that unblocks MCP Registry submission.

## [0.1.0] — 2026-04-08

### Added — initial public release

- **MCP server** with four deterministic tools: `wiki_read`,
  `wiki_write_page`, `wiki_log_append`, `wiki_inventory`. Atomic
  writes, etag-based conflict detection, append-only log integrity,
  path containment against CVE-2025-53109 class attacks.
- **Local filesystem backend** (`LocalFilesystemStorage`) as the
  reference implementation of the `WikiStorage` Protocol.
- **Four Claude Code skills** (`wiki-init`, `wiki-ingest`,
  `wiki-query`, `wiki-lint`) shipping as a plugin in the same repo.
  Faithful to Karpathy's
  [LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
  — closed 3-op taxonomy, 6 page categories, log format locked.
- **Library embedding surface**: public `WikiStorage` Protocol,
  `PageRead` NamedTuple, `LogEntry` model, and six typed domain
  errors exported from the package root.
  `build_server(*, storage: WikiStorage)` at `llm_wiki_mcp.server`
  is the composition root for external consumers who want to plug a
  different backend.
- **PEP 561 `py.typed` marker** — downstream mypy/pyright users get
  full type information for the public API.
- **Bundled skills shipped as package data** under
  `llm_wiki_mcp/skills/` — loadable via `importlib.resources` for
  non-Claude-Code agents.
- **100+ tests** across unit, integration, and security layers
  (including a CVE-2025-53109 path-traversal regression suite).

### Design

- **MCP enforces behaviors, not schemas.** Mechanical safety
  (atomicity, etag CAS, append-only, path containment) is
  guaranteed; frontmatter shape, page types, and categories live
  in the user's `wiki/CLAUDE.md` and are never touched by the
  server. Co-evolves with the LLM instead of locking a schema.

### Known limitations

- `write_page` etag CAS has a small TOCTOU window (POSIX
  read-then-rename). Acceptable for single-process MCP; documented,
  not fixed.
- `wiki_inventory` reads pages sequentially. Acceptable at <50
  pages on local filesystem; will be parallelized when a real
  backend demands it.
- Obsidian-style `[[slug]]` links only; Markdown `[]()` detection
  deferred until a first non-Obsidian user asks.

[0.1.1]: https://github.com/flsteven87/llm-wiki-mcp/releases/tag/v0.1.1
[0.1.0]: https://github.com/flsteven87/llm-wiki-mcp/releases/tag/v0.1.0
