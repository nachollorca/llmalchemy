"""Tests for the serialize / deserialize round-trip."""

from typing import cast

import pytest
from sqlalchemy import Column, MetaData, String, Table, insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Session

from llmalchemy.agent import State, _init_session
from llmalchemy.database import deserialize, diff, serialize
from tests.fixtures.advanced import Manager, Team, team_members
from tests.fixtures.joined import Employee


def _agent_session(base):
    """The session ``agent.run`` creates for itself."""
    state = State()
    _init_session(state, base)
    return state.session


def _snapshot(session: Session, base) -> dict[str, list[dict]]:
    """``serialize`` with the dead-session ``None`` narrowed away for assertions."""
    data = serialize(session=session, base=base)
    assert data is not None
    return data


_FK_SESSIONS = [
    pytest.param(_agent_session, id="agent"),
    pytest.param(lambda base: deserialize(data={}, base=base), id="deserialize"),
]


def test_serialize_seeded_session(base, seeded_session):
    data = _snapshot(seeded_session, base)

    assert set(data.keys()) == {"authors", "books"}
    assert len(data["authors"]) == 2
    assert len(data["books"]) == 4
    assert {a["name"] for a in data["authors"]} == {"Tolkien", "Dhalia de la Cerda"}


def test_serialize_dead_session_returns_none(base, book_cls):
    session = _agent_session(base)
    session.add(book_cls(title="Orphan", author_id=999))
    with pytest.raises(IntegrityError):
        session.flush()

    assert serialize(session=session, base=base) is None
    assert serialize(session=None, base=base) is None


def test_roundtrip_preserves_rows(base, seeded_session):
    data = _snapshot(seeded_session, base)
    restored = deserialize(data=data, base=base)
    restored_data = _snapshot(restored, base)
    assert restored_data == data


def test_deserialize_empty_payload(base):
    session = deserialize(data={}, base=base)
    assert _snapshot(session, base) == {"authors": [], "books": []}


def test_deserialize_ignores_unknown_tables(base):
    session = deserialize(data={"ghosts": [{"id": 1}]}, base=base)
    # No crash, no rows; known tables still materialise as empty lists.
    assert _snapshot(session, base) == {"authors": [], "books": []}


def test_serialize_empty_session(base, session):
    assert _snapshot(session, base) == {"authors": [], "books": []}


def test_roundtrip_single_table_inheritance(advanced_base):
    session = deserialize(data={}, base=advanced_base)
    session.add(Manager(name="Ada"))
    session.commit()

    data = _snapshot(session, advanced_base)
    # One entry per table: ``Manager`` shares ``Employee``'s table, no duplicates.
    assert set(data) == {"employees", "teams", "memberships"}
    assert data["employees"] == [{"id": 1, "name": "Ada", "role": "manager"}]
    assert data["memberships"] == []

    restored = deserialize(data=data, base=advanced_base)
    assert _snapshot(restored, advanced_base) == data
    assert restored.query(Manager).count() == 1


def test_roundtrip_joined_table_inheritance(joined_base):
    session = deserialize(data={}, base=joined_base)
    session.add(Employee(name="Ada", salary=100))
    session.commit()

    data = _snapshot(session, joined_base)
    # Both tables are captured: the subclass salary lives in its own table.
    assert data["people"] == [{"id": 1, "kind": "employee", "name": "Ada"}]
    assert data["employees"] == [{"id": 1, "salary": 100}]

    restored = deserialize(data=data, base=joined_base)
    assert _snapshot(restored, joined_base) == data
    assert restored.query(Employee).one().salary == 100


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


# -- diff --------------------------------------------------------------


def test_diff_detects_added_updated_deleted_rows(base, seeded_session, author_cls, book_cls):
    before = _snapshot(seeded_session, base)

    renamed = seeded_session.query(author_cls).first()
    renamed.name = "Renamed"
    seeded_session.delete(seeded_session.query(book_cls).first())
    seeded_session.add(author_cls(name="New"))
    seeded_session.commit()

    changes = diff(before=before, after=_snapshot(seeded_session, base), base=base)

    assert [(u.before["name"], u.after["name"]) for u in changes["authors"].updated] == [
        ("Tolkien", "Renamed")
    ]
    assert [row["name"] for row in changes["authors"].added] == ["New"]
    assert len(changes["books"].deleted) == 1


def test_diff_identical_snapshots_is_empty(base, seeded_session):
    before = _snapshot(seeded_session, base)
    assert diff(before=before, after=before, base=base) == {}


def test_diff_uses_composite_primary_key(advanced_base):
    session = deserialize(data={}, base=advanced_base)
    before = _snapshot(session, advanced_base)

    session.add(Manager(name="Ada"))
    session.add(Team(name="Core"))
    session.commit()
    session.execute(insert(team_members), [{"employee_id": 1, "team_id": 1}])
    session.commit()

    changes = diff(before=before, after=_snapshot(session, advanced_base), base=advanced_base)
    assert changes["memberships"].added == [{"employee_id": 1, "team_id": 1}]


def test_diff_skips_tables_without_primary_key():
    metadata = MetaData()
    Table("logs", metadata, Column("message", String))
    fake_base = cast("type[DeclarativeBase]", type("FakeBase", (), {"metadata": metadata}))

    changes = diff(
        before={"logs": [{"message": "a"}]},
        after={"logs": [{"message": "a"}, {"message": "b"}]},
        base=fake_base,
    )
    assert changes == {}
