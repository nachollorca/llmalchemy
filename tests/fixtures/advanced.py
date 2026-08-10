"""Dummy schema with single-table inheritance and a ``Table``-based M:N junction.

It lives on its own declarative base (instead of extending ``schema.py``) so the
author/book expectations of the rest of the suite stay untouched.
"""

from sqlalchemy import Column, ForeignKey, String, Table
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class AdvancedBase(DeclarativeBase):
    """Declarative base for the inheritance + junction schema."""


# Variable name deliberately differs from the table name, to exercise the
# Python-variable-name recovery of ``database.association_tables``.
team_members = Table(
    "memberships",
    AdvancedBase.metadata,
    Column("employee_id", ForeignKey("employees.id"), primary_key=True),
    Column("team_id", ForeignKey("teams.id"), primary_key=True),
)


class Employee(AdvancedBase):
    """An employee, discriminated on ``role`` (single-table inheritance)."""

    __tablename__ = "employees"
    __mapper_args__ = {  # noqa: RUF012
        "polymorphic_on": "role",
        "polymorphic_identity": "employee",
    }

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20))

    teams: Mapped[list["Team"]] = relationship(secondary=team_members)


class Manager(Employee):
    """An employee who manages others; shares the ``employees`` table."""

    __mapper_args__ = {"polymorphic_identity": "manager"}  # noqa: RUF012


class Team(AdvancedBase):
    """A team employees can belong to."""

    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120))
