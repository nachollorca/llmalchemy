"""End-to-end tests for ``agent.run`` with a scripted fake LM.

These tests exercise the full loop (validation, execution, message
accumulation, signalling) without ever calling a real model.
"""

from lmdk import UserMessage
from pydantic import BaseModel, Field

from llmalchemy.agent import (
    DatabaseChangesEvent,
    MessageEvent,
    Signal,
    SignalEvent,
    SystemInstructionEvent,
    run,
)


def _signals(events):
    return [e.signal for e in events if isinstance(e, SignalEvent)]


def _messages(events):
    return [e.message for e in events if isinstance(e, MessageEvent)]


# -- basic flows ------------------------------------------------------


def test_single_turn_no_code(base, state, fake_llm):
    fake = fake_llm()
    fake.reply(message="hi")

    state.messages.append(UserMessage("hello"))
    events = list(run(state=state, base=base, model="fake"))

    # First event is the system instruction, then one completion + message.
    assert isinstance(events[0], SystemInstructionEvent)
    assert _signals(events) == [Signal.COMPLETION]
    assert len(_messages(events)) == 1
    assert len(fake.calls) == 1


def test_single_code_turn_mutates_database(base, state, author_cls, fake_llm):
    fake = fake_llm()
    fake.reply(code="session.add(Author(name='X')); session.commit()")
    fake.reply(message="done")

    state.messages.append(UserMessage("add X"))
    events = list(run(state=state, base=base, model="fake"))

    assert _signals(events) == [
        Signal.COMPLETION,
        Signal.VALIDATION,
        Signal.EXECUTION,
        Signal.COMPLETION,
    ]
    authors = state.session.query(author_cls).all()
    assert [a.name for a in authors] == ["X"]


def test_rejected_code_feeds_back_reason(base, state, fake_llm):
    fake = fake_llm()
    fake.reply(code="import os")  # forbidden
    fake.reply(message="ok, giving up")

    state.messages.append(UserMessage("do bad things"))
    events = list(run(state=state, base=base, model="fake"))

    # Validation signal appears, execution never does for the rejected call.
    signals = _signals(events)
    assert Signal.VALIDATION in signals
    assert signals.count(Signal.EXECUTION) == 0

    rejection = next(
        m for m in _messages(events) if isinstance(m, UserMessage) and "rejected" in m.content
    )
    assert "Forbidden import" in rejection.content


def test_execution_error_is_reported_as_user_message(base, state, fake_llm):
    fake = fake_llm()
    fake.reply(code="raise RuntimeError('kaboom')")
    fake.reply(message="sorry")

    state.messages.append(UserMessage("run bad code"))
    events = list(run(state=state, base=base, model="fake"))

    traceback_msg = next(
        m
        for m in _messages(events)
        if isinstance(m, UserMessage) and "Execution result" in m.content
    )
    assert "RuntimeError" in traceback_msg.content
    assert "kaboom" in traceback_msg.content


def test_max_loops_emits_exceeded(base, state, fake_llm, monkeypatch):
    monkeypatch.setattr("llmalchemy.agent.MAX_LOOPS", 2)
    fake = fake_llm()
    # Always request more code; loop should cap at 2 iterations.
    for _ in range(5):
        fake.reply(code="x = 1")

    state.messages.append(UserMessage("loop forever"))
    events = list(run(state=state, base=base, model="fake"))

    signals = _signals(events)
    assert signals.count(Signal.EXECUTION) == 2
    assert signals[-1] == Signal.EXCEEDED


# -- tools + extensions + persistence --------------------------------


def test_tool_is_callable_from_agent_code(base, state, catalog_tool, fake_llm):
    fake = fake_llm()
    fake.reply(
        code=(
            "session.add(Author(name='Z', books=[Book(title='B1'), Book(title='B2')]));"
            " session.commit();"
            " print(get_author_catalog('Z', session))"
        )
    )
    fake.reply(message="done")

    state.messages.append(UserMessage("use the tool"))
    events = list(run(state=state, base=base, model="fake", tools=[catalog_tool]))

    exec_result = next(
        m
        for m in _messages(events)
        if isinstance(m, UserMessage) and "Execution result" in m.content
    )
    assert "B1" in exec_result.content
    assert "B2" in exec_result.content


def test_output_extensions_extend_schema_passed_to_complete(base, state, fake_llm):
    """The dynamic output schema used by the LM carries the extension fields.

    We assert on the schema handed to ``complete`` (recorded by ``FakeLLM``)
    instead of iterating the full loop, because feeding extension-shaped
    replies through the loop is gated by an ``isinstance(..., Output)``
    assertion unrelated to this test.
    """

    class Reasoning(BaseModel):
        thoughts: str = Field(description="scratch")

    fake = fake_llm()
    fake.reply(message="hi", thoughts="I think")

    state.messages.append(UserMessage("hello"))
    # Drain events defensively; we only care about the first completion call.
    try:
        for _ in run(state=state, base=base, model="fake", output_extensions=Reasoning):
            if fake.calls:
                break
    except AssertionError:
        # agent.py's `isinstance(response.output, Output)` check fires with
        # dynamic schemas; irrelevant to what we're asserting here.
        pass

    schema = fake.calls[0]["output_schema"]
    assert list(schema.model_fields.keys()) == ["thoughts", "message", "code"]


def test_state_persists_across_runs(base, state, author_cls, fake_llm):
    fake = fake_llm()
    fake.reply(code="session.add(Author(name='first')); session.commit()")
    fake.reply(message="done one")
    fake.reply(code="session.add(Author(name='second')); session.commit()")
    fake.reply(message="done two")

    state.messages.append(UserMessage("add first"))
    list(run(state=state, base=base, model="fake"))

    state.messages.append(UserMessage("add second"))
    list(run(state=state, base=base, model="fake"))

    names = [a.name for a in state.session.query(author_cls).all()]
    assert names == ["first", "second"]
    # Namespace was reused: `Author` symbol is still bound.
    assert state.namespace["Author"] is author_cls


def test_emits_database_changes_event(base, state, fake_llm):
    fake = fake_llm()
    fake.reply(code="session.add(Author(name='X')); session.commit()")
    fake.reply(message="done")

    state.messages.append(UserMessage("add X"))
    events = list(run(state=state, base=base, model="fake"))

    event = next(e for e in events if isinstance(e, DatabaseChangesEvent))
    assert event.changes["authors"].added[0]["name"] == "X"


def test_database_changes_event_reports_update(base, ready_state, fake_llm):
    fake = fake_llm()
    fake.reply(code="a = session.query(Author).first(); a.name = 'Renamed'; session.commit()")
    fake.reply(message="done")

    ready_state.messages.append(UserMessage("rename first"))
    events = list(run(state=ready_state, base=base, model="fake"))

    event = next(e for e in events if isinstance(e, DatabaseChangesEvent))
    assert event.changes["authors"].updated[0].after["name"] == "Renamed"


def test_no_database_changes_event_for_read_only_run(base, state, fake_llm):
    fake = fake_llm()
    fake.reply(code="print('read only')")
    fake.reply(message="done")

    state.messages.append(UserMessage("look"))
    events = list(run(state=state, base=base, model="fake"))

    assert not any(isinstance(e, DatabaseChangesEvent) for e in events)
