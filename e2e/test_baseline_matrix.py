import pytest

from support import JSON_HEADERS, METER_ID, REQUEST_DIR

# (gateway status, Python status) after Stage 6: docs/comprehension/baseline-matrix.md. The gateway answers 400 where
# Python answers 422 (the contracts differ in status code, by design; the property tested below is the agreement).
EXPECTED = {
    "01-valid.json": (200, 200),
    "02-kwh-zero.json": (400, 422),
    "03-voltage-too-low.json": (400, 422),
    "04-timestamp-no-offset.json": (400, 422),
    "05-empty-readings.json": (400, 422),
    "06-blank-grid-zone.json": (400, 422),
    "07-meter-id-too-short.json": (400, 422),
    "08-malformed-json.json": (400, 422),
    "09-missing-readings-field.json": (400, 422),
    # Added in Stage 6: each file tests one rule that both services must now enforce (D29, D37, D36, D39).
    "10-timestamp-as-number.json": (400, 422),
    "11-offset-beyond-14-hours.json": (400, 422),
    "12-null-reading.json": (400, 422),
    "13-control-character-in-grid-zone.json": (400, 422),
}


def request_text(name: str) -> str:
    # The valid file is stored by both services; its meter id is replaced so that the rows carry the run's prefix and
    # are removed afterwards. For the eight invalid files the replace finds nothing and changes nothing.
    return (REQUEST_DIR / name).read_text(encoding="utf-8").replace("MTR-POC2-001", METER_ID)


def send_to_both(gateway, validator, auth, name: str) -> tuple[int, int]:
    content = request_text(name)
    # content= sends the text exactly as stored, including the deliberately malformed file (json= would re-encode it).
    via_gateway = gateway.post("/api/v1/ingest/bulk", content=content, headers=JSON_HEADERS).status_code
    direct = validator.post("/api/v1/transform", content=content, headers={**auth, **JSON_HEADERS}).status_code
    return via_gateway, direct


# E01
def test_every_request_file_has_an_expected_status():
    # A new request file cannot be added without deciding what both services must answer.
    assert sorted(path.name for path in REQUEST_DIR.glob("*.json")) == sorted(EXPECTED)


# E02: parametrize runs the test once per (name, expected) pair: 9 executions, each reported separately.
@pytest.mark.parametrize("name, expected", sorted(EXPECTED.items()))
def test_status_codes_match_the_baseline(gateway, validator, auth, name, expected):
    assert send_to_both(gateway, validator, auth, name) == expected


# E03
@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_the_two_services_agree_on_accept_or_reject(gateway, validator, auth, name):
    # Finding D19 as a property: whatever the status codes are, one service must never accept what the other rejects.
    via_gateway, direct = send_to_both(gateway, validator, auth, name)
    assert (via_gateway == 200) == (direct == 200), f"{name}: gateway {via_gateway}, Python {direct}"
