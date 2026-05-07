"""
Clerk JWT verification — the security boundary of the app.

Every protected endpoint depends on `get_current_user`. It:
  1. Pulls the Bearer token out of the Authorization header.
  2. Verifies the JWT signature using Clerk's published public keys (JWKS).
  3. Returns the user_id from the verified token.

If any step fails — missing header, bad signature, expired token — we
raise a 401 and the endpoint never runs.

Why JWKS verification, not "just call Clerk's API to validate the token"?
Performance. Verifying a JWT locally takes microseconds and zero network
calls. Hitting Clerk's API on every request adds 100ms of latency and a
hard dependency on Clerk being up. We fetch the public keys once and
cache them in memory.
"""

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.config import CLERK_JWKS_URL

# PyJWKClient fetches Clerk's public keys from the JWKS URL and caches
# them. The cache auto-refreshes when Clerk rotates keys. One client,
# reused across all requests.
_jwks_client = PyJWKClient(CLERK_JWKS_URL)

# HTTPBearer is FastAPI's helper for extracting "Authorization: Bearer <token>"
# headers. auto_error=False lets us craft our own 401 message instead of
# FastAPI's default.
_bearer_scheme = HTTPBearer(auto_error=False)


class AuthError(HTTPException):
    """401 Unauthorized — token missing, invalid, or expired."""

    def __init__(self, detail: str) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    """
    FastAPI dependency. Verifies the JWT and returns the Clerk user_id.

    Use it on a route like:

        @app.get("/api/me")
        async def me(user_id: str = Depends(get_current_user)):
            return {"user_id": user_id}

    Anything inside the route is unreachable without a valid token.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthError("Missing or malformed Authorization header.")

    token = credentials.credentials

    try:
        # Look up which public key signed this specific token. JWTs carry
        # a key-id (kid) in their header so the verifier knows which of
        # the issuer's keys to use — Clerk rotates keys periodically.
        signing_key = _jwks_client.get_signing_key_from_jwt(token).key

        # Verify signature, expiration (exp), and not-before (nbf).
        # We don't verify "aud" because Clerk doesn't set it by default.
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except jwt.ExpiredSignatureError:
        raise AuthError("Token has expired.")
    except jwt.InvalidTokenError as e:
        raise AuthError(f"Invalid token: {e}")

    # Clerk puts the user ID in the standard "sub" (subject) claim.
    user_id = payload.get("sub")
    if not user_id:
        raise AuthError("Token has no subject claim.")

    return user_id