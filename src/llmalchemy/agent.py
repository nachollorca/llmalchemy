"""Contains the agentic loop and related utils."""

import weakref
from collections.abc import Generator, Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from lmdk import Message, UserMessage, complete
from pydantic import BaseModel, Field, create_model
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session

from .code import execute, validate
from .context import render
from .database import association_tables, mapped_classes
from .tools import Tool, make_disclose_fn

MAX_LOOPS = 20


@dataclass
class State:
    """Contains the different objects whose state is modified through the agentic loop.

    Attributes:
        session: the sqlalchemy database connection
        messages: the conversation history
        namespace: symbols of the code environment that the agent uses
    """

    session: Session | None = None
    messages: list[Message] = field(default_factory=list)
    namespace: dict = field(default_factory=dict)


class Output(BaseModel):
    """Pydantic model to force the LM structured output."""

    message: str = Field(description="The response shown to the user.")
    code: str = Field(default="", description="The optional code to run.")


class Signal(StrEnum):
    """Signals emitted by the agentic loop to indicate current stage."""

    COMPLETION = "COMPLETION"
    VALIDATION = "VALIDATION"
    EXECUTION = "EXECUTION"
    EXCEEDED = "EXCEEDED"


@dataclass(frozen=True)
class Event:
    """Base class for all events yielded by the agentic loop."""


@dataclass(frozen=True)
class SignalEvent(Event):
    """A control-flow signal indicating the current stage."""

    signal: Signal


@dataclass(frozen=True)
class MessageEvent(Event):
    """A message appended to the conversation history."""

    message: Message


@dataclass(frozen=True)
class SystemInstructionEvent(Event):
    """The system instruction sent to the model."""

    content: str


def _complete(
    state: State,
    model: str,
    system_instruction: str,
    output_schema: type[Output],
) -> Generator[Event, None, Output]:
    """Single LM call: append the response, yield signals and the message, return parsed output."""
    yield SignalEvent(Signal.COMPLETION)
    response = complete(
        model=model,
        prompt=state.messages,
        system_instruction=system_instruction,
        output_schema=output_schema,
    )
    state.messages.append(response.message)
    yield MessageEvent(response.message)
    assert isinstance(response.output, Output)
    return response.output


def _build_output_schema(output_extensions: type[BaseModel] | None) -> type[Output]:
    """Build the structured-output schema used by the agent loop.

    When ``output_extensions`` is ``None``, the plain :class:`Output` model is
    returned. Otherwise, a dynamic subclass is created whose fields are the
    extension fields followed by ``message`` and ``code`` (in that order).

    Ordering matters: fields emitted earlier in the structured output act as a
    scratchpad for later fields (this is how chain-of-thought-in-schema works).
    Typical uses are reasoning slots (e.g. ``thoughts: str`` or ARQ-style
    ``user_intent`` / ``info_needed`` / ``info_missing``) and product fields
    (``confidence``, ``citations``, ``suggested_followups``, …). The agent loop
    only reads ``.message`` and ``.code``; extra fields ride along on the
    yielded message object for the caller to consume.
    """
    if output_extensions is None:
        return Output

    extension_fields = {
        name: (f.annotation, f) for name, f in output_extensions.model_fields.items()
    }
    base_fields = {name: (f.annotation, f) for name, f in Output.model_fields.items()}
    # ``create_model``'s overloads don't accept ``**kwargs`` unpacking, so we
    # cast to ``Any`` to silence the type checker without a per-call pragma.
    return cast(Any, create_model)("Output", **extension_fields, **base_fields)


def _init_session(state: State, base: type[DeclarativeBase]) -> None:
    """Initialize the SQLAlchemy session when missing (first call)."""
    if state.session is None:
        engine = create_engine("sqlite://")
        base.metadata.create_all(engine)
        state.session = Session(engine)
        # Dispose the engine (and close its pooled sqlite3.Connection) when
        # the session is garbage-collected, to avoid ResourceWarnings.
        weakref.finalize(state.session, engine.dispose)


def _init_namespace(
    state: State,
    base: type[DeclarativeBase],
    tools: list[Tool],
) -> dict[str, str]:
    """Populate or refresh the agent code execution namespace.

    On the first call the namespace is empty, so all symbols are injected:
    ``session``, ORM model classes, tool functions, and ``disclose``.
    On follow-up calls only ``session`` is refreshed because the database
    may have changed between calls (user side).

    Returns:
        A ``{name: description}`` dict of every injected **infrastructure**
        symbol.  Tool symbols are excluded — their source of truth is the
        ``Tool`` object itself, rendered separately by ``_render_tools_summary``.
    """
    descriptions: dict[str, str] = {}

    state.namespace["session"] = state.session
    descriptions["session"] = "a `sqlalchemy.orm.Session` connected to the database."

    orm_classes = mapped_classes(base)
    for cls in orm_classes:
        state.namespace[cls.__name__] = cls
    if orm_classes:
        names = ", ".join(cls.__name__ for cls in orm_classes)
        descriptions[names] = "ORM model classes (see schema above)."

    tables = association_tables(base)
    state.namespace.update(tables)
    if tables:
        names = ", ".join(tables)
        descriptions[names] = (
            "`sqlalchemy.Table` association objects for many-to-many junctions,"
            " usable directly (e.g. `session.execute(insert(table), rows)`)."
        )

    for t in tools:
        state.namespace[t.name] = t.fn

    if tools:
        state.namespace["disclose"] = make_disclose_fn(tools)
        descriptions["disclose"] = (
            "`disclose(name: str) -> str` — prints the full signature"
            " and docstring of a tool. Call it before using a tool you haven't seen yet."
        )

    return descriptions


def run(
    state: State,
    base: type[DeclarativeBase],
    model: str,
    tools: list[Tool] | None = None,
    allowed_imports: list[str] | None = None,
    prompt_template: str | Path | None = None,
    output_extensions: type[BaseModel] | None = None,
    thinking: bool = False,
) -> Iterator[Event]:
    """Execute the agentic loop.

    An intermediate turn is one where the assistant message requests to run ``.code``.
    The loop ends as soon as the assistant responds without code. Turn is returned to user.

    Args:
        state: Conversation, database state and python namespace (mutated in place).
        base: SQLAlchemy declarative base that defines the db schema.
        model: Model identifier forwarded to ``complete()``.
        tools: User-provided tools the agent can call in generated code.
        allowed_imports: Any vanilla module or third-party package that the agent can use.
        output_extensions: Optional Pydantic model to force in the LM structured output.
        thinking: Level of thinking for provider-native reasoning tokens. Not implemented yet.
        prompt_template: Custom jinja system prompt. Should contain placeholders for:
            - ``SCHEMA``: used to show agent the source code of ORM classes
            - ``SYMBOLS``: used to show ageent all pre-loaded namespace symbols.
            - ``TOOLS``: usedf to show the agent tool names + short descriptions.

    Yields:
        ``Event``: system instruction, loop signals, and conversation messages.
    """
    if thinking:
        raise NotImplementedError("Native provider thinking is not yet wired through lmdk.")

    # Initialize everything
    tools = tools or []
    allowed_imports = allowed_imports or []
    output_schema = _build_output_schema(output_extensions)
    _init_session(state, base)
    descriptions = _init_namespace(state, base, tools)
    system_instruction = render(base, tools, descriptions, prompt_template)
    yield SystemInstructionEvent(system_instruction)

    # First call to the model
    output = yield from _complete(state, model, system_instruction, output_schema)
    code = output.code

    # Loop until model is over with the task
    loops = 0
    while code:
        if loops >= MAX_LOOPS:
            yield SignalEvent(Signal.EXCEEDED)
            break
        loops += 1

        yield SignalEvent(Signal.VALIDATION)
        if reason := validate(source=code, allowed_imports=allowed_imports):
            message = UserMessage(f"Code rejected: {reason}")
            state.messages.append(message)
            yield MessageEvent(message)
            output = yield from _complete(state, model, system_instruction, output_schema)
            code = output.code
            continue

        yield SignalEvent(Signal.EXECUTION)
        result = execute(source=code, namespace=state.namespace)
        message = UserMessage(f"Execution result:\n{result}")
        state.messages.append(message)
        yield MessageEvent(message)
        output = yield from _complete(state, model, system_instruction, output_schema)
        code = output.code
