"""Tests for the tool wrapper, decorator and disclose closure."""

from llmalchemy.tools import Tool, make_disclose_fn, tool


def _with_doc(a: int, b: str) -> str:
    """Do a thing.

    Extra details on a second line.
    """
    return f"{a}{b}"


def _no_doc(x):
    return x


def test_from_function_extracts_name_and_descriptions():
    t = Tool.from_function(_with_doc)
    assert t.name == "_with_doc"
    assert t.short_description == "Do a thing."
    assert "def _with_doc(a: int, b: str) -> str:" in t.full_description
    assert "Extra details on a second line." in t.full_description
    assert t.fn is _with_doc


def test_from_function_without_docstring():
    t = Tool.from_function(_no_doc)
    assert t.name == "_no_doc"
    assert t.short_description == ""
    assert t.full_description.startswith("def _no_doc(")
    assert '"""' not in t.full_description


def test_tool_decorator_matches_from_function():
    @tool
    def _decorated(x: int) -> int:
        """Double it."""
        return x * 2

    assert isinstance(_decorated, Tool)
    assert _decorated.name == "_decorated"
    assert _decorated.short_description == "Double it."


def test_disclose_returns_full_description_for_known_tool():
    t = Tool.from_function(_with_doc)
    disclose = make_disclose_fn([t])
    assert disclose("_with_doc") == t.full_description


def test_disclose_reports_unknown_tool_with_available_list():
    t = Tool.from_function(_with_doc)
    disclose = make_disclose_fn([t])
    out = disclose("missing")
    assert "Unknown tool" in out
    assert "_with_doc" in out


def test_disclose_with_no_tools():
    disclose = make_disclose_fn([])
    out = disclose("anything")
    assert "Unknown tool" in out
    assert "(none)" in out


def test_catalog_tool_fixture_is_a_tool(catalog_tool):
    assert isinstance(catalog_tool, Tool)
    assert catalog_tool.name == "get_author_catalog"


def test_disclose_accepts_function_object():
    t = tool(_with_doc)
    disclose = make_disclose_fn([t])
    assert disclose(_with_doc) == t.full_description
