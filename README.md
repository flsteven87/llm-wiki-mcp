# llm-wiki-mcp

Persistent markdown wiki for your AI agent, built on [Karpathy's LLM wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f). Four MCP tools (`wiki_read`, `wiki_write_page`, `wiki_log_append`, `wiki_inventory`) plus four Claude Code skills (`wiki-init`, `wiki-ingest`, `wiki-query`, `wiki-lint`). stdio transport, local filesystem.

The server handles the boring layer LLMs keep getting wrong: atomic writes, etag conflict checks, append-only log integrity, path containment. The skills give the agent a workflow to follow. The wiki schema lives in your own `wiki/CLAUDE.md` and grows with your domain. There is no Layer 3 schema validation in the server.

> Status: alpha (v0.1.1). Local backend only. MIT licensed.

## Quick start

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

Pick an absolute path for the wiki folder. The server creates `pages/` and `log.md` under it on first run if they don't exist:

```bash
uvx llm-wiki-mcp --wiki-root /absolute/path/to/wiki
```

Wire it into your MCP client.

**Claude Code:**

```bash
claude mcp add llm-wiki -- uvx llm-wiki-mcp --wiki-root /absolute/path/to/wiki
```

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS) or **Cursor** (`~/.cursor/mcp.json`):

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

Restart the client. Four tools should appear: `wiki_read`, `wiki_write_page`, `wiki_log_append`, `wiki_inventory`.

## Claude Code skills

Claude Code users can install the bundled workflow skills as a plugin:

```bash
claude plugin marketplace add https://github.com/flsteven87/llm-wiki-mcp
claude plugin install llm-wiki-skills@llm-wiki-mcp
```

Each skill reads `wiki/CLAUDE.md` for the active schema on every run, so you can evolve the schema without re-installing anything. Ask the agent things like:

| Skill | What to ask | Needs MCP server? |
|---|---|---|
| `wiki-init` | "Create an LLM wiki for AI safety research at `~/wikis/ai-safety`." | No |
| `wiki-ingest` | "Ingest https://arxiv.org/abs/2310.12345 into the wiki." | Yes |
| `wiki-query` | "What does the wiki say about steering vectors?" | Yes |
| `wiki-lint` | "Run a wiki health check." | Yes |

`wiki-init` is a one-shot scaffolder; the other three are Karpathy's three operations.

Other MCP clients (Claude Desktop, Cursor) get the four tools but not the skills. The agent has to derive the workflow from tool descriptions alone, which works for one-off reads and writes but tends to skip the bookkeeping (log entries, backlink audits) the skills make explicit.

## The four tools

| Tool | Annotations | Purpose |
|---|---|---|
| `wiki_read` | read-only, idempotent | Read one page. Returns body, parsed frontmatter, outgoing links, etag. |
| `wiki_write_page` | destructive, idempotent | Atomic create or update with etag CAS. Pass `etag=null` to create, the read etag to update. |
| `wiki_log_append` | not idempotent | Append one entry to `log.md` in Karpathy's `## [YYYY-MM-DD] op \| Title` format. |
| `wiki_inventory` | read-only, idempotent | Snapshot the whole graph: pages, frontmatter, link edges, log entries, plus an optional plain-text mention scan for backlink audits. |

`index.md` and `raw/` are intentionally not exposed as tools. The index is LLM-curated content edited via the host's `Read`/`Write`. The raw layer is immutable from the server's perspective.

## Wiki layout

`wiki-init` scaffolds a project that looks like this:

```
your-project/
├── raw/                    Immutable source files (papers, articles, transcripts)
│   └── ...
└── wiki/                   ← --wiki-root points here
    ├── pages/              Markdown pages, one per topic
    ├── log.md              Append-only session log
    ├── index.md            LLM-curated browse page
    └── CLAUDE.md           Schema doc the LLM reads on every operation
```

`--wiki-root` points at the curated `wiki/` folder, not the parent project folder containing `raw/`. Easy to get wrong on first install; the troubleshooting section below covers the error you'll see.

## Design boundary

The server enforces mechanics, not content shape:

- **Atomic writes.** `tmp-file + fsync + rename` for pages. `O_APPEND` single-write for log entries.
- **Optimistic concurrency.** Every page has an etag (`sha256(body) || mtime_ns`). Updates supply the etag they read; a mismatch raises `WikiConflictError`, and the agent re-reads, merges, and retries.
- **Path containment.** Slugs are regex-validated. Resolved paths are checked against the realpath of the root, blocking the CVE-2025-53109 symlink-escape class.
- **Format-locked log line.** `## [YYYY-MM-DD] operation | Title`. Operation names are free strings; only characters that would break the line shape are rejected.

The server does not validate frontmatter shape, page categories, or link targets. That layer lives in your `wiki/CLAUDE.md` schema doc and grows with the LLM. Karpathy's gist is deliberately silent on content shape; baking a schema into the server would defeat the point.

## Python API

If you want to wrap the MCP server with your own storage backend (SQLite, Notion, GDrive, a test fake), implement the `WikiStorage` Protocol and pass an instance to `build_server`:

```python
from llm_wiki_mcp import WikiStorage, PageRead, LogEntry
from llm_wiki_mcp.server import build_server

class MyStorage:  # satisfies the WikiStorage Protocol
    async def read_page(self, slug: str) -> PageRead: ...
    async def write_page(self, slug, body, expected_etag=None) -> str: ...
    async def list_pages(self) -> list[str]: ...
    async def append_log(self, entry: LogEntry) -> None: ...
    async def read_log(self) -> str: ...
    async def write_raw_file(self, name, data) -> None: ...  # usually raises

server = build_server(storage=MyStorage())
server.run()
```

`build_server` is the composition root. The CLI `main()` is a thin caller that constructs `LocalFilesystemStorage` from `--wiki-root` and hands it in.

The bundled Claude Code skills ship as package data under `llm_wiki_mcp/skills/` and load via `importlib.resources` if you want to wire them into a non-Claude-Code agent. Typed domain errors (`WikiConflictError`, `WikiNotFoundError`, `WikiPermissionError`, `WikiPathError`, `WikiSchemaViolationError`) are importable from the package root for catching at your own boundary.

## Troubleshooting

**`llm-wiki-mcp: command not found`** after `uv tool install`. `uv` puts the binary in `~/.local/bin` (or `%USERPROFILE%\.local\bin` on Windows). Add it to `PATH`, or use `uvx llm-wiki-mcp ...` to invoke without a persistent shim.

**`wiki_*` tools don't appear after editing the client config.** Restart the MCP client. Claude Desktop, Claude Code, and Cursor only re-read `mcpServers` at startup.

**`WikiPathError: path escapes wiki root`.** You pointed `--wiki-root` at the project folder containing `raw/` instead of the curated `wiki/` folder inside it. `/Users/me/wikis/ai-safety/wiki` is correct; `/Users/me/wikis/ai-safety` is not.

**Skills not loading in Claude Code.** Run `claude plugin list`. If `llm-wiki-skills` is missing, rerun the marketplace commands in the [Claude Code skills](#claude-code-skills) section.

## Development

```bash
git clone https://github.com/flsteven87/llm-wiki-mcp
cd llm-wiki-mcp
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run pyright src/llm_wiki_mcp
```

## License

MIT. See [LICENSE](https://github.com/flsteven87/llm-wiki-mcp/blob/master/LICENSE).

<!-- mcp-name: io.github.flsteven87/llm-wiki-mcp -->

