"""Contains the utilities that access or modify the database."""

import weakref

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session


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

    # Build a lookup from table name to mapped class
    cls_by_table: dict[str, type] = {}
    for cls in base.__subclasses__():
        table_name = cls.__tablename__ if hasattr(cls, "__tablename__") else cls.__table__.name
        cls_by_table[table_name] = cls

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
    for cls in base.__subclasses__():
        table_name = cls.__tablename__ if hasattr(cls, "__tablename__") else cls.__table__.name
        columns = [c.key for c in cls.__table__.columns]
        rows = session.query(cls).all()
        result[table_name] = [{col: getattr(row, col) for col in columns} for row in rows]
    return result
