"""Tests for the serialize / deserialize round-trip."""

import pytest
from sqlalchemy.exc import IntegrityError

from llmalchemy.agent import State, _init_session
from llmalchemy.database import deserialize, serialize


def _agent_session(base):
    """The session ``agent.run`` creates for itself."""
    state = State()
    _init_session(state, base)
    return state.session


_FK_SESSIONS = [
    pytest.param(_agent_session, id="agent"),
    pytest.param(lambda base: deserialize(data={}, base=base), id="deserialize"),
]


def test_serialize_seeded_session(base, seeded_session):
    data = serialize(session=seeded_session, base=base)

    assert set(data.keys()) == {"authors", "books"}
    assert len(data["authors"]) == 2
    assert len(data["books"]) == 4
    assert {a["name"] for a in data["authors"]} == {"Tolkien", "Dhalia de la Cerda"}


def test_roundtrip_preserves_rows(base, seeded_session):
    data = serialize(session=seeded_session, base=base)
    restored = deserialize(data=data, base=base)
    restored_data = serialize(session=restored, base=base)
    assert restored_data == data


def test_deserialize_empty_payload(base):
    session = deserialize(data={}, base=base)
    assert serialize(session=session, base=base) == {"authors": [], "books": []}


def test_deserialize_ignores_unknown_tables(base):
    session = deserialize(data={"ghosts": [{"id": 1}]}, base=base)
    # No crash, no rows; known tables still materialise as empty lists.
    assert serialize(session=session, base=base) == {"authors": [], "books": []}


def test_serialize_empty_session(base, session):
    assert serialize(session=session, base=base) == {"authors": [], "books": []}


# -- foreign-key enforcement -------------------------------------------


@pytest.mark.parametrize("make_session", _FK_SESSIONS)
def test_dangling_foreign_key_is_rejected(base, book_cls, make_session):
    session = make_session(base)
    session.add(book_cls(title="Orphan", author_id=999))
    with pytest.raises(IntegrityError):
        session.commit()


@pytest.mark.parametrize("make_session", _FK_SESSIONS)
def test_delete_parent_cascades_to_children(base, author_cls, book_cls, make_session):
    session = make_session(base)
    session.add(author_cls(name="Tolkien", books=[book_cls(title="LOTR")]))
    session.commit()

    session.delete(session.query(author_cls).one())
    session.commit()

    assert session.query(book_cls).all() == []
