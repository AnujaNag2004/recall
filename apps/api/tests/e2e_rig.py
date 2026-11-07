"""Local rig for the Playwright tests. Not used in production.

Runs real Postgres with every migration, and the real Recall API with its real worker.
Two things are stand-ins, because they can't run locally without accounts: Supabase Auth
(this signs real ES256 tokens, published through JWKS) and the AI providers.
"""

import json
import os
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import jwt
import pgserver
import uvicorn
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parents[3]
API_PORT = int(os.environ.get("RIG_API_PORT", "8100"))
AUTH_PORT = int(os.environ.get("RIG_AUTH_PORT", "54399"))
WEB_ORIGIN = os.environ.get("CORS_ORIGINS", "http://localhost:3100")
AUTH_URL = f"http://localhost:{AUTH_PORT}"
ISSUER = f"{AUTH_URL}/auth/v1"
KID = "rig-key"

data_dir = tempfile.mkdtemp(prefix="recall-rig-", dir="/tmp")
pg = pgserver.get_server(data_dir, cleanup_mode="stop")  # type: ignore[attr-defined]
pg.psql((ROOT / "supabase/local/auth_stub.sql").read_text())
for migration in sorted((ROOT / "supabase/migrations").glob("*.sql")):
    pg.psql(migration.read_text())
socket_dir = pg.get_uri().split("host=")[1]

os.environ.update(
    DATABASE_URL=f"postgresql+asyncpg://postgres@/postgres?host={socket_dir}",
    SUPABASE_URL=AUTH_URL,
    CORS_ORIGINS=WEB_ORIGIN,
    WORKER_POLL_SECONDS="0.2",
)
os.environ.pop("SUPABASE_JWT_SECRET", None)

private_key = ec.generate_private_key(ec.SECP256R1())
public_jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(private_key.public_key()))
public_jwk.update({"kid": KID, "alg": "ES256", "use": "sig"})

users: dict[str, dict[str, Any]] = {}
refresh_tokens: dict[str, dict[str, Any]] = {}
auth = FastAPI()
auth.add_middleware(
    CORSMiddleware,
    allow_origins=[WEB_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "aud": "authenticated",
        "role": "authenticated",
        "email": user["email"],
        "app_metadata": {"provider": "email"},
        "user_metadata": user["user_metadata"],
        "created_at": "2026-11-07T00:00:00Z",
    }


def session_for(user: dict[str, Any]) -> dict[str, Any]:
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": user["id"],
            "aud": "authenticated",
            "iss": ISSUER,
            "role": "authenticated",
            "email": user["email"],
            "iat": now,
            "exp": now + 3600,
            "session_id": str(uuid.uuid4()),
            "user_metadata": user["user_metadata"],
        },
        private_key,
        algorithm="ES256",
        headers={"kid": KID},
    )
    refresh = uuid.uuid4().hex
    refresh_tokens[refresh] = user
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 3600,
        "expires_at": now + 3600,
        "refresh_token": refresh,
        "user": public_user(user),
    }


def create_user(email: str, password: str, metadata: dict[str, Any]) -> dict[str, Any]:
    user = {
        "id": str(uuid.uuid4()),
        "email": email,
        "password": password,
        "user_metadata": metadata,
    }
    users[email] = user
    meta = json.dumps(metadata).replace("'", "''")
    # Fires the real signup trigger.
    pg.psql(
        "insert into auth.users (id, email, raw_user_meta_data) "
        f"values ('{user['id']}', '{email}', '{meta}');"
    )
    return user


def _json(body: dict[str, Any], status: int = 200) -> Response:
    return Response(json.dumps(body), status_code=status, media_type="application/json")


@auth.get("/auth/v1/.well-known/jwks.json")
def jwks() -> dict[str, Any]:
    return {"keys": [public_jwk]}


@auth.post("/auth/v1/signup")
async def signup(request: Request) -> dict[str, Any]:
    body = await request.json()
    if body["email"] in users:
        raise HTTPException(422, {"code": "user_already_exists", "msg": "exists"})
    return session_for(create_user(body["email"], body["password"], body.get("data") or {}))


@auth.post("/auth/v1/token")
async def token(request: Request, grant_type: str) -> Response:
    body = await request.json()
    if grant_type == "password":
        user = users.get(body["email"])
        if not user or user["password"] != body["password"]:
            return _json({"error_code": "invalid_credentials", "msg": "Invalid credentials"}, 400)
    else:
        user = refresh_tokens.get(body["refresh_token"])
        if not user:
            return _json({"error_code": "refresh_token_not_found", "msg": "Unknown token"}, 400)
    return _json(session_for(user))


@auth.post("/auth/v1/logout")
def logout() -> Response:
    return Response(status_code=204)


@auth.get("/auth/v1/user")
def get_user(request: Request) -> dict[str, Any]:
    claims = jwt.decode(
        request.headers["authorization"].split()[1],
        private_key.public_key(),
        algorithms=["ES256"],
        audience="authenticated",
    )
    return public_user(users[claims["email"]])


create_user("demo@example.com", "e2e-demo-password", {"full_name": "Demo Account"})


def serve(app: FastAPI, port: int) -> None:
    uvicorn.Server(uvicorn.Config(app, port=port, log_level="warning")).run()


threading.Thread(target=serve, args=(auth, AUTH_PORT), daemon=True).start()

# Imported only now, because they read the environment set above.
import app.main as api_main  # noqa: E402
from app.providers.registry import get_providers  # noqa: E402
from tests.fakes import fake_providers  # noqa: E402

providers = fake_providers()
setattr(api_main, "get_providers", lambda: providers)  # noqa: B010
api_main.app.dependency_overrides[get_providers] = lambda: providers

# Uvicorn re-raises the stop signal once it's finished, which would skip any cleanup after
# it. So it runs in a thread, and this main thread owns the signal and the cleanup.
stop = threading.Event()
signal.signal(signal.SIGTERM, lambda *_: stop.set())
signal.signal(signal.SIGINT, lambda *_: stop.set())
threading.Thread(target=serve, args=(api_main.app, API_PORT), daemon=True).start()
stop.wait()

# "immediate" ends the workers' open connections, which a polite stop would wait for.
pg_ctl = Path(pgserver.__file__).parent / "pginstall/bin/pg_ctl"
subprocess.run(
    [str(pg_ctl), "-D", data_dir, "stop", "-m", "immediate"], check=False, capture_output=True
)
shutil.rmtree(data_dir, ignore_errors=True)
