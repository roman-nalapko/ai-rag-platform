import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Any

from app.core.config import settings


class InvalidTokenError(ValueError):
    """Raised when a JWT is missing, malformed, expired, or invalid."""


def create_access_token(user_id: uuid.UUID) -> tuple[str, int]:
    expires_in = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    expires_at = int(time.time()) + expires_in
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user_id),
        "exp": expires_at,
        "iat": int(time.time()),
    }
    signing_input = (
        f"{_base64url_json(header)}.{_base64url_json(payload)}".encode("ascii")
    )
    signature = _sign(signing_input)
    return f"{signing_input.decode('ascii')}.{signature}", expires_in


def decode_access_token(token: str) -> uuid.UUID:
    try:
        header_segment, payload_segment, signature = token.split(".")
    except ValueError as error:
        raise InvalidTokenError("Invalid token") from error

    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    expected_signature = _sign(signing_input)
    if not hmac.compare_digest(signature, expected_signature):
        raise InvalidTokenError("Invalid token")

    header = _decode_segment(header_segment)
    if header.get("alg") != "HS256" or header.get("typ") != "JWT":
        raise InvalidTokenError("Invalid token")

    payload = _decode_segment(payload_segment)
    expires_at = payload.get("exp")
    if not isinstance(expires_at, int) or expires_at < int(time.time()):
        raise InvalidTokenError("Token has expired")

    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise InvalidTokenError("Invalid token")

    try:
        return uuid.UUID(subject)
    except ValueError as error:
        raise InvalidTokenError("Invalid token") from error


def _base64url_json(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
    return _base64url_encode(encoded)


def _decode_segment(segment: str) -> dict[str, Any]:
    try:
        decoded = base64.urlsafe_b64decode(_restore_padding(segment))
        payload = json.loads(decoded)
    except (ValueError, json.JSONDecodeError) as error:
        raise InvalidTokenError("Invalid token") from error
    if not isinstance(payload, dict):
        raise InvalidTokenError("Invalid token")
    return payload


def _sign(signing_input: bytes) -> str:
    digest = hmac.new(
        settings.JWT_SECRET_KEY.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    return _base64url_encode(digest)


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _restore_padding(value: str) -> bytes:
    return f"{value}{'=' * (-len(value) % 4)}".encode("ascii")
