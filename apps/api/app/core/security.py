"""Verifies the Supabase access token sent with every API request.

New Supabase projects sign tokens with asymmetric keys, published at a JWKS URL, so
the API holds no secret at all. Older projects sign with a shared secret, which is
supported only when SUPABASE_JWT_SECRET is set.

The accepted algorithm decides where the key comes from, and each decode allows only
that one algorithm. So a forged HS256 token can't be "signed" with the public key,
which is the classic JWT algorithm-confusion attack.
"""

import hashlib
import secrets
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Any
from uuid import UUID

import jwt
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text

from app.core.config import Settings, get_settings
from app.db.engine import get_engine

ASYMMETRIC_ALGORITHMS = {"ES256", "RS256"}
AUDIENCE = "authenticated"
API_KEY_PREFIX = "rk_"

bearer_scheme = HTTPBearer(auto_error=False)


class InvalidTokenError(Exception):
    """The token is missing, malformed, forged or expired."""


class AuthUnavailableError(Exception):
    """Tokens can't be checked right now: not configured, or signing keys unreachable."""


@dataclass(frozen=True)
class CurrentUser:
    id: UUID
    email: str | None


class TokenVerifier:
    def __init__(self, settings: Settings, jwk_client: jwt.PyJWKClient | None = None) -> None:
        self._issuer = settings.supabase_issuer
        self._secret = settings.supabase_jwt_secret
        jwks_url = settings.supabase_jwks_url
        # PyJWKClient caches keys and refetches only for an unknown key id.
        self._jwk_client = jwk_client or (
            jwt.PyJWKClient(jwks_url, cache_keys=True, timeout=5) if jwks_url else None
        )

    def verify(self, token: str) -> CurrentUser:
        if not self._issuer:
            raise AuthUnavailableError("SUPABASE_URL is not set")
        try:
            algorithm = str(jwt.get_unverified_header(token).get("alg"))
            claims = jwt.decode(
                token,
                self._key_for(token, algorithm),
                algorithms=[algorithm],
                audience=AUDIENCE,
                issuer=self._issuer,
                options={"require": ["exp", "sub", "aud", "iss"]},
            )
        except (jwt.PyJWKClientConnectionError, jwt.PyJWKSetError) as error:
            raise AuthUnavailableError("Could not fetch signing keys") from error
        except jwt.PyJWTError as error:
            raise InvalidTokenError(str(error)) from error
        return self._to_user(claims)

    def _key_for(self, token: str, algorithm: str) -> Any:
        if algorithm in ASYMMETRIC_ALGORITHMS and self._jwk_client:
            return self._jwk_client.get_signing_key_from_jwt(token).key
        if algorithm == "HS256" and self._secret:
            return self._secret
        raise InvalidTokenError(f"Algorithm not accepted: {algorithm}")

    @staticmethod
    def _to_user(claims: dict[str, Any]) -> CurrentUser:
        if claims.get("role") != AUDIENCE:
            raise InvalidTokenError("Token does not belong to a signed-in user")
        try:
            return CurrentUser(id=UUID(claims["sub"]), email=claims.get("email"))
        except ValueError as error:
            raise InvalidTokenError("Token subject is not a user id") from error


@lru_cache
def get_token_verifier() -> TokenVerifier:
    return TokenVerifier(get_settings())


def generate_api_key() -> str:
    return f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"


def hash_api_key(key: str) -> str:
    """Only this is stored, so a database leak doesn't hand out working keys."""
    return hashlib.sha256(key.encode()).hexdigest()


async def _user_from_api_key(key: str) -> CurrentUser | None:
    """For the MCP server and other tools. Acts as the user, under the same RLS."""
    async with get_engine().begin() as connection:
        row = (
            await connection.execute(
                text(
                    """
                    update public.api_keys set last_used_at = now()
                    where hashed_key = :hash returning user_id
                    """
                ),
                {"hash": hash_api_key(key)},
            )
        ).first()
    return CurrentUser(id=row.user_id, email=None) if row else None


def _fernet(settings: Settings) -> Fernet:
    if not settings.token_encryption_key:
        raise AuthUnavailableError("TOKEN_ENCRYPTION_KEY is not set")
    return Fernet(settings.token_encryption_key)


def encrypt_secret(value: str, settings: Settings) -> str:
    return _fernet(settings).encrypt(value.encode()).decode()


def decrypt_secret(value: str, settings: Settings) -> str:
    try:
        return _fernet(settings).decrypt(value.encode()).decode()
    except InvalidToken as error:
        raise AuthUnavailableError("A stored token couldn't be decrypted") from error


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    verifier: Annotated[TokenVerifier, Depends(get_token_verifier)],
) -> CurrentUser:
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    if credentials.credentials.startswith(API_KEY_PREFIX):
        user = await _user_from_api_key(credentials.credentials)
        if user is None:
            raise unauthorized
        return user
    try:
        # Off the event loop: fetching signing keys is blocking network I/O.
        return await run_in_threadpool(verifier.verify, credentials.credentials)
    except InvalidTokenError as error:
        raise unauthorized from error
    except AuthUnavailableError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="Authentication is unavailable"
        ) from error
