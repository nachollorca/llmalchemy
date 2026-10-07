"""Unit tests for ``agent.py`` helpers (no loop / no LM)."""

import json

import pytest
from lmdk import UserMessage
from pydantic import BaseModel, Field

from llmalchemy.agent import (
    DatabaseChangesEvent,
    MessageEvent,
    Output,
    Signal,
    SignalEvent,
    SystemInstructionEvent,
    _build_output_schema,
    _init_namespace,
)
from llmalchemy.code import execute, validate
from llmalchemy.database import RowUpdate, TableChanges, new_session
from llmalchemy.tools import Tool
from tests.fixtures.advanced import Manager, team_members

# -- Event.to_dict -----------------------------------------------------


def test_event_to_dict_tags_type_and_is_json_serializable():
    events = [
        SignalEvent(Signal.EXECUTION),
        SystemInstructionEvent(content="you are a coding agent"),
        MessageEvent(UserMessage(content="hello")),
        DatabaseChangesEvent(
            changes={
                "books": TableChanges(
                    added=[{"id": 1, "title": "The Hobbit"}],
                    updated=[
                        RowUpdate(before={"id": 2, "title": "x"}, after={"id": 2, "title": "y"})
                    ],
                    deleted=[],
                )
            }
        ),
    ]
    for event in events:
        data = event.to_dict()
        assert data["type"] == type(event).__name__
        json.dumps(data)  # plain JSON types, no dataclasses/enums leaking through


def test_event_to_dict_flattens_nested_changes():
    event = DatabaseChangesEvent(
        changes={
            "books": TableChanges(
                added=[{"id": 1}],
                updated=[RowUpdate(before={"id": 2, "title": "x"}, after={"id": 2, "title": "y"})],
                deleted=[],
            )
        }
    )
    changes = event.to_dict()["changes"]
    assert changes["books"]["added"] == [{"id": 1}]
    assert changes["books"]["updated"] == [
        {"before": {"id": 2, "title": "x"}, "after": {"id": 2, "title": "y"}}
    ]
    assert changes["books"]["deleted"] == []


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


# -- _init_namespace --------------------------------------------------


def test_init_namespace_injects_all_symbols(base, seeded_session, catalog_tool):
    namespace, descriptions = _init_namespace(seeded_session, base, [catalog_tool])

    assert namespace["session"] is seeded_session
    for cls in base.__subclasses__():
        assert namespace[cls.__name__] is cls
    assert namespace["get_author_catalog"] is catalog_tool.fn
    assert callable(namespace["disclose"])

    assert "session" in descriptions
    assert "disclose" in descriptions
    # Tool names are NOT in descriptions (they're rendered separately).
    assert "get_author_catalog" not in descriptions


def test_init_namespace_without_tools_skips_disclose(base, seeded_session):
    namespace, descriptions = _init_namespace(seeded_session, base, [])
    assert "disclose" not in namespace
    assert "disclose" not in descriptions


def test_init_namespace_injects_inherited_classes_and_junctions(advanced_base):
    namespace, descriptions = _init_namespace(new_session(advanced_base), advanced_base, [])

    # ``Manager`` is a grandchild of the base, invisible to ``__subclasses__()``.
    assert namespace["Manager"] is Manager
    # Junctions are bound to their Python variable name, not their table name.
    assert namespace["team_members"] is team_members
    assert "memberships" not in namespace
    assert any("Manager" in name for name in descriptions)
    assert any("team_members" in name for name in descriptions)


def test_agent_code_can_insert_into_junction(advanced_base):
    namespace, _ = _init_namespace(new_session(advanced_base), advanced_base, [])
    source = (
        "from sqlalchemy import insert, select\n"
        "session.add_all([Manager(name='Ada'), Team(name='Core')])\n"
        "session.flush()\n"
        "session.execute(insert(team_members), [{'employee_id': 1, 'team_id': 1}])\n"
        "print(session.execute(select(team_members)).all())\n"
    )
    assert validate(source=source, allowed_imports=["sqlalchemy"]) == ""
    assert execute(source=source, namespace=namespace).strip() == "[(1, 1)]"


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
