"""Tests for the serialize / deserialize round-trip."""

from llmalchemy.database import deserialize, serialize
from tests.fixtures.advanced import Manager


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


def test_roundtrip_single_table_inheritance(advanced_base):
    session = deserialize(data={}, base=advanced_base)
    session.add(Manager(name="Ada"))
    session.commit()

    data = serialize(session=session, base=advanced_base)
    # One entry per table: ``Manager`` shares ``Employee``'s table, no duplicates.
    assert set(data) == {"employees", "teams"}
    assert data["employees"] == [{"id": 1, "name": "Ada", "role": "manager"}]

    restored = deserialize(data=data, base=advanced_base)
    assert serialize(session=restored, base=advanced_base) == data
    assert restored.query(Manager).count() == 1
