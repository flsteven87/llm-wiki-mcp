---
name: wiki-ingest
description: Ingest a new source (URL, file, paper, transcript, pasted text) into an existing Karpathy-style LLM wiki. Reads the source, discusses key takeaways with the user, writes a summary page, updates the index, updates relevant entity and concept pages across the wiki, and appends an entry to the log — the exact flow from Karpathy's LLM Wiki pattern. A single ingest may touch 10–15 pages. Use this whenever the user gives you a URL, a file path, or pasted text and asks to "add this to the wiki", "ingest", "process", "file this", or simply pastes a source into a session where a wiki is active. Also use when the user says "add this paper to the knowledge base" or "can you process this article for my wiki". Reads wiki/CLAUDE.md for the active schema and drives all wiki mutations through the llm-wiki-mcp tools (wiki_inventory, wiki_read, wiki_write_page, wiki_log_append). Do NOT use when the user wants a plain summary with no wiki context — just summarize directly. Do NOT use when no wiki exists yet — run wiki-init first. Do NOT use for querying the wiki (use wiki-query) or health-checking it (use wiki-lint).
license: Complete terms in LICENSE.txt
---

# wiki-ingest

Process a new source into an existing Karpathy-style LLM wiki. The
pattern and the ingest example this skill follows are described in
https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f.

Karpathy's ingest example, verbatim:

> the LLM reads the source, discusses key takeaways with you, writes
> a summary page in the wiki, updates the index, updates relevant
> entity and concept pages across the wiki, and appends an entry to
> the log.

A single ingest may touch 10–15 pages. Karpathy prefers one source
at a time with the user in the loop; batch mode is also possible
(see the end).

## Prerequisites

- A wiki exists. If not, run `wiki-init` first.
- The llm-wiki-mcp server is wired into this session. If
  `wiki_inventory` is not callable, tell the user to add the server
  to their MCP client config and restart.

## Pre-flight

Read `wiki/CLAUDE.md`. This is the authoritative schema — page
categories, frontmatter fields, link conventions, and operation
vocabulary. The user may have evolved it since `wiki-init`. Honor
the current state, not the defaults.

## Flow

Follow Karpathy's six actions in order.

### 1. Read the source

Use whatever the host agent provides — `WebFetch` for URLs, `Read`
for local files, or treat pasted text as-is. The llm-wiki-mcp server
does not fetch sources; extraction is the host's job. Archiving the
raw file into `raw/` is the user's job, not this skill's.

### 2. Discuss key takeaways with the user

Surface the handful of entities, concepts, and claims that matter.
Ask the user what to emphasize.

### 3. Write a summary page in the wiki

Pick a slug (lowercase, dashes, at least two characters). Build
`body` to match the schema in `wiki/CLAUDE.md`, including any
frontmatter block. The server does not validate frontmatter shape —
you are responsible for consistency.

    wiki_write_page(slug=..., body=..., etag=None)

`etag=None` asserts the page does not exist. If the server returns
a conflict error, the slug is taken — pick a different one.

### 4. Update the index

`wiki/index.md` sits outside `wiki/pages/`, so the MCP tools do not
touch it. Read it with the host `Read` tool, add a one-line entry
under the correct category section, write it back with `Write`.

### 5. Update relevant entity and concept pages across the wiki

Extract the set of key terms from the source — entity names, concept
names, notable claims. Aim for five to twenty terms.

    wiki_inventory(scan_for=<terms>)

The response's `mentions` field lists each existing page that
mentions any of the terms and the exact line. The `pages` field
tells you which entities and concepts already have their own page
versus which are only mentioned in passing and deserve one now.
Note that `wiki_inventory` does not return page bodies — only
metadata and mention lines. Use `wiki_read` when you need the full
body of a page to update.

Use this as the ground truth for Karpathy's "relevant entity and
concept pages":

- **Existing page, new information.** `wiki_read(slug=...)` for the
  current body and etag. Integrate the new claim, source citation,
  backlink, or contradiction note. `wiki_write_page(slug, body,
  etag=<previous etag>)`. On conflict, re-read and retry. Never
  discard existing content.
- **New entity or concept deserving its own page.** Create it with
  `wiki_write_page(..., etag=None)`, then add it to the index
  (repeat step 4 for the new slug).

Include `[[slug]]` backlinks to other wiki pages wherever natural.
Link only to slugs that appear in `wiki_inventory.pages`.

### 6. Append a log entry

    wiki_log_append(
        operation="ingest",
        title=<source title>,
        extra_lines=[<one or two short lines>],
    )

The server formats the entry as `## [YYYY-MM-DD] ingest | <title>`
and guarantees atomic append. Concurrent ingests will not clobber
each other. Use `operation="ingest"` unless `wiki/CLAUDE.md` has
defined different vocabulary.

## Tool cheatsheet

| Karpathy step              | Tool                                                          |
| -------------------------- | ------------------------------------------------------------- |
| 1. Read source             | host `WebFetch` / `Read`                                      |
| 2. Discuss takeaways       | (conversation; no tool call)                                  |
| 3. Summary page            | `wiki_write_page`                                             |
| 4. Index update            | host `Read` / `Write`                                         |
| 5. Entity/concept updates  | `wiki_inventory(scan_for=...)`, `wiki_read`, `wiki_write_page`|
| 6. Log entry               | `wiki_log_append`                                             |

The llm-wiki-mcp server deliberately owns only page CRUD, inventory,
and log append. Index, raw/, and source fetching stay with the host
agent.

## Batch mode

If the user explicitly asks to batch-ingest a directory, loop the
flow per source. Skip step 2's discussion unless the user wants it.
Pause every five sources to report progress.

## Reporting

When done, report: source title, pages created (slugs), pages
updated (slug + one-line diff reason), and the log entry appended.
Keep it terse — the user can read `wiki/log.md` or call
`wiki_inventory` for details.
