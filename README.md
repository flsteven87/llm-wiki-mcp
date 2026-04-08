# llm-wiki-mcp

An MCP server + Claude Code skills that ship Karpathy's LLM Wiki workflow
as deterministic tools any MCP client can call.

> Status: alpha (v0.1.0). Local filesystem backend only. 100+ tests green.
> All four skills written. Published on PyPI.

## The idea

Karpathy's [LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f):
instead of re-deriving knowledge from raw sources on every query (RAG),
have your LLM incrementally build and maintain a persistent markdown
wiki. Pages cross-link. Contradictions get flagged. The wiki gets richer
with every source.

This project is the *infrastructure* for that pattern — the bookkeeping
layer LLMs forget when left to free-form file writing.

## What's in the box

- **An MCP server** (`llm-wiki-mcp`) exposing four deterministic tools:
  `wiki_read`, `wiki_write_page`, `wiki_log_append`, `wiki_inventory`.
  Atomic writes, etag-based conflict detection, append-only log
  integrity, path containment. Local filesystem backend.
- **Four Claude Code skills** (`wiki-init`, `wiki-ingest`, `wiki-query`,
  `wiki-lint`) that drive the server through Karpathy's three
  operations plus a one-shot scaffolder.

The MCP server enforces mechanical invariants; the skills give the LLM
the workflow to follow. Both pieces install as a single Claude Code
plugin.

## Install

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv tool install llm-wiki-mcp
```

Or run it ad-hoc without installing a persistent shim:

```bash
uvx llm-wiki-mcp --wiki-root /absolute/path/to/wiki
```

This installs the `llm-wiki-mcp` CLI (the MCP server). The skills ship
as a Claude Code plugin in the same repo — see "Install the Claude Code
skills" below.

## Install the Claude Code skills (optional)

If you use Claude Code, the four skills (`wiki-init`, `wiki-ingest`,
`wiki-query`, `wiki-lint`) ship as a plugin in the same repo. They
drive the MCP server through Karpathy's workflow — the LLM reads
`SKILL.md` at the start of each operation instead of improvising.

```bash
claude plugin marketplace add https://github.com/flsteven87/llm-wiki-mcp
claude plugin install llm-wiki-skills@llm-wiki-mcp
```

Other MCP clients (Claude Desktop, Cursor) get the four MCP tools but
not the skills — the LLM derives the workflow from the tool descriptions
alone, which works but is less guided. You can still load the skill
bodies via `importlib.resources` if you're embedding the server as a
library (see "Embedding as a library" below).

## Wire it into your MCP client

Pick a wiki root. If you don't have one yet, the `wiki-init` skill will
scaffold one — but the server needs a root to point at, so create an
empty directory first or let `wiki-init` run before wiring.

**Claude Desktop** — edit
`~/Library/Application Support/Claude/claude_desktop_config.json` on
macOS:

```json
{
  "mcpServers": {
    "llm-wiki": {
      "command": "uvx",
      "args": ["llm-wiki-mcp", "--wiki-root", "/absolute/path/to/wiki"]
    }
  }
}
```

**Claude Code** — add the same block to `.mcp.json` in your project
or `~/.claude/mcp_servers.json` globally.

**Cursor** — same block in `~/.cursor/mcp.json`.

Restart the client. The four `wiki_*` tools should appear in the
session.

## First run

In any Claude Code / Claude Desktop / Cursor session with this plugin
installed:

1. *"Create an llm wiki for AI safety research at `~/wikis/ai-safety`."*
   — triggers `wiki-init`, scaffolds the directory, prints the wiring
   block.
2. Paste the wiring block into your MCP client config. Restart.
3. *"Ingest https://arxiv.org/abs/2310.12345"* — triggers `wiki-ingest`,
   reads the paper, discusses takeaways with you, writes a summary page,
   updates the index, updates relevant entity and concept pages, and
   appends a log entry.

That's Karpathy's ingest loop, running on atomic writes.

## The four tools

| Tool               | What it does                                                          |
| ------------------ | --------------------------------------------------------------------- |
| `wiki_read`        | Read a page. Returns body, parsed frontmatter, etag.                  |
| `wiki_write_page`  | Create or update a page. Etag CAS for conflict-free concurrent writes.|
| `wiki_log_append`  | Append an entry to `log.md`. Karpathy format, atomic.                 |
| `wiki_inventory`   | Snapshot pages + log + optional mention scan for backlink audit.      |

The server does *not* expose tools for `index.md` or `raw/`. Index
is LLM-owned content — use the host's standard `Read` / `Write`. `raw/`
is immutable from the server's perspective.

## The four skills

- **`wiki-init`** — scaffold a fresh wiki. Creates `raw/`, `wiki/`, a
  starter `wiki/CLAUDE.md` schema doc, seeded `index.md` and `log.md`.
  Does not need the MCP server to run.
- **`wiki-ingest`** — Karpathy's six-step ingest flow. Reads a source,
  discusses takeaways, writes a summary page, updates the index,
  updates relevant entity and concept pages, appends a log entry.
- **`wiki-query`** — answer a question by reading relevant pages and
  synthesizing a cited answer. Files valuable cross-page analyses
  back as `synthesis` pages so they compound instead of vanishing
  into chat history.
- **`wiki-lint`** — health-check the wiki for contradictions, stale
  claims, orphans, concepts deserving their own page, missing
  cross-references, and data gaps. Reports; does not auto-fix.

All four map directly to Karpathy's gist. The server stays
schema-agnostic — each skill reads `wiki/CLAUDE.md` for the active
schema on every run.

## Embedding as a library

If you want to wrap `llm-wiki-mcp` with your own storage backend
(SQLite, Notion, a hosted service, a test fake), the package exposes
a small public API:

```python
from llm_wiki_mcp import WikiStorage, PageRead
from llm_wiki_mcp.server import create_server

class MyStorage:  # must satisfy the WikiStorage Protocol
    async def read_page(self, slug: str) -> PageRead: ...
    async def write_page(self, slug, body, expected_etag=None) -> str: ...
    async def list_pages(self) -> list[str]: ...
    async def append_log(self, entry) -> None: ...
    async def read_log(self) -> str: ...
    async def write_raw_file(self, name, data) -> None: ...  # usually raises

server = create_server(storage=MyStorage())
server.run()
```

`create_server` is the composition root. It wires all four MCP tools
against whatever storage you pass in. The default CLI entry
(`llm-wiki-mcp --wiki-root <path>`) is a thin wrapper that constructs
`LocalFilesystemStorage` and calls `create_server` for you.

Typed domain errors (`WikiConflictError`, `WikiNotFoundError`,
`WikiPermissionError`, `WikiPathError`, `WikiSchemaViolationError`)
are importable from the package root for catching at your own
boundary.

Bundled skills (`wiki-init`, `wiki-ingest`, `wiki-query`, `wiki-lint`)
ship as package data under `llm_wiki_mcp/skills/`. You can read them
programmatically via `importlib.resources.files("llm_wiki_mcp")
.joinpath("skills/wiki-ingest/SKILL.md")` if you want to wire them
into a non-Claude-Code agent.

## Design note

**The MCP server enforces behaviors, not schemas.** It guarantees atomic
writes, etag-based conflict detection, append-only log integrity, and
path containment. It does *not* validate frontmatter shape, page types,
or categories. That layer lives in the user's `wiki/CLAUDE.md` — the
schema doc Karpathy describes — and is co-evolved with the LLM over
time. The skills read that file as the authoritative source of truth.

This split is deliberate. Karpathy's pattern is intentionally abstract
(the gist says so explicitly); hard-coding a schema into the server
would defeat the point. The server is the boring layer LLMs keep
getting wrong. The schema is the interesting layer you keep evolving.

## Development

```bash
git clone https://github.com/flsteven87/llm-wiki-mcp
cd llm-wiki-mcp
uv sync --extra dev
uv run pytest
uv run ruff check .
```

Plans live in `docs/plans/`. Session state in `MEMORY.md`.

## Troubleshooting

**`llm-wiki-mcp: command not found`** — `uv tool install` places the
binary under `~/.local/bin` (Linux/macOS) or `%USERPROFILE%\.local\bin`
(Windows). Add that to your `PATH`, or use `uvx llm-wiki-mcp ...` to
invoke it without installing a persistent shim.

**`wiki_*` tools don't appear in the MCP client after wiring** — you
must restart the MCP client (Claude Desktop / Claude Code / Cursor)
after editing its config. The client only reads `mcpServers` at
startup.

**`WikiPathError: path not contained in wiki root`** — the server
refuses writes outside `--wiki-root`. Double-check the path you
passed is absolute and points at the wiki folder itself, not its
parent. `/absolute/path/to/wiki` is correct; `/absolute/path/to` is
not.

**Skills not loading in Claude Code** — check the plugin is installed
with `claude plugin list`. If missing, rerun the install commands in
the "Install the Claude Code skills" section above.

## License

Apache 2.0. See `LICENSE`.
