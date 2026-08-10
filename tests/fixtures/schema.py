"""Dummy schema and a tool for demo/testing purposes."""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

from llmalchemy.tools import tool


class Base(DeclarativeBase):
    """Shared declarative base."""


class Author(Base):
    """An author who can write many books."""

    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120))

    books: Mapped[list["Book"]] = relationship(back_populates="author", passive_deletes=True)


class Book(Base):
    """A book belonging to a single author."""

    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200))
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id", ondelete="CASCADE"))

    author: Mapped["Author"] = relationship(back_populates="books")


@tool
def get_author_catalog(author: str, session: Session) -> list[str]:
    """Dummy tool that simply lists all the the book titles for an author.

    Args:
        author: the name of the author for which to output the books
        session: the database connection
    """
    author_obj = session.query(Author).filter(Author.name == author).first()
    if not author_obj:
        return []
    return [book.title for book in author_obj.books]
