"""Tests for system-prompt rendering."""

from pathlib import Path

import pytest

from llmalchemy.agent import State, _init_namespace
from llmalchemy.context import LLMAlchemyPromptWarning, render

_MINIMAL_TEMPLATE = (
    "SCHEMA:\n{{ SCHEMA }}\nSYMBOLS:\n{{ SYMBOLS }}\nTOOLS:\n{{ TOOLS }}\nIMPORTS:\n{{ IMPORTS }}\n"
)


def test_render_default_template_contains_all_sections(base, catalog_tool):
    descriptions = {"session": "db session", "disclose": "reveal tools"}
    out = render(base=base, tools=[catalog_tool], descriptions=descriptions)

    # Schema section: every ORM class source is present.
    assert "class Author(Base)" in out
    assert "class Book(Base)" in out
    # Symbols section: bullet list with the descriptions passed in.
    assert "`session`" in out
    assert "db session" in out
    assert "`disclose`" in out
    # Tools section: name + short description.
    assert "`get_author_catalog`" in out


def test_render_with_string_template(base):
    out = render(base=base, tools=[], descriptions={}, template=_MINIMAL_TEMPLATE)
    assert "SCHEMA:" in out
    assert "class Author(Base)" in out
    assert "SYMBOLS:" in out
    assert "TOOLS:" in out


def test_render_with_path_template(base, tmp_path: Path):
    path = tmp_path / "prompt.jinja"
    path.write_text(_MINIMAL_TEMPLATE)
    out = render(base=base, tools=[], descriptions={}, template=path)
    assert "class Book(Base)" in out


@pytest.mark.parametrize("missing", ["SCHEMA", "SYMBOLS", "TOOLS", "IMPORTS"])
def test_render_warns_on_missing_marker(base, missing: str):
    template = _MINIMAL_TEMPLATE.replace("{{ " + missing + " }}", "")
    with pytest.warns(LLMAlchemyPromptWarning, match=missing):
        render(base=base, tools=[], descriptions={}, template=template)


def test_render_tools_section_empty_when_no_tools(base):
    out = render(
        base=base,
        tools=[],
        descriptions={"session": "x"},
        template=_MINIMAL_TEMPLATE,
    )
    # The TOOLS section is present in the template but has no bullets.
    assert "TOOLS:\n" in out


def test_render_imports_reports_policy(base):
    forbidden = render(base=base, tools=[], descriptions={}, allowed_imports=[])
    assert "import` statements are forbidden" in forbidden

    allowed = render(
        base=base, tools=[], descriptions={}, allowed_imports=["sqlalchemy", "datetime"]
    )
    assert "`sqlalchemy`" in allowed
    assert "`datetime`" in allowed


def test_render_symbols_formats_as_markdown_bullets(base):
    out = render(
        base=base,
        tools=[],
        descriptions={"session": "a session", "disclose": "a discloser"},
        template=_MINIMAL_TEMPLATE,
    )
    assert "- `session`: a session" in out
    assert "- `disclose`: a discloser" in out


def test_render_symbols_list_inherited_classes_and_junctions(advanced_base):
    descriptions = _init_namespace(State(), advanced_base, [])
    out = render(base=advanced_base, tools=[], descriptions=descriptions)

    symbols = [line for line in out.splitlines() if line.startswith("- `")]
    assert any("Manager" in line for line in symbols)
    assert any("team_members" in line for line in symbols)
    # The schema section shows the subclass source too.
    assert "class Manager(Employee)" in out
