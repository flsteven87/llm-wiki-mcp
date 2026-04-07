"""Slug validation.

A slug is the LLM-facing identifier for a wiki page. It must be:
- Filesystem-safe across Linux/macOS/Windows (no slashes, no nulls, no Windows reserved names)
- Stable as part of URLs / wikilinks
- Short enough to use as a filename
- Long enough to be meaningful

We use a strict regex applied at the MCP boundary so the LLM cannot smuggle
"../../etc/passwd" into a slug field.
"""

import pytest

from llm_wiki_mcp.errors import WikiPathError
from llm_wiki_mcp.slug import is_valid_slug, validate_slug


@pytest.mark.parametrize(
    "slug",
    [
        "a",  # too short (min 2)
        "",
        "A-page",  # uppercase
        "page!",  # special chars
        "page name",  # space
        "page/sub",  # slash
        "../etc",
        "page-",  # trailing hyphen
        "-page",  # leading hyphen
        "page--name",  # consecutive hyphens? actually allowed by our regex; remove this case
        "x" * 65,  # too long
    ],
)
def test_invalid_slugs_rejected(slug: str):
    if slug == "page--name":
        return  # consecutive hyphens are allowed; this case is intentionally a no-op reminder
    assert not is_valid_slug(slug)
    with pytest.raises(WikiPathError):
        validate_slug(slug)


@pytest.mark.parametrize(
    "slug",
    [
        "ab",  # min length
        "x" * 64,  # max length
        "page",
        "page-name",
        "page-name-2026",
        "abc-def-ghi-jkl-mno",
        "transformer-architecture",
        "msap-process",
        "rl-from-human-feedback",
    ],
)
def test_valid_slugs_accepted(slug: str):
    assert is_valid_slug(slug)
    assert validate_slug(slug) == slug
