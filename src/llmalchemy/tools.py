"""Logic to expose functions to the model."""

import inspect
from collections.abc import Callable, Sequence
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
        short_description: First docstring paragraph, collapsed onto one line.
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
        short = " ".join(doc.split("\n\n", 1)[0].split()) if doc else ""
        sig = inspect.signature(fn)
        body = "\n    ".join(doc.split("\n")) if doc else ""
        full = f'def {name}{sig}:\n    """{body}"""' if doc else f"def {name}{sig}:"
        return cls(fn=fn, name=name, short_description=short, full_description=full)


@dataclass(frozen=True)
class Toolset:
    """A named group of related tools, described for the agent.

    Attributes:
        name: Group name, shown in bold in the prompt.
        description: One paragraph saying what the group is for.
        tools: The tools in the group, in the order the agent should read them.
    """

    name: str
    description: str
    tools: tuple[Tool, ...]


def tool(fn: Any) -> Tool:
    """Decorator that turns a function into a ``Tool``."""
    return Tool.from_function(fn)


def flatten_toolsets(tools: Sequence[Tool | Toolset]) -> list[Tool]:
    """Expand toolsets into a single tool list, keeping declaration order.

    Raises:
        ValueError: If a tool is listed twice, or a toolset has no tools.
    """
    flat: list[Tool] = []
    seen: set[str] = set()
    for item in tools:
        group = item.tools if isinstance(item, Toolset) else (item,)
        if not group:
            raise ValueError(f"Toolset {item.name!r} has no tools.")
        for t in group:
            if t.name in seen:
                raise ValueError(f"Tool {t.name!r} is listed more than once.")
            seen.add(t.name)
            flat.append(t)
    return flat


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
