"""Shared fixtures for the whole test suite.

Conventions (see PLAN.md):
- Every test that needs the dummy schema goes through ``base`` / ``session`` /
  ``seeded_session`` here. No inline declarative bases in test modules.
- Every test that exercises the agent loop goes through ``fake_llm`` to
  script the LM output. No ad-hoc patching of ``lmdk.complete``.
"""

from dataclasses import dataclass, field
from typing import Any

import pytest
from lmdk.datatypes import CompletionResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from llmalchemy.agent import Output, State
from tests.fixtures.advanced import AdvancedBase
from tests.fixtures.joined import JoinedBase
from tests.fixtures.schema import Author, Base, Book, get_author_catalog

# -- schema / tool ------------------------------------------------------


@pytest.fixture(scope="session")
def base() -> type[Base]:
    return Base


@pytest.fixture(scope="session")
def advanced_base() -> type[AdvancedBase]:
    """Base with single-table inheritance (``Manager``) and a junction table."""
    return AdvancedBase


@pytest.fixture(scope="session")
def joined_base() -> type[JoinedBase]:
    """Base with joined-table inheritance (``Employee`` owns its own table)."""
    return JoinedBase


@pytest.fixture(scope="session")
def author_cls() -> type[Author]:
    return Author


@pytest.fixture(scope="session")
def book_cls() -> type[Book]:
    return Book


@pytest.fixture(scope="session")
def catalog_tool():
    return get_author_catalog


# -- database ----------------------------------------------------------


@pytest.fixture
def session():
    """A fresh in-memory SQLite session with ``Base.metadata`` created."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def seeded_session(session: Session) -> Session:
    """``session`` + 2 authors with 2 books each."""
    tolkien = Author(name="Tolkien", books=[Book(title="The Hobbit"), Book(title="LOTR")])
    dhalia = Author(
        name="Dhalia de la Cerda",
        books=[Book(title="Perras de reserva"), Book(title="Desde los zulos")],
    )
    session.add_all([tolkien, dhalia])
    session.commit()
    return session


# -- agent state -------------------------------------------------------


@pytest.fixture
def state() -> State:
    """A fresh ``State`` with no session attached."""
    return State()


@pytest.fixture
def ready_state(seeded_session: Session) -> State:
    """A ``State`` already wired to a seeded session (skips ``_init_session``)."""
    return State(session=seeded_session)


# -- fake LM -----------------------------------------------------------


@dataclass
class FakeLLM:
    """Scripted replacement for ``lmdk.complete`` used inside ``agent.run``.

    Instantiate via the ``fake_llm`` fixture. Queue outputs with ``reply()``
    (sugar) or pass real ``Output`` objects to the factory. Each call to the
    loop pops the next output FIFO and records the prompt on ``.calls``.
    """

    outputs: list[dict[str, Any]] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)

    def reply(self, message: str = "", code: str = "", **extras: Any) -> "FakeLLM":
        """Queue one response. Extras go into output-extension fields."""
        self.outputs.append({"message": message, "code": code, **extras})
        return self

    def __call__(
        self,
        *,
        model: str,
        prompt,
        system_instruction: str | None = None,
        output_schema=None,
        **_: Any,
    ) -> CompletionResponse:
        if not self.outputs:
            raise AssertionError("FakeLLM ran out of scripted outputs")
        self.calls.append(
            {
                "model": model,
                "prompt": list(prompt),
                "system": system_instruction,
                "output_schema": output_schema,
            }
        )
        data = self.outputs.pop(0)
        parsed = output_schema(**data) if output_schema is not None else Output(**data)
        return CompletionResponse(
            content=parsed.model_dump_json(),
            input_tokens=0,
            output_tokens=0,
            parsed=parsed,
        )


@pytest.fixture
def fake_llm(monkeypatch):
    """Factory that installs a ``FakeLLM`` in place of ``llmalchemy.agent.complete``."""

    def _make(*outputs: dict[str, Any]) -> FakeLLM:
        fake = FakeLLM(outputs=list(outputs))
        monkeypatch.setattr("llmalchemy.agent.complete", fake)
        return fake

    return _make
