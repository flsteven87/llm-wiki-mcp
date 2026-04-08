"""The package version has one writable source of truth: pyproject.toml.
`llm_wiki_mcp.__version__` is derived from installed metadata and must match.
"""

from __future__ import annotations

import tomllib
from importlib.metadata import version
from pathlib import Path

import llm_wiki_mcp


def _pyproject_version() -> str:
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    with pyproject.open("rb") as f:
        return tomllib.load(f)["project"]["version"]


def test_dunder_version_matches_installed_metadata() -> None:
    assert llm_wiki_mcp.__version__ == version("llm-wiki-mcp")


def test_dunder_version_matches_pyproject() -> None:
    assert llm_wiki_mcp.__version__ == _pyproject_version()
