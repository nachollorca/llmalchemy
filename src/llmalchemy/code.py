"""Contains the logic for the sandboxed python env on which to run the agent requested code.

HuggingFace has a very nice reference for further ideas:
https://github.com/huggingface/smolagents/blob/main/src/smolagents/local_python_executor.py
"""

import ast
import contextlib
import io
import sys
import time
import traceback

FORBIDDEN_BUILTINS = frozenset(
    {
        "exec",
        "eval",
        "compile",
        "__import__",
        "open",
        "exit",
        "quit",
        "breakpoint",
        "input",
        "getattr",
        "setattr",
        "delattr",
        "globals",
        "locals",
        "vars",
        "dir",
    }
)

FORBIDDEN_MODULE_NAMES = frozenset(
    {
        "os",
        "subprocess",
        "sys",
        "shutil",
        "pathlib",
        "importlib",
    }
)

FORBIDDEN_ATTRIBUTES = frozenset(
    {
        "__globals__",
        "__builtins__",
        "__subclasses__",
        "__bases__",
        "__code__",
        "__import__",
        "__dict__",
    }
)


def _check_import(node: ast.Import, allowed_imports: list[str]) -> str:
    """Block imports whose root module is not in the whitelist."""
    for alias in node.names:
        root = alias.name.split(".")[0]
        if root not in allowed_imports:
            return f"Forbidden import: {alias.name}"
    return ""


def _check_import_from(node: ast.ImportFrom, allowed_imports: list[str]) -> str:
    """Block star imports unconditionally; block modules not in the whitelist."""
    for alias in node.names:
        if alias.name == "*":
            return f"Forbidden star import: from {node.module} import *"
    if node.module:
        root = node.module.split(".")[0]
        if root not in allowed_imports:
            return f"Forbidden import: {node.module}"
    return ""


def _check_name(node: ast.Name) -> str:
    """Block dangerous builtin calls/references and dangerous module names."""
    if node.id in FORBIDDEN_BUILTINS:
        return f"Forbidden builtin: {node.id}"
    if node.id in FORBIDDEN_MODULE_NAMES:
        return f"Forbidden name: {node.id}"
    return ""


def _check_attribute(node: ast.Attribute) -> str:
    """Block dangerous dunder attribute access."""
    if node.attr in FORBIDDEN_ATTRIBUTES:
        return f"Forbidden attribute access: {node.attr}"
    return ""


def validate(source: str, allowed_imports: list[str]) -> str:
    """Use AST parsing against a set of rules to decide if the code is safe.

    Args:
        source: Python source code produced by the model.
        allowed_imports: Whitelist of importable module names.

    Returns:
        ``""`` on success, or a human-readable reason string on rejection.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return f"Syntax error: {e.msg}"

    reason = ""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            reason = _check_import(node, allowed_imports)
        elif isinstance(node, ast.ImportFrom):
            reason = _check_import_from(node, allowed_imports)
        elif isinstance(node, ast.Name):
            reason = _check_name(node)
        elif isinstance(node, ast.Attribute):
            reason = _check_attribute(node)
        # Exit if any checker populated `reason` -> code is invalid
        if reason:
            break

    return reason


class _Timeout(BaseException):
    """Deadline escape hatch; BaseException so the model's `except Exception` can't eat it."""


def execute(source: str, namespace: dict, timeout: float = 30.0) -> str:
    """Execute *source* code requested by the Agent inside *namespace*.

    Runs synchronously in the calling thread so the caller's SQLAlchemy session keeps
    its thread affinity. A ``sys.settrace`` line hook enforces a wall-clock deadline,
    so the model's infinite loops are interrupted instead of hanging the caller.

    Args:
        source: Python/SQLAlchemy source code produced by the model.
        namespace: Dict of python symbols available during execution.
            **Mutated in-place** — new bindings created by the code
            persist in *namespace* after this call returns.
        timeout: Wall-clock seconds before execution is abandoned.

    Returns:
        A string with stdout output, a traceback, or a status message.
    """
    buf = io.StringIO()
    deadline = time.monotonic() + timeout

    def trace(frame, event, arg):
        # Raises before the next line runs; note CPython unsets the hook if a traced
        # frame swallows this, which a bare `except:` still can.
        if time.monotonic() > deadline:
            raise _Timeout
        return trace

    # shortcut: the deadline only fires between Python bytecodes, so a blocking C
    # call (time.sleep, sockets) still hangs; move to process isolation for a hard kill.
    previous_trace = sys.gettrace()  # e.g. a coverage/debugger hook — restore it
    sys.settrace(trace)
    try:
        compiled = compile(source, "<agent>", "exec")
        with contextlib.redirect_stdout(buf):
            exec(compiled, namespace)
        if time.monotonic() > deadline:
            raise _Timeout
        return (
            buf.getvalue()
            or "Code executed successfully but produced no stdout. To see a value use print()."
        )
    except _Timeout:
        return f"Execution timed out after {timeout}s."
    except Exception:
        return traceback.format_exc()
    finally:
        sys.settrace(previous_trace)
