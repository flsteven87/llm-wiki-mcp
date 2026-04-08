---
name: wiki-query
description: Answer a question against an existing Karpathy-style LLM wiki by reading relevant pages and synthesizing a cited answer. Valuable answers — cross-page comparisons, novel analyses, newly-discovered connections — are filed back into the wiki as new synthesis pages so they do not disappear into chat history. Use whenever the user asks a substantive question about the wiki's topic, requests a comparison or analysis across pages, or says things like "what does the wiki say about X", "compare X and Y", "summarize what we know about X", "according to the wiki", "does the wiki cover X", or wants an answer filed back as a new wiki page. Reads wiki/CLAUDE.md for the active schema and drives all wiki access through the llm-wiki-mcp tools (wiki_inventory, wiki_read, wiki_write_page, wiki_log_append). Do NOT use when the user wants a general-knowledge answer that has nothing to do with the wiki — answer from your own knowledge. Do NOT use when the user is adding a source (use wiki-ingest) or asking for a health check (use wiki-lint). Do NOT use when no wiki exists yet — run wiki-init first.
license: Complete terms in LICENSE.txt
---

# wiki-query

Answer a question against an existing Karpathy-style LLM wiki. The
pattern this skill follows is described in
https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f.

Karpathy's query description, verbatim:

> You ask questions against the wiki. The LLM searches for relevant
> pages, reads them, and synthesizes an answer with citations.

And on filing answers back:

> good answers can be filed back into the wiki as new pages. A
> comparison you asked for, an analysis, a connection you discovered
> — these are valuable and shouldn't disappear into chat history.

Filing is a judgment call, not an automatic step. Pure fact lookup or
restatement of an existing page stays in chat. Cross-page analyses and
new connections earn a page.

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

### 1. Scope

    wiki_inventory()

No `scan_for` argument — this is a cheap call that returns every
page's slug, frontmatter, body length, and computed in/out links.
Combine it with a host `Read` of `wiki/index.md` to pick candidate
slugs. Prefer pages whose title, `tags`, or category directly match
the question. When in doubt, widen the candidate set — reading is
cheap.

### 2. Read

    wiki_read(slug=...)

Pull the full body of each candidate. If a page cites a neighbor
(`[[other-slug]]`) that clearly bears on the question, widen and
read it too. Two or three reads are normal; ten means the question
is too broad and you should narrow it with the user first.

### 3. Synthesize with citations

Write the answer in the primary language declared in
`wiki/CLAUDE.md`. Cite every non-trivial claim with `[[slug]]`
pointing at the page the claim came from. **Only cite slugs that
appeared in the `pages` list returned by step 1** — this is the
deterministic guarantee that your citations are not hallucinations.
If a claim deserves a citation but no page supports it, say so
explicitly ("the wiki does not currently cover X") rather than
inventing a slug.

Do not paraphrase so aggressively that the citation loses its
anchor. A reader should be able to open the cited page and find the
claim within a few lines.

### 4. The filing decision

Ask: is this answer worth persisting?

**File it back** when the answer is:

- A comparison across two or more pages the wiki did not previously
  contain (e.g. "how do X and Y differ on Z?")
- A new analysis that synthesizes claims from multiple pages into a
  conclusion no single page states
- A connection between pages the wiki did not previously link

**Do not file it back** when the answer is:

- A pure fact lookup ("when was X founded?") — the fact already
  lives on the source page
- A restatement of what one existing page already says
- An answer the user flagged as tentative or exploratory

When filing:

1. Pick a slug that describes the question, not the answer (e.g.
   `hua-tong-vs-zhen-ding-seasonality`, not
   `hua-tong-wins-on-seasonality`). Lowercase, dashes, at least two
   characters.
2. Build `body` to match the schema in `wiki/CLAUDE.md`. The typical
   category is `synthesis`. Include frontmatter fields the schema
   requires, the question as a heading, the cited answer, and a
   "Sources" section listing every `[[slug]]` you cited.
3. `wiki_write_page(slug=..., body=..., etag=None)`. `etag=None`
   asserts the page does not exist. On conflict, pick a different
   slug.
4. Add a one-line entry under the correct category in
   `wiki/index.md` using host `Read`/`Write` (the MCP tools do not
   touch the index).
5. `wiki_log_append(operation="query", title=<question>,
   extra_lines=[...])`. Use `operation="query"` unless
   `wiki/CLAUDE.md` has defined different vocabulary.

When not filing, skip straight to reporting.

## Tool cheatsheet

| Step                  | Tool                                     |
| --------------------- | ---------------------------------------- |
| 1. Scope              | `wiki_inventory()`                       |
| 1. Scope (index)      | host `Read` on `wiki/index.md`           |
| 2. Read candidates    | `wiki_read(slug=...)`                    |
| 3. Synthesize         | (conversation; no tool call)             |
| 4. File (page)        | `wiki_write_page(..., etag=None)`        |
| 4. File (index)       | host `Read` / `Write` on `wiki/index.md` |
| 4. File (log)         | `wiki_log_append(operation="query", ...)`|

The llm-wiki-mcp server deliberately owns only page CRUD, inventory,
and log append. Index and source fetching stay with the host agent.

## Reporting

When done, report: the answer itself (with citations), the pages
read, and whether the answer was filed (and if so, under which
slug). Keep the non-answer parts terse — the user can call
`wiki_inventory` for details.
