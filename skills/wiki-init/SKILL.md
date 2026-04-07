---
name: wiki-init
description: Scaffolds a fresh Karpathy-style LLM wiki — creates the raw/ and wiki/ directories, seeds wiki/index.md and wiki/log.md, and writes a starter wiki/CLAUDE.md schema doc that the LLM will co-evolve with the user. Use this when the user says "create a wiki", "set up an llm-wiki", "initialize a knowledge base for X", or installs the llm-wiki-mcp plugin and has no wiki yet. Also use when a user asks how to start collecting sources into the Karpathy wiki pattern. After scaffolding, prints the exact MCP client configuration snippet (Claude Desktop / Claude Code / Cursor) the user needs to wire the new wiki root into their agent. Do NOT use when a wiki already exists at the target path — read the existing wiki/CLAUDE.md and proceed with wiki-ingest instead. Do NOT use for generic note-taking setups (plain Obsidian vaults, Notion exports) that do not follow the Karpathy ingest/query/lint operation model.
license: Complete terms in LICENSE.txt
---

# wiki-init

Scaffold a Karpathy-style LLM wiki so the user can start ingesting
sources immediately. The pattern is described in
https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f —
this skill produces the minimal scaffold it implies.

## What you create

    <root>/
      raw/             # immutable source archive
      wiki/
        CLAUDE.md      # the schema, co-evolved with the user
        index.md       # catalog, organized by category
        log.md         # append-only chronological record
        pages/         # LLM-authored pages live here

`raw/` holds the original sources. `wiki/` is owned entirely by the
LLM. `wiki/CLAUDE.md` is the only file the user regularly edits — it
teaches the LLM how this particular wiki works.

## Intake

Ask the user three things, in order:

1. **Path** — where to create the wiki. Default `./wiki-root`. Suggest
   `~/wikis/<topic>` if the user keeps multiple wikis.
2. **Topic** — one sentence describing what this wiki is about.
3. **Primary language** — the language wiki pages will be written in
   (default: English).

If `<path>/wiki/CLAUDE.md` already exists, stop and tell the user the
wiki exists. Do not overwrite.

## Scaffold

This skill does not require the llm-wiki-mcp server to be running — it
creates the directory the server will later point at. Use the standard
`Write` and `Bash` tools.

1. Create `<root>/raw/` and `<root>/wiki/pages/`.
2. Write `<root>/wiki/CLAUDE.md` from `templates/CLAUDE.md.template`,
   substituting `{{TOPIC}}` and `{{LANGUAGE}}`.
3. Write `<root>/wiki/index.md` from `templates/index.md.template`,
   substituting `{{TOPIC}}`.
4. Write `<root>/wiki/log.md` from `templates/log.md.template`,
   substituting `{{DATE}}` (today, `YYYY-MM-DD`) and `{{TOPIC}}`.
5. Print the contents of `templates/mcp-wiring.md` with
   `{{ABSOLUTE_PATH}}` substituted to the absolute path of `<root>`.
6. Tell the user the wiki is ready and suggest they restart their MCP
   client, then say `ingest <first-source>` to trigger `wiki-ingest`.

## About the templates

Do not paraphrase. Write the files verbatim with placeholders replaced.
The templates encode Karpathy's operation vocabulary (ingest, query,
lint) and log format (`## [YYYY-MM-DD] <op> | <title>`) — preserving
them keeps downstream skills (`wiki-ingest`, `wiki-query`, `wiki-lint`)
working without reinterpretation.
