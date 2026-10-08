"""Tests for system-prompt rendering."""

from pathlib import Path

import pytest

from llmalchemy.context import LLMAlchemyPromptWarning, render

_MINIMAL_TEMPLATE = "SCHEMA:\n{{ SCHEMA }}\nTOOLS:\n{{ TOOLS }}\nIMPORTS:\n{{ IMPORTS }}\n"


def test_render_default_template_contains_all_sections(base, catalog_tool):
    out = render(base=base, tools=[catalog_tool])

    # Schema section: every ORM class source is present.
    assert "class Author(Base)" in out
    assert "class Book(Base)" in out
    # The pre-loaded namespace is announced in one line.
    assert "pre-loaded" in out
    # Tools section: name + short description.
    assert "`get_author_catalog`" in out


def test_render_with_string_template(base):
    out = render(base=base, tools=[], template=_MINIMAL_TEMPLATE)
    assert "SCHEMA:" in out
    assert "class Author(Base)" in out
    assert "TOOLS:" in out


def test_render_with_path_template(base, tmp_path: Path):
    path = tmp_path / "prompt.jinja"
    path.write_text(_MINIMAL_TEMPLATE)
    out = render(base=base, tools=[], template=path)
    assert "class Book(Base)" in out


@pytest.mark.parametrize("missing", ["SCHEMA", "TOOLS", "IMPORTS"])
def test_render_warns_on_missing_marker(base, missing: str):
    template = _MINIMAL_TEMPLATE.replace("{{ " + missing + " }}", "")
    with pytest.warns(LLMAlchemyPromptWarning, match=missing):
        render(base=base, tools=[], template=template)


def test_render_tools_section_empty_when_no_tools(base):
    out = render(
        base=base,
        tools=[],
        template=_MINIMAL_TEMPLATE,
    )
    # The TOOLS section is present in the template but has no bullets.
    assert "TOOLS:\n" in out


def test_render_imports_reports_policy(base):
    forbidden = render(base=base, tools=[], allowed_imports=[])
    assert "import` statements are forbidden" in forbidden

    allowed = render(base=base, tools=[], allowed_imports=["sqlalchemy", "datetime"])
    assert "`sqlalchemy`" in allowed
    assert "`datetime`" in allowed


def test_render_references_lists_allowed_tables(base):
    out = render(base=base, tools=[], referenceable_tables=["authors", "books"])
    assert "`authors`" in out
    assert "`books`" in out
    # Lowercase concrete example, matching the snake_case table names.
    assert "[authors:row_pk]" in out


def test_render_appends_system_prompt_extension_at_the_end(base):
    out = render(base=base, tools=[], system_prompt_extension="Always answer in Spanish.")
    assert out.rstrip().endswith("Always answer in Spanish.")


def test_render_system_prompt_extension_absent_by_default(base):
    out = render(base=base, tools=[])
    assert "Always answer" not in out


def test_render_references_absent_by_default(base):
    out = render(base=base, tools=[])
    assert "row_pk" not in out


def test_render_references_rejects_unknown_table(base):
    with pytest.raises(ValueError, match="Unknown referenceable table"):
        render(base=base, tools=[], referenceable_tables=["nope"])


def test_render_schema_shows_whole_module_including_junctions(advanced_base):
    out = render(base=advanced_base, tools=[])

    # The junction ``Table(...)`` is part of the module source, so the agent
    # sees its variable name and columns, not just the mapped classes.
    assert "team_members = Table(" in out
    assert 'Column("employee_id", ForeignKey("employees.id")' in out
    # Inherited classes are shown too.
    assert "class Manager(Employee)" in out
