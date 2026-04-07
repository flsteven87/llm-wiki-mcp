"""Slug validation and symlink-safe path resolution.

Two responsibilities:

1. validate_slug() — accept only path-safe identifiers (regex-enforced).
2. resolve_under_root() — join a slug or relative path under a wiki root and
   verify the resolved real path remains inside the root, even if symlinks
   are involved (CVE-2025-53109 hardening).

Both functions raise WikiPathError on rejection. Both are pure (no side
effects). resolve_under_root touches the filesystem only via Path.resolve().
"""

from __future__ import annotations

import re
from pathlib import Path

from llm_wiki_mcp.errors import WikiPathError

# A slug is 2-64 chars, lowercase letters/digits/hyphens, must start and end
# with alphanumeric. Consecutive hyphens are allowed (real-world page titles
# sometimes need them after slugification).
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$")


def is_valid_slug(slug: str) -> bool:
    """Return True if slug matches the path-safe identifier regex."""
    return bool(_SLUG_RE.match(slug))


def validate_slug(slug: str) -> str:
    """Return the slug unchanged if valid; raise WikiPathError otherwise."""
    if not is_valid_slug(slug):
        raise WikiPathError(
            f"invalid slug: {slug!r}. "
            "Slugs must be 2-64 chars, lowercase a-z 0-9 and hyphens, "
            "starting and ending with alphanumeric.",
            attempted_path=slug,
        )
    return slug


def resolve_under_root(root: Path, relative: str | Path) -> Path:
    """Resolve `relative` under `root`, rejecting any path that escapes.

    The check uses realpath-after-resolve, which catches the symlink-escape
    class of bug (CVE-2025-53109). Reject conditions:

    - relative is absolute (e.g., "/etc/passwd")
    - relative contains ".." that escapes root after normalization
    - relative resolves through a symlink that points outside root
    - relative contains a null byte

    Returns the absolute, fully-resolved Path on success.
    """
    rel = str(relative)
    if "\x00" in rel:
        raise WikiPathError("null byte in path", attempted_path=rel)

    rel_path = Path(rel)
    if rel_path.is_absolute():
        raise WikiPathError(f"absolute paths not allowed: {rel!r}", attempted_path=rel)

    # Anchor the relative path under root, then resolve symlinks fully.
    candidate = root / rel_path
    try:
        resolved = candidate.resolve(strict=False)
    except (OSError, RuntimeError) as e:
        raise WikiPathError(f"failed to resolve path {rel!r}: {e}", attempted_path=rel) from e

    root_resolved = root.resolve(strict=False)

    # is_relative_to is the canonical containment check on Python 3.9+.
    # We compare the FULLY RESOLVED paths so symlinks cannot escape.
    if not resolved.is_relative_to(root_resolved):
        raise WikiPathError(
            f"path escapes wiki root: {rel!r} → {resolved}",
            attempted_path=rel,
        )

    return resolved
