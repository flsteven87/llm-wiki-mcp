"""Domain models exposed by the MCP tools.

These are intentionally minimal. Frontmatter is dict[str, Any] — we do not
declare a typed Frontmatter model, because Karpathy explicitly leaves
frontmatter shape per-domain.
"""

from datetime import UTC, datetime

from llm_wiki_mcp.models import Inventory, InventoryItem, Mention, Page


def test_page_construction():
    page = Page(
        slug="hello-world",
        body="# Hi\n[[other]]",
        etag="abc123",
        frontmatter={"title": "Hi", "tags": ["greet"]},
        links_out=["other"],
    )
    assert page.slug == "hello-world"
    assert page.frontmatter["title"] == "Hi"
    assert page.links_out == ["other"]


def test_inventory_aggregates():
    item = InventoryItem(
        slug="a",
        frontmatter={},
        body_length=10,
        mtime=datetime(2026, 4, 7, tzinfo=UTC),
        etag="x",
        links_out=["b"],
        links_in=[],
    )
    inv = Inventory(pages=[item], log_entries=[], mentions=[])
    assert inv.pages[0].slug == "a"
    assert inv.mentions == []


def test_mention_construction():
    m = Mention(slug="page-a", line=42, term="Transformer")
    assert m.slug == "page-a"
    assert m.line == 42
    assert m.term == "Transformer"
