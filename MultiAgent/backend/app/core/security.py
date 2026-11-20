"""Password hashing, JWT, secret encryption and token helpers."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

_PBKDF2_ITERATIONS = 310_000
JWT_ALG = "HS256"
JWT_ISSUER = "agentforge"


# --------------------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_b64, hash_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt_b64), int(iterations))
        return hmac.compare_digest(dk, base64.b64decode(hash_b64))
    except Exception:
        return False


# A pre-computed hash used to equalise timing when the user does not exist.
DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def validate_password_strength(password: str) -> str | None:
    if len(password) < 8:
        return "Password must be at least 8 characters"
    if len(password) > 256:
        return "Password is too long"
    classes = sum(bool(any(f(c) for c in password)) for f in (str.islower, str.isupper, str.isdigit))
    if classes < 2 and not any(not c.isalnum() for c in password):
        return "Use a mix of letters, numbers or symbols"
    return None


# --------------------------------------------------------------------------- JWT
def create_access_token(user_id: str, token_version: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "ver": token_version,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_minutes)).timestamp()),
        "iss": JWT_ISSUER,
        "typ": "access",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALG)


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[JWT_ALG], issuer=JWT_ISSUER, options={"require": ["exp", "sub"]}
        )
        if payload.get("typ") != "access":
            return None
        return payload
    except jwt.PyJWTError:
        return None


# --------------------------------------------------------------------------- encryption at rest
def _fernet() -> Fernet:
    key = hashlib.sha256((settings.secret_key + ":enc:v1").encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt(value: str) -> str:
    if not value:
        return ""
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return ""


def encrypt_json(data: dict[str, Any]) -> str:
    return encrypt(json.dumps(data)) if data else ""


def decrypt_json(token: str) -> dict[str, Any]:
    raw = decrypt(token)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "••••"
    return f"{value[:3]}••••{value[-4:]}"


# --------------------------------------------------------------------------- opaque tokens
def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def generate_api_key() -> str:
    return "afk_" + secrets.token_urlsafe(32)


def generate_webhook_token() -> str:
    return "whk_" + secrets.token_urlsafe(24)
