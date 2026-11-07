"""Verifies the Supabase access token sent with every API request.

New Supabase projects sign tokens with asymmetric keys, published at a JWKS URL, so
the API holds no secret at all. Older projects sign with a shared secret, which is
supported only when SUPABASE_JWT_SECRET is set.

The accepted algorithm decides where the key comes from, and each decode allows only
that one algorithm. So a forged HS256 token can't be "signed" with the public key,
which is the classic JWT algorithm-confusion attack.
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Any
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings

ASYMMETRIC_ALGORITHMS = {"ES256", "RS256"}
AUDIENCE = "authenticated"

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
    try:
        # Off the event loop: fetching signing keys is blocking network I/O.
        return await run_in_threadpool(verifier.verify, credentials.credentials)
    except InvalidTokenError as error:
        raise unauthorized from error
    except AuthUnavailableError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="Authentication is unavailable"
        ) from error
