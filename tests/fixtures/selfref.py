"""Dummy schema whose table references itself.

Like ``advanced``, it lives on its own declarative base so the author/book
expectations of the rest of the suite stay untouched.
"""

from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class SelfRefBase(DeclarativeBase):
    """Declarative base for the self-referential schema."""


class Node(SelfRefBase):
    """A tree node; every node points at its parent."""

    __tablename__ = "nodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("nodes.id"))
    name: Mapped[str] = mapped_column()
