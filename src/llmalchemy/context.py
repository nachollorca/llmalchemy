"""Contains the utils to engineer the context passed to the agent."""

import inspect
import re
import warnings
from pathlib import Path

from lmdk import render_template
from sqlalchemy.orm import DeclarativeBase

from .database import mapped_classes
from .tools import Tool

_TEMPLATE_PATH = Path(__file__).parent / "prompt.jinja"

_REQUIRED_MARKERS = ("SCHEMA", "SYMBOLS", "TOOLS", "IMPORTS")


class LLMAlchemyPromptWarning(UserWarning):
    """Warning for prompt templates missing one of the documented Jinja variables."""


def _render_schema_source(base: type[DeclarativeBase]) -> str:
    """Return the source code of ORM classes for the LM prompt.

    Extracts source code via ``inspect.getsource`` for every mapped class
    registered under *base*.  The sources are concatenated separated by
    blank lines.
    """
    sources = [inspect.getsource(cls) for cls in mapped_classes(base)]
    return "\n\n".join(sources)


def _render_symbols(descriptions: dict[str, str]) -> str:
    """Format the symbol descriptions dict as a Markdown bullet list."""
    return "\n".join(f"- `{name}`: {desc}" for name, desc in descriptions.items())


def _render_tools_summary(tools: list[Tool]) -> str:
    """Render name + one-liner for each tool (empty string if no tools)."""
    if not tools:
        return ""
    return "\n".join(f"- `{t.name}`: {t.short_description}" for t in tools)


def _render_imports(allowed_imports: list[str]) -> str:
    """Render the import policy as one sentence."""
    if not allowed_imports:
        return "`import` statements are forbidden. Use only the pre-loaded symbols listed below."
    modules = ", ".join(f"`{m}`" for m in allowed_imports)
    return f"Only these modules may be imported: {modules}."


def _render_references(base: type[DeclarativeBase], referenceable_tables: list[str] | None) -> str:
    """Render the row-reference instruction for the allowed tables.

    Table names are validated against the schema so a typo raises instead of
    silently letting the agent cite a table that does not exist.
    """
    if not referenceable_tables:
        return ""
    known = base.metadata.tables
    unknown = [name for name in referenceable_tables if name not in known]
    if unknown:
        raise ValueError(
            f"Unknown referenceable table(s): {', '.join(unknown)}. "
            f"Available tables: {', '.join(sorted(known))}."
        )
    names = ", ".join(f"`{name}`" for name in referenceable_tables)
    return (
        f"You can reference specific rows in {names} by inlining "
        "`[TableName:row_pk]` in your message to the user."
    )


def _check_markers(source: str) -> None:
    """Warn for each required Jinja variable missing from the raw template source."""
    for marker in _REQUIRED_MARKERS:
        if not re.search(r"\{\{\s*" + marker + r"\s*\}\}", source):
            warnings.warn(
                f"Prompt template is missing the `{{{{ {marker} }}}}` variable; "
                "the agent may behave unpredictably.",
                LLMAlchemyPromptWarning,
                stacklevel=2,
            )


def render(
    base: type[DeclarativeBase],
    tools: list[Tool],
    descriptions: dict[str, str],
    template: str | Path | None = None,
    allowed_imports: list[str] | None = None,
    referenceable_tables: list[str] | None = None,
) -> str:
    """Build the system instruction for the LM with all context parts.

    Args:
        base: The declarative base describing the schema.
        tools: User-provided tools registered for this run.
        descriptions: ``{name: description}`` of every namespace symbol,
            as returned by ``_init_namespace`` in ``agent.py``.
        template: A Jinja template source string, a ``Path`` to a template
            file, or ``None`` to use the shipped default.
        allowed_imports: Modules the agent may import. ``None`` or an empty
            list means imports are forbidden.
        referenceable_tables: Schema table names the agent may cite inline
            with ``[TableName:row_pk]``. ``None`` means citations are disabled.
    """
    if template is None:
        path: Path = _TEMPLATE_PATH
        source = path.read_text()
    else:
        source = template.read_text() if isinstance(template, Path) else template
    _check_markers(source)
    return render_template(
        template=source,
        SCHEMA=_render_schema_source(base=base),
        SYMBOLS=_render_symbols(descriptions),
        TOOLS=_render_tools_summary(tools),
        IMPORTS=_render_imports(allowed_imports or []),
        REFERENCES=_render_references(base, referenceable_tables),
    )
