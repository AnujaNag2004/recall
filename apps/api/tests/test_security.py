"""Token verification, including the attacks it exists to stop."""

import base64
import hashlib
import hmac
import json
import time
from typing import Any
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.core.config import Settings
from app.core.security import AuthUnavailableError, InvalidTokenError, TokenVerifier
from tests.conftest import TEST_JWT_SECRET, TEST_SUPABASE_URL, make_token

USER_ID = uuid4()
ISSUER = f"{TEST_SUPABASE_URL}/auth/v1"


def es256_claims(**overrides: Any) -> dict[str, Any]:
    return {
        "sub": str(USER_ID),
        "aud": "authenticated",
        "iss": ISSUER,
        "role": "authenticated",
        "email": "person@example.com",
        "exp": int(time.time()) + 600,
        **overrides,
    }


class FakeJwkClient(jwt.PyJWKClient):
    """Hands back a fixed public key, or fails the way a network outage does."""

    def __init__(self, public_key: Any = None, error: Exception | None = None) -> None:
        self._public_key = public_key
        self._error = error

    def get_signing_key_from_jwt(self, token: Any) -> Any:
        if self._error:
            raise self._error
        return type("SigningKey", (), {"key": self._public_key})()


@pytest.fixture
def es256_key() -> ec.EllipticCurvePrivateKey:
    return ec.generate_private_key(ec.SECP256R1())


def hs256_verifier() -> TokenVerifier:
    settings = Settings(supabase_url=TEST_SUPABASE_URL, supabase_jwt_secret=TEST_JWT_SECRET)
    return TokenVerifier(settings)


def jwks_verifier(public_key: Any) -> TokenVerifier:
    settings = Settings(supabase_url=TEST_SUPABASE_URL, supabase_jwt_secret=None)
    return TokenVerifier(settings, jwk_client=FakeJwkClient(public_key))


def test_accepts_a_token_signed_by_the_project_key(es256_key: ec.EllipticCurvePrivateKey) -> None:
    token = jwt.encode(es256_claims(), es256_key, algorithm="ES256")
    user = jwks_verifier(es256_key.public_key()).verify(token)
    assert user.id == USER_ID
    assert user.email == "person@example.com"


def test_accepts_a_legacy_shared_secret_token() -> None:
    assert hs256_verifier().verify(make_token(USER_ID)).id == USER_ID


def test_rejects_a_token_signed_by_another_key(es256_key: ec.EllipticCurvePrivateKey) -> None:
    attacker = ec.generate_private_key(ec.SECP256R1())
    token = jwt.encode(es256_claims(), attacker, algorithm="ES256")
    with pytest.raises(InvalidTokenError):
        jwks_verifier(es256_key.public_key()).verify(token)


def test_rejects_hs256_signed_with_the_public_key(es256_key: ec.EllipticCurvePrivateKey) -> None:
    """Algorithm confusion: the public key is public, so it must never act as a secret."""
    pem = es256_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps(es256_claims()).encode()).rstrip(b"=").decode()
    signature = hmac.new(pem, f"{header}.{payload}".encode(), hashlib.sha256).digest()
    forged = f"{header}.{payload}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"
    with pytest.raises(InvalidTokenError):
        jwks_verifier(es256_key.public_key()).verify(forged)


def test_rejects_an_unsigned_token() -> None:
    token = jwt.encode(es256_claims(), None, algorithm="none")  # type: ignore[arg-type]
    with pytest.raises(InvalidTokenError):
        hs256_verifier().verify(token)


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"exp": int(time.time()) - 10}, id="expired"),
        pytest.param({"aud": "someone-else"}, id="wrong-audience"),
        pytest.param({"iss": "https://evil.example/auth/v1"}, id="wrong-issuer"),
        pytest.param({"role": "anon"}, id="anon-key-not-a-user"),
        pytest.param({"role": "service_role"}, id="service-key-not-a-user"),
        pytest.param({"sub": "not-a-uuid"}, id="bad-subject"),
    ],
)
def test_rejects_bad_claims(overrides: dict[str, Any]) -> None:
    with pytest.raises(InvalidTokenError):
        hs256_verifier().verify(make_token(USER_ID, **overrides))


def test_rejects_a_token_missing_required_claims() -> None:
    token = jwt.encode(
        {"sub": str(USER_ID), "aud": "authenticated", "iss": ISSUER, "role": "authenticated"},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(InvalidTokenError):  # no exp
        hs256_verifier().verify(token)


def test_rejects_garbage() -> None:
    with pytest.raises(InvalidTokenError):
        hs256_verifier().verify("not.a.token")


def test_hs256_is_refused_when_no_secret_is_configured() -> None:
    settings = Settings(supabase_url=TEST_SUPABASE_URL, supabase_jwt_secret=None)
    with pytest.raises(InvalidTokenError):
        TokenVerifier(settings).verify(make_token(USER_ID))


def test_unconfigured_auth_is_unavailable_not_open() -> None:
    settings = Settings(supabase_url=None, supabase_jwt_secret=None)
    with pytest.raises(AuthUnavailableError):
        TokenVerifier(settings).verify(make_token(USER_ID))


def test_unreachable_signing_keys_are_unavailable(es256_key: ec.EllipticCurvePrivateKey) -> None:
    settings = Settings(supabase_url=TEST_SUPABASE_URL, supabase_jwt_secret=None)
    client = FakeJwkClient(error=jwt.PyJWKClientConnectionError("network down"))
    token = jwt.encode(es256_claims(), es256_key, algorithm="ES256")
    with pytest.raises(AuthUnavailableError):
        TokenVerifier(settings, jwk_client=client).verify(token)
