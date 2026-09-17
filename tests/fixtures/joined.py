"""Dummy schema with joined-table inheritance (each class owns its own table)."""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class JoinedBase(DeclarativeBase):
    """Declarative base for the joined-table inheritance schema."""


class Person(JoinedBase):
    """A person, discriminated on ``kind`` across two tables."""

    __tablename__ = "people"
    __mapper_args__ = {  # noqa: RUF012
        "polymorphic_on": "kind",
        "polymorphic_identity": "person",
    }

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))


class Employee(Person):
    """A person who is also an employee; the salary lives in its own table."""

    __tablename__ = "employees"
    __mapper_args__ = {"polymorphic_identity": "employee"}  # noqa: RUF012

    id: Mapped[int] = mapped_column(ForeignKey("people.id"), primary_key=True)
    salary: Mapped[int] = mapped_column()
