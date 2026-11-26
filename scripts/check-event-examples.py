"""Checks the example events against the event schema: every valid-*.json must pass, every invalid-*.json must fail.

Run from the repository root:  python scripts/check-event-examples.py
Exit code 0 when every example behaves as its name says, 1 otherwise. Used by CI (contract-lint) and by hand.

The format checker matters: without it, "format": "date-time" is only a comment, and a timestamp with no UTC offset
would pass. jsonschema checks date-time only when the rfc3339-validator package is installed, so this script refuses
to run without it.
"""

import json
import sys
from importlib.util import find_spec
from pathlib import Path

from jsonschema import Draft7Validator

SCHEMA = Path("docs/api/events/readings-stored.schema.json")
EXAMPLES = Path("docs/api/events/examples")


def main() -> int:
    if find_spec("rfc3339_validator") is None:
        print("rfc3339-validator is not installed: date-time formats would not be checked")
        return 1
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft7Validator.check_schema(schema)                     # the schema itself must be a valid draft-07 schema
    validator = Draft7Validator(schema, format_checker=Draft7Validator.FORMAT_CHECKER)

    failures = 0
    files = sorted(EXAMPLES.glob("*.json"))
    for path in files:
        errors = sorted(validator.iter_errors(json.loads(path.read_text(encoding="utf-8"))), key=lambda e: list(e.path))
        expected_valid = path.name.startswith("valid-")
        if expected_valid and not errors:
            print(f"ok    {path.name}: valid, as expected")
        elif not expected_valid and errors:
            where = "/".join(str(p) for p in errors[0].path) or "(top level)"
            print(f"ok    {path.name}: rejected, as expected, at {where}: {errors[0].message}")
        else:
            failures += 1
            print(f"FAIL  {path.name}: expected {'valid' if expected_valid else 'invalid'}, got "
                  f"{'valid' if not errors else 'invalid: ' + errors[0].message}")
    print(f"{len(files)} examples, {failures} not as expected")
    return 1 if failures or not files else 0


if __name__ == "__main__":
    sys.exit(main())
