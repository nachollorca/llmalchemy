"""Contains the utilities that access or modify the database."""

import sys
import weakref

from sqlalchemy import Table, create_engine, insert, select
from sqlalchemy.orm import DeclarativeBase, Session


def mapped_classes(base: type[DeclarativeBase]) -> list[type[DeclarativeBase]]:
    """Return every class mapped under *base*, at any inheritance depth.

    ``base.__subclasses__()`` yields direct subclasses only, so the mapped
    classes of inheritance hierarchies (``class Manager(Employee)``) are
    missed.
    """
    return sorted((m.class_ for m in base.registry.mappers), key=lambda cls: cls.__name__)


def association_tables(base: type[DeclarativeBase]) -> dict[str, Table]:
    """Return ``{name: Table}`` for every table of ``base`` with no mapped class.

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

    for table in base.metadata.sorted_tables:
        rows = data.get(table.name)
        if rows:
            session.execute(insert(table), rows)

    session.commit()
    return session


def serialize(session: Session, base: type[DeclarativeBase]) -> dict[str, list[dict]]:
    """Freeze the current database state into a JSON-serializable dict.

    Args:
        session: The active session to read from.
        base: The declarative base whose metadata describes the schema.

    Returns:
        ``{table_name: [row_dict, ...]}`` for every table in the schema.
    """
    # Snapshot at the table level: classes are not tables. Single-table
    # inheritance would duplicate rows if walked per class, and joined-table
    # inheritance would drop the subclass table entirely.
    result: dict[str, list[dict]] = {}
    for table in base.metadata.sorted_tables:
        rows = session.execute(select(table)).all()
        result[table.name] = [dict(row._mapping) for row in rows]
    return result
