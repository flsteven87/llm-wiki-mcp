# llm-wiki-mcp

An MCP server + Claude Code skills that ship Karpathy's LLM Wiki workflow
as deterministic tools any MCP client can call.

> Status: early. Local filesystem backend only. 79 tests green.
> All four skills written. PyPI publish pending — install from git for now.

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

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
uv tool install git+https://github.com/flsteven87/llm-wiki-mcp
```

This installs the `llm-wiki-mcp` CLI (the MCP server). The skills ship
as a Claude Code plugin in the same repo — see the wiring step below.

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

## License

Apache 2.0. See `LICENSE`.
