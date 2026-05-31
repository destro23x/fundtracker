"""
Unit tests for auth helper functions in app.api.auth.
No database required — only pure functions are tested.
"""
import uuid

import pytest
from jose import jwt, JWTError

from app.api.auth import _hash, _verify, _make_token, settings


class TestHashAndVerify:
    def test_hash_returns_bcrypt_string(self):
        h = _hash("password123")
        assert h.startswith("$2b$")

    def test_hash_correct_password_verifies(self):
        h = _hash("correcthorse")
        assert _verify("correcthorse", h) is True

    def test_hash_wrong_password_rejected(self):
        h = _hash("correcthorse")
        assert _verify("wrongpassword", h) is False

    def test_hash_is_salted(self):
        # Two hashes of the same password must differ (bcrypt salt)
        h1 = _hash("same")
        h2 = _hash("same")
        assert h1 != h2

    def test_empty_password_round_trips(self):
        h = _hash("")
        assert _verify("", h) is True
        assert _verify("x", h) is False

    def test_long_password_round_trips(self):
        pw = "a" * 50  # well within bcrypt 72-byte limit
        h = _hash(pw)
        assert _verify(pw, h) is True

    def test_polish_characters_round_trip(self):
        pw = "zażółćgęśląjaźń"
        h = _hash(pw)
        assert _verify(pw, h) is True
        assert _verify(pw + "x", h) is False


class TestMakeToken:
    def test_token_is_string(self):
        token = _make_token(str(uuid.uuid4()), "user@example.com")
        assert isinstance(token, str)

    def test_token_sub_claim(self):
        uid = str(uuid.uuid4())
        payload = jwt.decode(
            _make_token(uid, "user@example.com"),
            settings.secret_key,
            algorithms=["HS256"],
        )
        assert payload["sub"] == uid

    def test_token_email_claim(self):
        payload = jwt.decode(
            _make_token("uid", "hello@test.pl"),
            settings.secret_key,
            algorithms=["HS256"],
        )
        assert payload["email"] == "hello@test.pl"

    def test_token_has_exp_claim(self):
        payload = jwt.decode(
            _make_token("uid", "u@t.com"),
            settings.secret_key,
            algorithms=["HS256"],
        )
        assert "exp" in payload

    def test_wrong_secret_rejected(self):
        token = _make_token("uid", "u@t.com")
        with pytest.raises(JWTError):
            jwt.decode(token, "completely-wrong-secret", algorithms=["HS256"])

    def test_tampered_token_rejected(self):
        token = _make_token("uid", "u@t.com")
        # Flip last character to tamper with signature
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
        with pytest.raises(JWTError):
            jwt.decode(tampered, settings.secret_key, algorithms=["HS256"])

    def test_tokens_for_different_users_differ(self):
        t1 = _make_token("user-1", "a@a.com")
        t2 = _make_token("user-2", "b@b.com")
        assert t1 != t2
