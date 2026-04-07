Wiki created at {{ABSOLUTE_PATH}}.

Add this to your MCP client config and restart the agent:

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):

    {
      "mcpServers": {
        "llm-wiki": {
          "command": "uvx",
          "args": ["llm-wiki-mcp", "--wiki-root", "{{ABSOLUTE_PATH}}"]
        }
      }
    }

**Claude Code** (`.mcp.json` in your project or `~/.claude/mcp_servers.json` globally): same shape.

**Cursor** (`~/.cursor/mcp.json`): same shape.

After restart, four tools become available:

- `wiki_read` — read a page by slug.
- `wiki_write_page` — create or update a page, with etag-based conflict detection.
- `wiki_log_append` — append an entry to `wiki/log.md` in Karpathy format.
- `wiki_inventory` — snapshot all pages + log entries + optional backlink scan.

Say `ingest <url-or-file>` to trigger the `wiki-ingest` skill.
