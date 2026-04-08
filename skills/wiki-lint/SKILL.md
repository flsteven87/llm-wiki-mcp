---
name: wiki-lint
description: Health-check an existing Karpathy-style LLM wiki and produce a structured findings report covering contradictions between pages, stale claims superseded by newer sources, orphan pages with no inbound links, important concepts mentioned but lacking their own page, missing cross-references, and data gaps worth filling with a web search — the six checks from Karpathy's LLM Wiki gist. Also suggests new questions to investigate and new sources to look for. Use when the user says "lint the wiki", "health check the wiki", "audit the wiki", "find orphans", "what's broken in the wiki", "what's missing from the wiki", or after every five to ten ingests as routine maintenance. Reads wiki/CLAUDE.md for the active schema and drives all wiki access through the llm-wiki-mcp tools (wiki_inventory, wiki_read, wiki_log_append). Reports findings only — it does NOT auto-fix. Fixes happen through wiki-ingest (when a new source corrects something) or through direct page edits the user approves. Do NOT use when the user is asking a substantive question (use wiki-query) or adding a source (use wiki-ingest). Do NOT use when no wiki exists yet — run wiki-init first.
license: Complete terms in LICENSE.txt
---

# wiki-lint

Health-check an existing Karpathy-style LLM wiki. The pattern this
skill follows is described in
https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f.

Karpathy's lint description, verbatim:

> Periodically, ask the LLM to health-check the wiki. Look for:
> contradictions between pages, stale claims that newer sources have
> superseded, orphan pages with no inbound links, important concepts
> mentioned but lacking their own page, missing cross-references,
> data gaps worth filling with a web search.

He also notes the LLM is good at suggesting new questions to
investigate and new sources to look for. Treat that as a seventh,
forward-looking output of lint.

**Lint reports; it does not fix.** Every finding is advisory. The
user decides which ones warrant action, and fixes happen through
`wiki-ingest` (when a new source corrects or extends the claim) or
through direct edits on the relevant page. Auto-rewriting during a
health check would defeat the point.

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

### 1. Snapshot

    wiki_inventory()

One call returns every page's slug, frontmatter, body length, mtime,
etag, `links_out`, and computed `links_in`, plus the full parsed
log. This is the deterministic backbone for checks 3, 4, and 5.

### 2. Deterministic checks (from the snapshot alone)

These do not require reading page bodies.

**Check 3 — Orphan pages.** Any page with `links_in == []` is an
orphan. `summary` pages are expected to be reached from the index
rather than from other pages, so they are not automatically orphans;
flag them only if they also have no index entry. Entity, concept,
comparison, overview, and synthesis pages with zero inbound links
are reportable orphans.

**Dangling links (bonus, mechanical).** Any slug in `links_out` that
is not present in the `pages` list is a dangling link. Not in
Karpathy's original six, but the check is free from the same data
and the finding is unambiguous.

**Check 5 — Missing cross-references.** Build the set of pages that
share a source (same `sources` frontmatter entry, or same ingest log
entry). Two pages from the same ingest with zero `[[]]` between them
are suspect — they were written in the same breath and should almost
always link each other. Flag the pair with severity "likely".

### 3. Mentioned-but-no-page (check 4)

Build a candidate term list from what already looks important:

- Every existing page title
- Every `tags` frontmatter value, deduplicated
- Proper nouns and concept names that appear repeatedly across
  recent summary pages — scan the last few summaries for nouns that
  are not already in the title/tags list but keep recurring
- Anything the user has explicitly flagged in recent log entries

Then:

    wiki_inventory(scan_for=<terms>)

The returned `mentions` field lists every `(slug, line, term)`
occurrence. For each term, count how many distinct pages mention it.
A term with mentions on three or more distinct pages but no page
whose slug equals (or closely matches) the term is a
**concept-deserving-a-page** finding. Report it with the mention
count and the list of pages that mention it.

Do not flag low-mention terms — Karpathy's "important concepts"
qualifier is doing real work. One-off mentions stay in prose.

### 4. LLM-reasoning checks (read page bodies)

These require judgment over actual content. Use `wiki_read(slug)`
on any page you need the full body of — `wiki_inventory` does not
return bodies.

**Check 1 — Contradictions.** For each entity or concept that
appears on multiple pages, re-read the relevant passages and flag
inconsistent claims about the same fact. A contradiction is not
"one page mentions X and another doesn't"; it is "one page says X
and another says not-X" or "one page says X happened in Y and
another says X happened in Z." Quote both sides in the finding.

**Check 2 — Stale claims.** A claim is stale when a more recent
ingest has superseded it but the older page was not updated. Use
log entries (`operation == "ingest"`) to identify recent sources,
cross-reference the pages they touched, and check whether older
pages making claims in the same area still reflect the latest
evidence. Frontmatter `updated` dates are a weak hint — a page not
updated since an ingest that should have touched it is suspect.

**Check 6 — Data gaps.** Step back from the wiki and ask: given
this topic (declared in `wiki/CLAUDE.md`), what is conspicuously
missing? Which entities are referenced but uninvestigated? Which
obvious primary sources have not been ingested? This is where the
LLM's general knowledge earns its keep. Suggest specific searches
the user could run, not vague areas.

**Bonus — New questions and sources.** Alongside check 6, propose
two to five concrete next moves: a question the user should be
asking the wiki, a source category they should be ingesting, or a
comparison page that would compound value. Keep this section short.

### 5. Report

Produce a single structured report. Suggested shape:

```
# Lint report — <YYYY-MM-DD>

## Summary
<pages scanned>, <findings by severity>

## Findings

### [severity] check: <name>
- slug(s): <affected pages>
- what: <one-line description>
- evidence: <quoted lines or link shape>
- suggested fix: <ingest source X / edit page Y / add page Z>

[repeat per finding]

## Suggested next moves
- <question / source / comparison>
```

Severities: **critical** (contradictions, dangling links), **likely**
(stale claims, missing cross-references between same-source pages),
**opportunity** (orphans, concepts deserving a page, data gaps,
next-move suggestions).

### 6. Log the lint run

    wiki_log_append(
        operation="lint",
        title=<one-line summary, e.g. "14 pages, 3 critical, 6 opportunities">,
        extra_lines=[<optional: top one or two findings>],
    )

Use `operation="lint"` unless `wiki/CLAUDE.md` has defined different
vocabulary.

## Tool cheatsheet

| Step                         | Tool                                              |
| ---------------------------- | ------------------------------------------------- |
| 1. Snapshot                  | `wiki_inventory()`                                |
| 2. Deterministic checks      | (snapshot fields; no tool call)                   |
| 3. Mentioned-but-no-page     | `wiki_inventory(scan_for=<terms>)`                |
| 4. Contradictions / stale    | `wiki_read(slug=...)` per page re-read            |
| 4. Data gaps / next moves    | (reasoning; no tool call)                         |
| 5. Report                    | (conversation; no tool call)                      |
| 6. Log                       | `wiki_log_append(operation="lint", ...)`          |

The llm-wiki-mcp server deliberately owns only page CRUD, inventory,
and log append. `wiki_inventory` is the workhorse here — one call
for the snapshot, a second call with `scan_for` for the
mention-driven check.

## Cadence

Run lint every five to ten ingests, or whenever the user suspects
drift. A clean wiki takes a minute; a messy one surfaces exactly
the findings that make it worth cleaning.

## What lint is not

- It is not auto-repair. Flag, do not fix.
- It is not a query. If the user wants an answer, use `wiki-query`.
- It is not an ingest. If the user brings a new source during lint,
  queue it and run `wiki-ingest` separately after the report.
