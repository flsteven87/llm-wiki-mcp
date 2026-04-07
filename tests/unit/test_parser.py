"""Markdown parser for wiki pages.

Two responsibilities:
1. Split frontmatter from body. Frontmatter is parsed as YAML into dict[str, Any]
   and passed through unchanged. We do NOT validate keys or values.
2. Extract Obsidian-style [[wikilinks]] from the body. Multi-syntax detection
   (e.g., Markdown []()) is intentionally deferred until a real user needs it.

The parser is pure: input is text, output is (frontmatter dict, body str, links list).
"""

from llm_wiki_mcp.parser import extract_links, parse_page


def test_parse_page_with_frontmatter():
    text = (
        "---\n"
        "title: Attention Is All You Need\n"
        "tags: [paper, transformer]\n"
        "updated: 2026-04-07\n"
        "---\n"
        "\n"
        "# Attention Is All You Need\n"
        "\n"
        "See also [[transformer-architecture]] and [[self-attention]].\n"
    )
    fm, body, links = parse_page(text)
    assert fm["title"] == "Attention Is All You Need"
    assert fm["tags"] == ["paper", "transformer"]
    assert "Attention Is All You Need" in body
    assert links == ["transformer-architecture", "self-attention"]


def test_parse_page_without_frontmatter():
    text = "Plain body with [[a-link]]."
    fm, body, links = parse_page(text)
    assert fm == {}
    assert "Plain body" in body
    assert links == ["a-link"]


def test_parse_page_with_unknown_frontmatter_keys_passes_through():
    """We never validate frontmatter — any keys the user puts in stay there."""
    text = (
        "---\n"
        "totally_made_up_field: 42\n"
        "another_one: [a, b, c]\n"
        "nested:\n"
        "  deep: value\n"
        "---\n"
        "body\n"
    )
    fm, _, _ = parse_page(text)
    assert fm["totally_made_up_field"] == 42
    assert fm["another_one"] == ["a", "b", "c"]
    assert fm["nested"] == {"deep": "value"}


def test_extract_links_deduplicates_in_order():
    body = "See [[foo]], then [[bar]], then [[foo]] again, then [[baz]]."
    assert extract_links(body) == ["foo", "bar", "baz"]


def test_extract_links_ignores_invalid_slugs():
    """Slugs inside [[]] that don't pass slug regex are not returned.

    Rationale: a stray "[[Some Random Phrase]]" in body is probably not a
    real link target. The slug regex is the bouncer.
    """
    body = "Real: [[valid-slug]]. Fake: [[Not A Slug]]. Also fake: [[UPPER]]."
    assert extract_links(body) == ["valid-slug"]


def test_extract_links_handles_no_links():
    assert extract_links("no links here") == []


def test_extract_links_handles_aliased_obsidian_link():
    """Obsidian supports [[slug|display text]]; we extract the slug."""
    body = "See [[transformer-architecture|the transformer]] for details."
    assert extract_links(body) == ["transformer-architecture"]
