"""Security regression tests for path containment.

CVE-2025-53109 was filed against the official MCP Filesystem server: a
crafted symlink inside the sandbox could resolve to a location outside the
sandbox after path normalization. The fix is to call realpath() AFTER all
join/normalize steps and check containment on the realpath result.

These tests must always pass. If a future change makes any of them fail,
we have reintroduced the CVE class.
"""

from pathlib import Path

import pytest

from llm_wiki_mcp.errors import WikiPathError
from llm_wiki_mcp.slug import resolve_under_root


def test_simple_join_inside_root_succeeds(tmp_path: Path):
    root = tmp_path / "wiki"
    root.mkdir()
    target = resolve_under_root(root, "page.md")
    assert target == (root / "page.md").resolve()


def test_dotdot_traversal_rejected(tmp_path: Path):
    root = tmp_path / "wiki"
    root.mkdir()
    with pytest.raises(WikiPathError):
        resolve_under_root(root, "../escape.md")


def test_absolute_path_rejected(tmp_path: Path):
    root = tmp_path / "wiki"
    root.mkdir()
    with pytest.raises(WikiPathError):
        resolve_under_root(root, "/etc/passwd")


def test_symlink_escape_rejected(tmp_path: Path):
    """The CVE-2025-53109 reproduction.

    Create a symlink INSIDE the wiki root that points OUTSIDE.
    A naive path-join + lexical-normalize check passes (the link sits inside
    root) but the real target is outside. The realpath-after-resolve check
    must catch this.
    """
    root = tmp_path / "wiki"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text("secret")

    # Plant the malicious symlink inside the wiki root
    (root / "evil-link").symlink_to(outside)

    with pytest.raises(WikiPathError):
        resolve_under_root(root, "evil-link/secret.md")


def test_symlink_inside_root_allowed(tmp_path: Path):
    """Symlinks that resolve back into the wiki root are fine."""
    root = tmp_path / "wiki"
    root.mkdir()
    (root / "real.md").write_text("hi")
    (root / "alias.md").symlink_to(root / "real.md")

    target = resolve_under_root(root, "alias.md")
    assert target.resolve() == (root / "real.md").resolve()


def test_null_byte_in_path_rejected(tmp_path: Path):
    root = tmp_path / "wiki"
    root.mkdir()
    with pytest.raises((WikiPathError, ValueError)):
        resolve_under_root(root, "page\x00.md")
