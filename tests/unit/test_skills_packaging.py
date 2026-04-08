"""Skills are shipped as package data — reachable via `importlib.resources`.

This is the third-party embeddability guarantee: after `pip install
llm-wiki-mcp`, a consumer can load the SKILL.md bodies programmatically
without having to clone the repo or know an external plugin path.

The test goes through `importlib.resources.files` (the modern
`pkgutil.get_data` replacement) so it reflects exactly what a wheel
install would expose. Because the source lives under
`src/llm_wiki_mcp/skills/`, an editable install hits the same code
path as a wheel install — no divergence between dev and prod layouts.
"""

from __future__ import annotations

from importlib.resources import files


def test_skill_md_shipped_for_each_of_four_skills():
    pkg = files("llm_wiki_mcp")
    expected_skills = ["wiki-init", "wiki-ingest", "wiki-query", "wiki-lint"]
    for skill in expected_skills:
        skill_md = pkg / f"skills/{skill}/SKILL.md"
        assert skill_md.is_file(), f"missing SKILL.md for {skill}"
        body = skill_md.read_text(encoding="utf-8")
        # Every SKILL.md is an Anthropic-format skill with frontmatter
        assert body.startswith("---\n"), f"{skill}/SKILL.md lacks frontmatter"
        assert f"name: {skill}" in body, f"{skill}/SKILL.md frontmatter wrong name"


def test_wiki_init_templates_shipped():
    """wiki-init's bundled templates are the largest data payload — they
    encode Karpathy's schema and must be present in the wheel for
    scaffolding to work at all.
    """
    pkg = files("llm_wiki_mcp")
    templates = [
        "CLAUDE.md.template",
        "index.md.template",
        "log.md.template",
        "mcp-wiring.md",
    ]
    for tpl in templates:
        path = pkg / f"skills/wiki-init/templates/{tpl}"
        assert path.is_file(), f"missing template {tpl}"


def test_skill_licenses_shipped():
    """Every skill carries its own LICENSE.txt (per Anthropic skill
    convention). They must ship with the skill or the `license:` field
    in SKILL.md frontmatter points nowhere.
    """
    pkg = files("llm_wiki_mcp")
    for skill in ["wiki-init", "wiki-ingest", "wiki-query", "wiki-lint"]:
        assert (pkg / f"skills/{skill}/LICENSE.txt").is_file()
