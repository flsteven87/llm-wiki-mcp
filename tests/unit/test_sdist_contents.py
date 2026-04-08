"""Guard: the source distribution must not leak private project context.

MEMORY.md holds session-to-session handoff notes, user profile, and
strategic decisions. It belongs in git history, not on PyPI.
"""

from __future__ import annotations

import subprocess
import tarfile
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def sdist_names(tmp_path_factory: pytest.TempPathFactory) -> list[str]:
    """Build a fresh sdist into a temp dir and return the archive member names."""
    out = tmp_path_factory.mktemp("dist")
    subprocess.run(
        ["uv", "build", "--sdist", "--out-dir", str(out)],
        check=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    tarballs = list(out.glob("*.tar.gz"))
    assert len(tarballs) == 1, f"expected exactly one sdist, got {tarballs}"
    with tarfile.open(tarballs[0], "r:gz") as tar:
        return tar.getnames()


def test_memory_md_excluded_from_sdist(sdist_names: list[str]) -> None:
    leaks = [n for n in sdist_names if n.endswith("/MEMORY.md")]
    assert not leaks, f"MEMORY.md leaked into sdist: {leaks}"


def test_plan_md_excluded_from_sdist(sdist_names: list[str]) -> None:
    leaks = [n for n in sdist_names if n.endswith("/PLAN.md")]
    assert not leaks, f"PLAN.md leaked into sdist: {leaks}"


def test_docs_plans_excluded_from_sdist(sdist_names: list[str]) -> None:
    leaks = [n for n in sdist_names if "/docs/plans/" in n]
    assert not leaks, f"docs/plans/* leaked into sdist: {leaks[:3]}..."


def test_readme_included_in_sdist(sdist_names: list[str]) -> None:
    assert any(n.endswith("/README.md") for n in sdist_names), "README.md must ship"


def test_license_included_in_sdist(sdist_names: list[str]) -> None:
    assert any(n.endswith("/LICENSE") for n in sdist_names), "LICENSE must ship"


def test_pyproject_included_in_sdist(sdist_names: list[str]) -> None:
    assert any(n.endswith("/pyproject.toml") for n in sdist_names), "pyproject.toml must ship"


def test_tests_included_in_sdist(sdist_names: list[str]) -> None:
    """Sdist should include tests so downstream packagers can verify."""
    assert any("/tests/" in n for n in sdist_names), "tests/ should ship in sdist"
