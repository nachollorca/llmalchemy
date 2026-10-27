"""Logic to expose functions to the model."""

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol


class HasMetadata(Protocol):
    """Protocol for objects that have __name__ and __doc__."""

    __name__: str
    __doc__: str | None


@dataclass(frozen=True)
class Tool:
    """Metadata wrapper around a user-provided function.

    Attributes:
        fn: The original callable.
        name: Function name (used as the namespace key).
        short_description: First line of the docstring.
        full_description: Full signature and docstring for discovery.
    """

    fn: Callable[..., Any]
    name: str
    short_description: str
    full_description: str

    @classmethod
    def from_function(cls, fn: Any) -> "Tool":
        """Build a ``Tool`` from a plain function."""
        name = getattr(fn, "__name__", "unknown")
        doc = inspect.cleandoc(getattr(fn, "__doc__", "") or "")
        short = doc.split("\n", 1)[0] if doc else ""
        sig = inspect.signature(fn)
        body = "\n    ".join(doc.split("\n")) if doc else ""
        full = f'def {name}{sig}:\n    """{body}"""' if doc else f"def {name}{sig}:"
        return cls(fn=fn, name=name, short_description=short, full_description=full)


def tool(fn: Any) -> Tool:
    """Decorator that turns a function into a ``Tool``."""
    return Tool.from_function(fn)


def make_disclose_fn(tools: list[Tool]) -> Callable:
    """Build the ``disclose`` closure injected into the agent namespace.

    This is a *closure factory*: it builds ``lookup`` once from *tools*,
    then returns an inner function that captures ``lookup``.  Each call to
    ``make_disclose_fn`` produces a fresh ``disclose`` bound to exactly the
    tools registered for that ``run()`` invocation.

    Args:
        tools: The list of tools registered for this run.

    Returns:
        A callable ``(name: str) -> str``.
    """
    lookup = {t.name: t.full_description for t in tools}

    def disclose(name: str | Callable) -> str:
        """Reveal the full signature and docstring of a tool.

        Args:
            name: The tool name (or the tool function itself) to look up.

        Returns:
            The full description string, or an error message if not found.
        """
        # model may pass the tool function itself rather than its name
        key: str = name if isinstance(name, str) else getattr(name, "__name__", "")
        if key in lookup:
            return lookup[key]
        available = ", ".join(lookup) or "(none)"
        return f"Unknown tool: {key!r}. Available tools: {available}"

    return disclose
