"""The event contract, loaded once for the tests that check real events against it (POC 4, Stage 2).

The schema file is the one CI checks the example events against (scripts/check-event-examples.py), so the service's
events and the contract can never drift apart unnoticed. Not a test file itself: pytest collects only test_*.py.

The format checker matters: without it, "format": "date-time" is only a comment, and jsonschema checks date-time only
when the rfc3339-validator package is installed (Stage 1, lesson A3). find_spec stops the run instead of letting the
tests quietly check less.
"""

import json                                    # reads the schema file's JSON text into a Python dict
from importlib.util import find_spec           # asks "could this package be imported?" without importing it
from pathlib import Path                       # file paths that work on Windows and Linux alike
from typing import Any

from jsonschema import Draft7Validator         # the JSON Schema checker, for the draft-07 version the schema uses

# Path(__file__)       this file:            02-python-transformation-api/tests/event_schema.py
# .resolve()           made absolute
# .parents[2]          two folders up:       the repository root (parents[0] is tests/, parents[1] the service folder)
SCHEMA_FILE = Path(__file__).resolve().parents[2] / "docs" / "api" / "events" / "readings-stored.schema.json"
EXAMPLE_FILE = SCHEMA_FILE.parent / "examples" / "valid-01-two-readings.json"     # the contract's own valid example

# This runs once, when the first test file imports this module. A RuntimeError here stops the whole test run.
if find_spec("rfc3339_validator") is None:
    raise RuntimeError("rfc3339-validator is not installed: date-time formats would not be checked")

SCHEMA = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))                       # the schema, as a dict
# format_checker=...: also check "format" keywords such as date-time (otherwise they are only comments).
VALIDATOR = Draft7Validator(SCHEMA, format_checker=Draft7Validator.FORMAT_CHECKER)


def contract_errors(event: dict[str, Any]) -> list[str]:
    """Every way the event breaks the contract, as readable messages; an empty list means it is valid."""
    # iter_errors gives one error object per problem. error.path is where it is, e.g. ["readings", 0], written here
    # as "readings/0" ("(top)" when the problem is at the top level), followed by jsonschema's own message.
    return [f"{'/'.join(str(p) for p in error.path) or '(top)'}: {error.message}" for error in VALIDATOR.iter_errors(event)]
