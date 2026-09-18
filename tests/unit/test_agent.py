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
)
from llmalchemy.code import execute, validate
from llmalchemy.tools import Tool
from tests.fixtures.advanced import Manager, team_members

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


def test_init_namespace_injects_inherited_classes_and_junctions(advanced_base):
    state = State()
    _init_session(state, advanced_base)
    descriptions = _init_namespace(state, advanced_base, [])

    # ``Manager`` is a grandchild of the base, invisible to ``__subclasses__()``.
    assert state.namespace["Manager"] is Manager
    # Junctions are bound to their Python variable name, not their table name.
    assert state.namespace["team_members"] is team_members
    assert "memberships" not in state.namespace
    assert any("Manager" in name for name in descriptions)
    assert any("team_members" in name for name in descriptions)


def test_agent_code_can_insert_into_junction(advanced_base):
    state = State()
    _init_session(state, advanced_base)
    _init_namespace(state, advanced_base, [])
    source = (
        "from sqlalchemy import insert, select\n"
        "session.add_all([Manager(name='Ada'), Team(name='Core')])\n"
        "session.flush()\n"
        "session.execute(insert(team_members), [{'employee_id': 1, 'team_id': 1}])\n"
        "print(session.execute(select(team_members)).all())\n"
    )
    assert validate(source=source, allowed_imports=["sqlalchemy"]) == ""
    assert execute(source=source, namespace=state.namespace).strip() == "[(1, 1)]"


# -- run() early-exits ------------------------------------------------
def test_tool_class_is_used_by_agent(catalog_tool):
    # Sanity: the fixture is shaped the way agent.py expects.
    assert isinstance(catalog_tool, Tool)
    assert callable(catalog_tool.fn)


# -- telemetry --------------------------------------------------------
def test_run_span_parents_completion_spans():
    pytest.importorskip("opentelemetry.sdk")
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    from llmalchemy.agent import _run_span

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    with _run_span("some:model"), trace.get_tracer("lmdk").start_as_current_span("chat x"):
        pass

    child, root = exporter.get_finished_spans()
    assert child.context.trace_id == root.context.trace_id
    parent = child.parent
    assert parent is not None
    assert parent.span_id == root.context.span_id
