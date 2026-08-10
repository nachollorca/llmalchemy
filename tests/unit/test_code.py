"""Tests for the sandboxed code validator and executor."""

import pytest

from llmalchemy.code import execute, validate

# -- validate -----------------------------------------------------------


@pytest.mark.parametrize(
    "source, reason_fragment",
    [
        ("import os", "Forbidden import: os"),
        ("import subprocess", "Forbidden import: subprocess"),
        ("from os import path", "Forbidden import: os"),
        ("from math import *", "Forbidden star import"),
        ("x = exec", "Forbidden builtin: exec"),
        ("eval('1+1')", "Forbidden builtin: eval"),
        ("open('f')", "Forbidden builtin: open"),
        ("x = os", "Forbidden name: os"),
        ("int.__subclasses__()", "Forbidden attribute access: __subclasses__"),
        ("x = (1 +", "Syntax error"),
    ],
)
def test_validate_rejects(source: str, reason_fragment: str):
    reason = validate(source=source, allowed_imports=[])
    assert reason_fragment in reason


@pytest.mark.parametrize(
    "source",
    [
        "x = 1 + 2",
        "session.query(Author).all()",
        "for i in range(3):\n    print(i)",
    ],
)
def test_validate_accepts_safe_code(source: str):
    assert validate(source=source, allowed_imports=[]) == ""


def test_validate_allows_whitelisted_import():
    assert validate(source="import datetime", allowed_imports=["datetime"]) == ""
    assert validate(source="from datetime import date", allowed_imports=["datetime"]) == ""


def test_validate_rejects_non_whitelisted_import():
    reason = validate(source="import json", allowed_imports=["datetime"])
    assert "Forbidden import: json" in reason


# -- execute ------------------------------------------------------------


def test_execute_captures_stdout():
    ns: dict = {}
    out, failed = execute(source="print('hello')", namespace=ns)
    assert "hello" in out
    assert failed is False


def test_execute_returns_message_when_no_stdout():
    out, failed = execute(source="x = 1", namespace={})
    assert "no stdout" in out.lower()
    assert failed is False


def test_execute_persists_namespace_bindings():
    ns: dict = {}
    execute(source="x = 42", namespace=ns)
    assert ns["x"] == 42


def test_execute_returns_traceback_on_exception():
    out, failed = execute(source="raise ValueError('boom')", namespace={})
    assert "ValueError" in out
    assert "boom" in out
    assert "Traceback" in out
    assert failed is True
