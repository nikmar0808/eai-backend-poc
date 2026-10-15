import hmac

import pytest
from fastapi import HTTPException

from app.api import authenticator
from app.api.authenticator import authenticate_request
from app.config import settings


@pytest.fixture(autouse=True)
def known_token(monkeypatch):
    monkeypatch.setattr(settings, "API_SECURITY_TOKEN", "correct-token")


def test_the_correct_token_is_accepted():
    assert authenticate_request("correct-token") == "correct-token"


@pytest.mark.parametrize("candidate", [None, "", "wrong", "correct-toke", "correct-token ", "CORRECT-TOKEN"])
def test_anything_else_is_rejected_with_401(candidate):
    with pytest.raises(HTTPException) as error:
        authenticate_request(candidate)
    assert error.value.status_code == 401


def test_a_non_ascii_token_is_rejected_and_does_not_crash():
    # hmac.compare_digest raises TypeError for a non-ASCII str; the code encodes both sides to avoid that.
    with pytest.raises(HTTPException) as error:
        authenticate_request("tökén")
    assert error.value.status_code == 401


def test_the_comparison_is_constant_time(monkeypatch):
    # Finding D7: a plain == stops at the first differing character. This guards against its return.
    calls = []
    real = hmac.compare_digest
    monkeypatch.setattr(authenticator.hmac, "compare_digest", lambda a, b: calls.append((a, b)) or real(a, b))

    authenticate_request("correct-token")

    assert calls == [(b"correct-token", b"correct-token")]
