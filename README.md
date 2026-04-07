# llm-wiki-mcp

An MCP server for Karpathy-style LLM wikis — persistent, compounding markdown knowledge bases that any MCP-compatible agent can read, write, and maintain.

> Status: **pre-alpha**, under active design. See [PLAN.md](PLAN.md).

## What it does

Karpathy's [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) pattern says: instead of re-deriving knowledge from raw documents on every query (RAG), have your LLM compile a structured wiki once and keep it current. Pages cross-link, contradictions get flagged, and the wiki gets richer with every source.

This project ships that workflow as an **MCP server** so it works in Claude Code, Claude Desktop, Cursor, Codex, Hermes, OpenClaw, or any MCP client.

The 6 core tools enforce the invariants that LLMs forget when left to free-form file writing:

- `wiki_create_page` — schema-validated page creation
- `wiki_update_page` — auto-bumps `updated`, atomic write
- `wiki_read_page` — parsed frontmatter + body
- `wiki_log_append` — append-only operation log, format guaranteed
- `wiki_index_add` — index maintenance under the right category
- `wiki_find_unlinked_mentions` — exhaustive backlink audit (the part LLMs always skip)

## Storage backends

The server speaks to a `Storage` protocol. v0.1 ships:

- **LocalFilesystemStorage** — for personal use, dev, and tests
- **GoogleDriveStorage** *(planned)* — point at any folder in your Drive, treat it as an Obsidian vault, edit from Obsidian + LLM in parallel

Install with extras:

```bash
pip install llm-wiki-mcp                # local filesystem only
pip install "llm-wiki-mcp[gdrive]"      # + Google Drive backend
```

## Why MCP and not a Claude Code skill?

Skills are prose instructions; MCP tools are deterministic functions. The wiki workflow needs **both**:

- Skills handle interpretation: reading sources, choosing what's important, writing prose summaries
- MCP tools handle invariants: backlink completeness, log formatting, frontmatter validation, atomic writes

This server is the invariant layer. Skills (in any agent) call these tools instead of writing files directly.

## License

Apache 2.0
