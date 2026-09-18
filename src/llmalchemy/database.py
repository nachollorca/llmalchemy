"""Contains the utilities that access or modify the database."""

import sys
import weakref
from dataclasses import dataclass

from sqlalchemy import Table, create_engine, event, insert, select
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


def _enable_foreign_keys(dbapi_connection, _record) -> None:
    """Turn on FK enforcement, which SQLite leaves off on every new connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def new_session(base: type[DeclarativeBase]) -> Session:
    """Create a session on a fresh in-memory SQLite database with *base*'s schema.

    Foreign keys are enforced, so cascades and dangling references behave like
    they would on the consumer's real database instead of being ignored.

    Args:
        base: The declarative base whose metadata describes the schema.

    Returns:
        A ready-to-use SQLAlchemy ``Session``.
    """
    engine = create_engine("sqlite://")
    event.listen(engine, "connect", _enable_foreign_keys)
    base.metadata.create_all(engine)
    session = Session(engine)
    # Ensure the underlying sqlite3.Connection is closed when the session
    # becomes unreachable, avoiding Python 3.13 ResourceWarnings.
    weakref.finalize(session, engine.dispose)
    return session


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
    session = new_session(base)

    for table in base.metadata.sorted_tables:
        rows = data.get(table.name)
        if rows:
            session.execute(insert(table), rows)

    session.commit()
    return session


def serialize(session: Session | None, base: type[DeclarativeBase]) -> dict[str, list[dict]] | None:
    """Freeze the current database state into a JSON-serializable dict.

    Snapshots are taken with autoflush disabled, so pending ORM work stays
    pending instead of being flushed as a side effect of reading.

    Args:
        session: The active session to read from, or ``None``.
        base: The declarative base whose metadata describes the schema.

    Returns:
        ``{table_name: [row_dict, ...]}`` for every table in the schema, or
        ``None`` when the session is missing or its transaction is dead, where
        reading would raise ``PendingRollbackError``.
    """
    if session is None or not session.is_active:
        return None
    # Snapshot at the table level: classes are not tables. Single-table
    # inheritance would duplicate rows if walked per class, and joined-table
    # inheritance would drop the subclass table entirely.
    result: dict[str, list[dict]] = {}
    with session.no_autoflush:
        for table in base.metadata.sorted_tables:
            rows = session.execute(select(table)).all()
            result[table.name] = [dict(row._mapping) for row in rows]
    return result


@dataclass(frozen=True)
class RowUpdate:
    """A row's serialized state before and after an update."""

    before: dict
    after: dict


@dataclass(frozen=True)
class TableChanges:
    """Row-level changes to one table, rows identified by primary key."""

    added: list[dict]
    updated: list[RowUpdate]
    deleted: list[dict]


def _rows_by_key(table: Table, snapshot: dict[str, list[dict]]) -> dict[tuple, dict]:
    """Index a snapshot's rows for *table* by their primary-key tuple."""
    names = [column.name for column in table.primary_key.columns]
    return {tuple(row[name] for name in names): row for row in snapshot.get(table.name, [])}


def _table_diff(
    table: Table,
    before: dict[str, list[dict]],
    after: dict[str, list[dict]],
) -> TableChanges | None:
    """Diff one PK-bearing table, or ``None`` when nothing changed."""
    old = _rows_by_key(table, before)
    new = _rows_by_key(table, after)
    added = [new[key] for key in new.keys() - old.keys()]
    deleted = [old[key] for key in old.keys() - new.keys()]
    updated = [
        RowUpdate(before=old[key], after=new[key])
        for key in old.keys() & new.keys()
        if old[key] != new[key]
    ]
    if not (added or updated or deleted):
        return None
    return TableChanges(added=added, updated=updated, deleted=deleted)


def diff(
    before: dict[str, list[dict]],
    after: dict[str, list[dict]],
    base: type[DeclarativeBase],
) -> dict[str, TableChanges]:
    """Compute row-level changes between two :func:`serialize` snapshots.

    Rows are identified by their primary key, so composite keys (junction
    tables declared as ``Table(...)``) work. Tables without a primary key have
    no stable identity and are skipped.

    Args:
        before: Snapshot taken before the agent ran.
        after: Snapshot taken right after.
        base: The declarative base describing the schema.

    Returns:
        ``{table_name: TableChanges}`` for the tables that changed.
    """
    tables: dict[str, TableChanges] = {}
    for table in base.metadata.sorted_tables:
        if len(table.primary_key.columns) == 0:
            # ponytail: no PK -> no stable row identity, skip. Add a synthetic
            # key if a schema without PKs ever needs its changes reported.
            continue
        if changes := _table_diff(table, before, after):
            tables[table.name] = changes
    return tables
