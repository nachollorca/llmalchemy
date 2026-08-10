"""Contains the utilities that access or modify the database."""

import sys
import weakref
from typing import Any

from sqlalchemy import Table, create_engine
from sqlalchemy.orm import DeclarativeBase, Session


def mapped_classes(base: type[DeclarativeBase]) -> list[Any]:
    """Return every class mapped under *base*, at any inheritance depth.

    ``base.__subclasses__()`` yields direct subclasses only, so the mapped
    classes of inheritance hierarchies (``class Manager(Employee)``) are
    missed. The mapper registry knows them all; it is an unordered set, hence
    the sort by class name to keep the rendered prompt stable across runs.
    """
    return sorted((m.class_ for m in base.registry.mappers), key=lambda cls: cls.__name__)


def _root_classes(base: type[DeclarativeBase]) -> list[Any]:
    """Return the base-most mapped class of every hierarchy under *base*.

    Used for (de)serialization: the rows of a subclass mapper already travel
    with its root mapper (whose polymorphic query returns them), so taking
    both would duplicate rows.
    """
    return [cls for cls in mapped_classes(base) if cls.__mapper__.inherits is None]


def association_tables(base: type[DeclarativeBase]) -> dict[str, Table]:
    """Return ``{name: Table}`` for every table of *base* with no mapped class.

    Those are the ``Table(...)`` M:N junctions. The name is the Python variable
    the table is bound to in the module declaring *base*, falling back to the
    table name.
    """
    mapped = {table.name for m in base.registry.mappers for table in m.tables}
    module = sys.modules.get(base.__module__)
    # ponytail: only the module declaring `base` is scanned for variable names;
    # junctions declared elsewhere fall back to their table name.
    variables = {id(v): k for k, v in vars(module).items()} if module else {}
    return {
        variables.get(id(table), table.name): table
        for table in base.metadata.tables.values()
        if table.name not in mapped
    }


def deserialize(data: dict[str, list[dict]], base: type[DeclarativeBase]) -> Session:
    """Unpack a JSON-serialised database state into an SQLAlchemy session.

    Creates an in-memory SQLite database, issues ``Base.metadata.create_all``,
    and populates every table from *data*.

    Args:
        data: Mapping of ``{table_name: [row_dict, ...]}``.
        base: The declarative base whose metadata describes the schema.

    Returns:
        A ready-to-use SQLAlchemy ``Session`` bound to the in-memory database.
    """
    engine = create_engine("sqlite://")
    base.metadata.create_all(engine)
    session = Session(engine)
    # Ensure the underlying sqlite3.Connection is closed when the session
    # becomes unreachable, avoiding Python 3.13 ResourceWarnings.
    weakref.finalize(session, engine.dispose)

    # Build a lookup from table name to mapped class
    cls_by_table: dict[str, Any] = {cls.__table__.name: cls for cls in _root_classes(base)}

    for table_name, rows in data.items():
        cls = cls_by_table.get(table_name)
        if cls is None:
            continue
        for row in rows:
            session.add(cls(**row))

    session.commit()
    return session


def serialize(session: Session, base: type[DeclarativeBase]) -> dict[str, list[dict]]:
    """Freeze the current database state into a JSON-serialisable dict.

    Args:
        session: The active session to read from.
        base: The declarative base whose metadata describes the schema.

    Returns:
        ``{table_name: [row_dict, ...]}`` for every table in the schema.
    """
    result: dict[str, list[dict]] = {}
    for cls in _root_classes(base):
        table_name = cls.__table__.name
        columns = [c.key for c in cls.__table__.columns]
        rows = session.query(cls).all()
        result[table_name] = [{col: getattr(row, col) for col in columns} for row in rows]
    return result
