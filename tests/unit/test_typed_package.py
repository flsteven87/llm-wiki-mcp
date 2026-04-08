"""PEP 561: the package ships a py.typed marker so downstream type checkers
pick up WikiStorage/PageRead/exception types instead of treating them as Any."""

from __future__ import annotations

import importlib.resources


def test_py_typed_marker_present() -> None:
    """The marker file must exist so PEP 561-compliant checkers recognize the
    package as providing inline type information."""
    marker = importlib.resources.files("llm_wiki_mcp").joinpath("py.typed")
    assert marker.is_file(), (
        "py.typed marker missing — downstream type checkers will treat imports as Any"
    )
    assert marker.read_text() == "", "py.typed marker should be empty per PEP 561"
