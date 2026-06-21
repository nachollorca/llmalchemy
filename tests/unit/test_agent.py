"""Unit tests for ``agent.py`` helpers (no loop / no LM)."""

from typing import Any, cast

import pytest
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from llmalchemy.agent import (
    Output,
    State,
    _build_output_schema,
    _init_namespace,
    _init_session,
    run,
)
from llmalchemy.tools import Tool

# -- _build_output_schema ---------------------------------------------


def test_build_output_schema_without_extensions_returns_output():
    assert _build_output_schema(None) is Output


def test_build_output_schema_with_extensions_orders_fields_first():
    class Reasoning(BaseModel):
        thoughts: str = Field(description="scratch")
        confidence: float = 0.0

    schema = _build_output_schema(Reasoning)
    names = list(schema.model_fields.keys())
    # Extensions come first, then message, then code.
    assert names == ["thoughts", "confidence", "message", "code"]


def test_build_output_schema_preserves_base_fields():
    class Ext(BaseModel):
        tag: str = ""

    schema = _build_output_schema(Ext)
    instance = schema.model_validate({"tag": "t", "message": "m", "code": "c"})
    dumped = instance.model_dump()
    assert dumped["tag"] == "t"
    assert instance.message == "m"
    assert instance.code == "c"


# -- _init_session ----------------------------------------------------


def test_init_session_creates_sqlite_when_missing(base):
    state = State()
    _init_session(state, base)
    assert isinstance(state.session, Session)
    # Schema was applied: querying the mapped classes doesn't error.
    for cls in base.__subclasses__():
        assert state.session.query(cls).all() == []


def test_init_session_reuses_existing_session(base, seeded_session):
    state = State(session=seeded_session)
    _init_session(state, base)
    assert state.session is seeded_session


# -- _init_namespace --------------------------------------------------


def test_init_namespace_injects_all_symbols(base, seeded_session, catalog_tool):
    state = State(session=seeded_session)
    descriptions = _init_namespace(state, base, [catalog_tool])

    assert state.namespace["session"] is seeded_session
    for cls in base.__subclasses__():
        assert state.namespace[cls.__name__] is cls
    assert state.namespace["get_author_catalog"] is catalog_tool.fn
    assert callable(state.namespace["disclose"])

    assert "session" in descriptions
    assert "disclose" in descriptions
    # Tool names are NOT in descriptions (they're rendered separately).
    assert "get_author_catalog" not in descriptions


def test_init_namespace_without_tools_skips_disclose(base, seeded_session):
    state = State(session=seeded_session)
    descriptions = _init_namespace(state, base, [])
    assert "disclose" not in state.namespace
    assert "disclose" not in descriptions


def test_init_namespace_second_call_refreshes_session(base, seeded_session):
    state = State(session=seeded_session)
    _init_namespace(state, base, [])
    # Simulate a user-side db swap between runs.
    new_session = object()
    state.session = cast(Any, new_session)
    _init_namespace(state, base, [])
    assert state.namespace["session"] is new_session


# -- run() early-exits ------------------------------------------------


def test_run_with_thinking_raises_not_implemented(base):
    state = State()
    gen = run(state=state, base=base, model="x", thinking=True)
    with pytest.raises(NotImplementedError):
        next(gen)


def test_tool_class_is_used_by_agent(catalog_tool):
    # Sanity: the fixture is shaped the way agent.py expects.
    assert isinstance(catalog_tool, Tool)
    assert callable(catalog_tool.fn)
