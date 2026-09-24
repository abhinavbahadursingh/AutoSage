"""JWT helpers — Phase 2 authentication with Supabase Auth / Better Auth.

Supports two auth providers:
1. Supabase Auth: RS256 JWTs verified via JWKS (keys rotated automatically)
2. Better Auth: HS256 JWTs verified via shared secret (BETTER_AUTH_SECRET)

The JWT_ALGORITHM setting determines which verification path is used:
- RS256/RS384/RS512/ES256/ES384/ES512 -> JWKS verification (Supabase)
- HS256/HS384/HS512 -> Shared secret verification (Better Auth)

Expected claims (both)::

    {"sub": "<user uuid>", "email": ..., "name": ..., "iat": ..., "exp": ..., "aud": "authenticated" (Supabase only)}

Only ``sub`` is required; ``email``/``name``/``image`` are used for lazy
local user provisioning (see :mod:`app.services.user_service`).
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import UUID

import jwt
import httpx

from app.core.config import settings


class TokenError(Exception):
    """Base class for token verification failures (mapped to 401)."""


class TokenExpiredError(TokenError):
    """Token signature is valid but the token has expired."""


class TokenInvalidError(TokenError):
    """Token is malformed, badly signed, or missing required claims."""


# In-memory JWKS cache
_jwks_cache: Dict[str, Any] = {"keys": {}, "fetched_at": 0}
_JWKS_TTL_SECONDS = 3600  # 1 hour


async def _fetch_jwks() -> Dict[str, Any]:
    """Fetch JWKS from Supabase Auth."""
    global _jwks_cache
    now = datetime.now(timezone.utc).timestamp()
    
    # Return cached if still valid
    if _jwks_cache["keys"] and (now - _jwks_cache["fetched_at"]) < _JWKS_TTL_SECONDS:
        return _jwks_cache["keys"]
    
    jwks_url = f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(jwks_url)
            response.raise_for_status()
            jwks = response.json()
            
            # Convert to kid -> public key mapping
            keys = {}
            for key in jwks.get("keys", []):
                kid = key.get("kid")
                if kid:
                    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
                    keys[kid] = public_key
            
            _jwks_cache = {"keys": keys, "fetched_at": now}
            return keys
    except Exception as exc:
        # If we have cached keys, use them; otherwise fail
        if _jwks_cache["keys"]:
            return _jwks_cache["keys"]
        raise TokenInvalidError(f"Unable to fetch JWKS: {exc}") from exc


async def decode_access_token(token: str) -> Dict[str, Any]:
    """Verify JWT signature + expiry and return the claims.

    Uses JWKS for RS/ES algorithms (Supabase) or shared secret for HS algorithms (dev tokens).

    Raises:
        TokenExpiredError: token is well-formed but past ``exp``.
        TokenInvalidError: bad signature, malformed, or missing ``sub``.
    """
    # Check the algorithm in the token header
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "HS256")
    except jwt.InvalidTokenError:
        alg = "HS256"
    
    if alg.startswith("RS") or alg.startswith("ES"):
        return await _decode_with_jwks(token, alg)
    else:
        return _decode_with_secret(token, alg)


async def _decode_with_jwks(token: str, alg: str) -> Dict[str, Any]:
    """Verify Supabase RS256/ES256 JWT signature + expiry via JWKS."""
    try:
        # Get the key ID from the token header
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if not kid:
            raise TokenInvalidError("Invalid token: missing 'kid' in header")
        
        # Fetch JWKS and get the public key
        keys = await _fetch_jwks()
        public_key = keys.get(kid)
        if not public_key:
            # Force refresh once
            _jwks_cache = {"keys": {}, "fetched_at": 0}
            keys = await _fetch_jwks()
            public_key = keys.get(kid)
            if not public_key:
                raise TokenInvalidError(f"Invalid token: key '{kid}' not found in JWKS")
        
        # Decode and verify with the algorithm from the token header
        claims: Dict[str, Any] = jwt.decode(
            token,
            public_key,
            algorithms=[alg],
            audience="authenticated",  # Supabase uses "authenticated" as audience
            options={
                "require": ["exp", "sub", "iat", "aud"],
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_aud": True,
            },
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError("Token has expired") from exc
    except jwt.InvalidAudienceError as exc:
        raise TokenInvalidError("Invalid token: audience mismatch") from exc
    except jwt.InvalidTokenError as exc:
        # Don't leak internal error details
        raise TokenInvalidError("Invalid token") from exc
    
    if not claims.get("sub"):
        raise TokenInvalidError("Invalid token: missing 'sub' claim")
    return claims


def _decode_with_secret(token: str, alg: str) -> Dict[str, Any]:
    """Verify HS256/HS384/HS512 JWT signature + expiry via shared secret."""
    # Shared-secret verification only accepts HMAC algorithms (prevents
    # algorithm-confusion: an RS/ES token must never be verified with the secret).
    if not alg.startswith("HS"):
        raise TokenInvalidError("Invalid token: unsupported algorithm for shared-secret verification")
    try:
        # Explicitly specify the token's own algorithm to prevent algorithm confusion attacks
        claims: Dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[alg],
            options={
                "require": ["exp", "sub", "iat"],
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
            },
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError("Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        # Don't leak internal error details
        raise TokenInvalidError("Invalid token") from exc
    
    if not claims.get("sub"):
        raise TokenInvalidError("Invalid token: missing 'sub' claim")
    return claims


def extract_user_id(claims: Dict[str, Any]) -> UUID:
    """Parse the ``sub`` claim as a UUID (Supabase/Better Auth uses UUID ids)."""
    try:
        return UUID(str(claims["sub"]))
    except (ValueError, AttributeError, TypeError) as exc:
        raise TokenInvalidError("Invalid token: 'sub' is not a valid user id") from exc


# Dev token creation (optional, for testing)
def get_signing_secret() -> str:
    """Secret used to sign/verify dev tokens (not used for Supabase tokens)."""
    if settings.APP_ENV == "production" and not settings.AUTH_DEV_TOKEN_ENABLED:
        raise RuntimeError("Dev tokens disabled in production")
    return settings.jwt_secret


def create_access_token(
    subject: str,
    extra_claims: Optional[Dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Mint a signed HS256 access token for ``subject`` (a user UUID string).
    
    This is ONLY for local development/testing. Production tokens come from Supabase Auth.
    """
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload: Dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": expire,
    }
    if extra_claims:
        payload.update(extra_claims)
    # Dev tokens use HS256 with shared secret; Supabase tokens use RS256 via JWKS
    return jwt.encode(payload, get_signing_secret(), algorithm="HS256")
