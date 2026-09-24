"""Unit tests: JWT creation/verification (no database required)."""
import uuid
from datetime import timedelta
from unittest.mock import patch

import jwt as pyjwt
import pytest

from app.core.config import settings
from app.core.security import (
    TokenExpiredError,
    TokenInvalidError,
    create_access_token,
    decode_access_token,
    extract_user_id,
    get_signing_secret,
)


def _subject() -> str:
    return str(uuid.uuid4())


# Patch settings for all tests to use HS256 with test secrets
@pytest.fixture(autouse=True)
def _patch_settings():
    with patch.object(settings, "JWT_ALGORITHM", "HS256"):
        with patch.object(settings, "BETTER_AUTH_SECRET", "test-secret-key-for-testing-32chars-long-enough"):
            with patch.object(settings, "APP_SECRET_KEY", "test-secret-key-for-testing-32chars-long-enough"):
                with patch.object(settings, "APP_ENV", "development"):
                    with patch.object(settings, "AUTH_DEV_TOKEN_ENABLED", True):
                        with patch.object(settings, "DEBUG", True):
                            yield


@pytest.mark.asyncio
async def test_roundtrip_preserves_subject_and_claims() -> None:
    sub = _subject()
    token = create_access_token(sub, extra_claims={"email": "a@x.io", "name": "A"})
    claims = await decode_access_token(token)
    assert claims["sub"] == sub
    assert claims["email"] == "a@x.io"
    assert "exp" in claims and "iat" in claims


@pytest.mark.asyncio
async def test_expired_token_rejected() -> None:
    token = create_access_token(_subject(), expires_delta=timedelta(seconds=-1))
    with pytest.raises(TokenExpiredError):
        await decode_access_token(token)


@pytest.mark.asyncio
async def test_wrong_secret_rejected() -> None:
    token = pyjwt.encode(
        {"sub": _subject(), "exp": 9999999999},
        "definitely-not-the-app-secret",
        algorithm=settings.JWT_ALGORITHM,
    )
    with pytest.raises(TokenInvalidError):
        await decode_access_token(token)


@pytest.mark.asyncio
async def test_malformed_token_rejected() -> None:
    with pytest.raises(TokenInvalidError):
        await decode_access_token("not-a-jwt")


@pytest.mark.asyncio
async def test_missing_sub_rejected() -> None:
    token = pyjwt.encode(
        {"email": "a@x.io", "exp": 9999999999},
        get_signing_secret(),
        algorithm=settings.JWT_ALGORITHM,
    )
    with pytest.raises(TokenInvalidError):
        await decode_access_token(token)


@pytest.mark.asyncio
async def test_tampered_payload_rejected() -> None:
    sub = _subject()
    token = create_access_token(sub)
    header, payload, signature = token.split(".")
    tampered = f"{header}.{payload}X.{signature}"
    with pytest.raises(TokenInvalidError):
        await decode_access_token(tampered)


def test_extract_user_id_accepts_uuid() -> None:
    sub = _subject()
    assert extract_user_id({"sub": sub}) == uuid.UUID(sub)


def test_extract_user_id_rejects_non_uuid() -> None:
    with pytest.raises(TokenInvalidError):
        extract_user_id({"sub": "not-a-uuid"})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])