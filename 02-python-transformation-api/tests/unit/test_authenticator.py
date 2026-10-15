"""
What this file protects. `authenticate_request` is the only gate in front of both data routes. Three things
must hold: only the exact token passes (P10, P11); a hostile or odd header cannot crash it into a 500 (P12);
and the comparison stays constant-time (P13, finding D7). A plain `==` stops at the first differing
character, so response time reveals how many leading characters of a guess were right; `hmac.compare_digest`
takes the same time either way.

New ideas used here.
- `@pytest.fixture(autouse=True)`: the fixture runs for every test in the file without being named. Here it
  sets the token for the whole file.
- `monkeypatch.setattr(obj, "name", value)` (A4): the change lasts for one test and is undone automatically.
- `pytest.raises(ExceptionType) as info`: asserts that the block raises that exception; `info.value` is the
  exception object, from which the status code is read.
- Patching a function to spy on it (P13). The test replaces `hmac.compare_digest` with a wrapper that
  records its arguments and then calls the real function. The test then asserts the recorded arguments:
  proof that the safe function was used, and with bytes.
"""
import hmac

import pytest
from fastapi import HTTPException        # what the function raises to produce an HTTP error response

from app.api import authenticator          # the module, so a test can patch things inside it
from app.api.authenticator import authenticate_request
from app.config import settings            # the object holding API_SECURITY_TOKEN


@pytest.fixture(autouse=True)              # applies to every test in this file without being requested
def known_token(monkeypatch):
    monkeypatch.setattr(settings, "API_SECURITY_TOKEN", "correct-token")


def test_the_correct_token_is_accepted():                                                 # P10
    assert authenticate_request("correct-token") == "correct-token"      # it returns the token it accepted


# Six wrong candidates, each a different way to be wrong: absent, empty, wrong, one character short,
# one character extra (a trailing space), and the right letters in the wrong case.
@pytest.mark.parametrize("candidate", [None, "", "wrong", "correct-toke", "correct-token ", "CORRECT-TOKEN"])   # P11: 6 runs
def test_anything_else_is_rejected_with_401(candidate):
    with pytest.raises(HTTPException) as error:
        authenticate_request(candidate)
    assert error.value.status_code == 401


def test_a_non_ascii_token_is_rejected_and_does_not_crash():                              # P12
    # hmac.compare_digest raises TypeError for a non-ASCII str; the code encodes both sides to bytes to avoid that.
    with pytest.raises(HTTPException) as error:
        authenticate_request("tökén")
    assert error.value.status_code == 401


def test_the_comparison_is_constant_time(monkeypatch):                                    # P13
    # Finding D7: a plain == stops at the first differing character. This guards against its return.
    calls = []
    real = hmac.compare_digest
    # The wrapper records the arguments, then returns the real function's answer. list.append returns None, so
    # "append(...) or real(a, b)" evaluates real(a, b) and returns its result.
    monkeypatch.setattr(authenticator.hmac, "compare_digest", lambda a, b: calls.append((a, b)) or real(a, b))

    authenticate_request("correct-token")

    assert calls == [(b"correct-token", b"correct-token")]       # the safe function, called once, with bytes
