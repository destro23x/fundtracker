"""
Unit tests for auth dependency functions in app.dependencies.

No database required — only the pure JWT validation logic is tested.
Both dev-mode (default secret key) and production-mode (patched secret) branches
are covered for get_current_user_id and get_optional_user_id.
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from app.config import get_settings
from app.dependencies import get_current_user_id, get_optional_user_id

settings = get_settings()

_DEV_SECRET = "change-me-in-production"
_PROD_SECRET = "super-secret-production-key-xyz"


# ─── helpers ─────────────────────────────────────────────────────────────────

def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _make_token(user_id: str, secret: str = _DEV_SECRET, email: str = "u@t.com") -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=1)
    return jwt.encode(
        {"sub": user_id, "email": email, "exp": expire},
        secret,
        algorithm="HS256",
    )


def _make_token_no_sub(secret: str = _DEV_SECRET) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=1)
    return jwt.encode({"email": "u@t.com", "exp": expire}, secret, algorithm="HS256")


# ─── get_current_user_id ─────────────────────────────────────────────────────

class TestGetCurrentUserId:
    async def test_dev_mode_no_credentials_returns_dev_user(self):
        # Patch settings so the secret key matches the dev default
        mock_settings = MagicMock()
        mock_settings.secret_key = _DEV_SECRET
        with patch("app.dependencies.settings", mock_settings):
            result = await get_current_user_id(credentials=None)
        assert result == "dev-user"

    async def test_valid_token_returns_user_id(self):
        uid = str(uuid.uuid4())
        mock_settings = MagicMock()
        mock_settings.secret_key = _PROD_SECRET
        token = _make_token(uid, secret=_PROD_SECRET)
        with patch("app.dependencies.settings", mock_settings):
            result = await get_current_user_id(credentials=_creds(token))
        assert result == uid

    async def test_invalid_token_raises_401(self):
        mock_settings = MagicMock()
        mock_settings.secret_key = _PROD_SECRET
        with patch("app.dependencies.settings", mock_settings):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_id(credentials=_creds("not.a.valid.token"))
        assert exc_info.value.status_code == 401

    async def test_tampered_token_raises_401(self):
        token = _make_token(str(uuid.uuid4()), secret=_PROD_SECRET)
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
        mock_settings = MagicMock()
        mock_settings.secret_key = _PROD_SECRET
        with patch("app.dependencies.settings", mock_settings):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_id(credentials=_creds(tampered))
        assert exc_info.value.status_code == 401

    async def test_token_missing_sub_raises_401(self):
        mock_settings = MagicMock()
        mock_settings.secret_key = _PROD_SECRET
        with patch("app.dependencies.settings", mock_settings):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_id(credentials=_creds(_make_token_no_sub(_PROD_SECRET)))
        assert exc_info.value.status_code == 401

    async def test_production_mode_no_credentials_raises_401(self):
        mock_settings = MagicMock()
        mock_settings.secret_key = _PROD_SECRET
        with patch("app.dependencies.settings", mock_settings):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_id(credentials=None)
        assert exc_info.value.status_code == 401

    async def test_production_mode_valid_token_returns_user_id(self):
        uid = str(uuid.uuid4())
        token = _make_token(uid, secret=_PROD_SECRET)
        mock_settings = MagicMock()
        mock_settings.secret_key = _PROD_SECRET
        with patch("app.dependencies.settings", mock_settings):
            result = await get_current_user_id(credentials=_creds(token))
        assert result == uid

    async def test_production_mode_wrong_secret_raises_401(self):
        # Token signed with dev secret presented to a production instance
        token = _make_token(str(uuid.uuid4()), secret=_DEV_SECRET)
        mock_settings = MagicMock()
        mock_settings.secret_key = _PROD_SECRET
        with patch("app.dependencies.settings", mock_settings):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_id(credentials=_creds(token))
        assert exc_info.value.status_code == 401


# ─── get_optional_user_id ────────────────────────────────────────────────────

class TestGetOptionalUserId:
    async def test_dev_mode_no_credentials_returns_dev_user(self):
        mock_settings = MagicMock()
        mock_settings.secret_key = _DEV_SECRET
        with patch("app.dependencies.settings", mock_settings):
            result = await get_optional_user_id(credentials=None)
        assert result == "dev-user"

    async def test_valid_token_returns_user_id(self):
        uid = str(uuid.uuid4())
        mock_settings = MagicMock()
        mock_settings.secret_key = _PROD_SECRET
        token = _make_token(uid, secret=_PROD_SECRET)
        with patch("app.dependencies.settings", mock_settings):
            result = await get_optional_user_id(credentials=_creds(token))
        assert result == uid

    async def test_invalid_token_returns_none(self):
        mock_settings = MagicMock()
        mock_settings.secret_key = _PROD_SECRET
        with patch("app.dependencies.settings", mock_settings):
            result = await get_optional_user_id(credentials=_creds("invalid.token.here"))
        assert result is None

    async def test_tampered_token_returns_none(self):
        token = _make_token(str(uuid.uuid4()), secret=_PROD_SECRET)
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
        mock_settings = MagicMock()
        mock_settings.secret_key = _PROD_SECRET
        with patch("app.dependencies.settings", mock_settings):
            result = await get_optional_user_id(credentials=_creds(tampered))
        assert result is None

    async def test_token_missing_sub_returns_none(self):
        mock_settings = MagicMock()
        mock_settings.secret_key = _PROD_SECRET
        with patch("app.dependencies.settings", mock_settings):
            result = await get_optional_user_id(credentials=_creds(_make_token_no_sub(_PROD_SECRET)))
        assert result is None

    async def test_production_mode_no_credentials_returns_none(self):
        mock_settings = MagicMock()
        mock_settings.secret_key = _PROD_SECRET
        with patch("app.dependencies.settings", mock_settings):
            result = await get_optional_user_id(credentials=None)
        assert result is None

    async def test_production_mode_valid_token_returns_user_id(self):
        uid = str(uuid.uuid4())
        token = _make_token(uid, secret=_PROD_SECRET)
        mock_settings = MagicMock()
        mock_settings.secret_key = _PROD_SECRET
        with patch("app.dependencies.settings", mock_settings):
            result = await get_optional_user_id(credentials=_creds(token))
        assert result == uid

    async def test_production_mode_wrong_secret_returns_none(self):
        token = _make_token(str(uuid.uuid4()), secret=_DEV_SECRET)
        mock_settings = MagicMock()
        mock_settings.secret_key = _PROD_SECRET
        with patch("app.dependencies.settings", mock_settings):
            result = await get_optional_user_id(credentials=_creds(token))
        assert result is None
