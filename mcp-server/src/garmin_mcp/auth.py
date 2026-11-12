"""Keycloak JWT token verification for MCP OAuth.

The verifier keeps two failures apart that the SDK would otherwise both answer with 401:

- **The token is bad** (signature, issuer, expiry, unknown key): `verify_token` returns None → 401.
- **Keycloak can't be reached**, so the token can't be checked at all: `AuthServerUnavailable`
  → 503 + Retry-After, via `AuthServerUnavailableMiddleware`.

The difference matters to the client: a 401 sends it into OAuth recovery (refresh, re-discovery),
and if Keycloak is down at that moment the refresh fails and the connector drops its grant for good
(astronomy-mcp on 2026-11-12: after a dockerd restart the MCP servers were up ~6 s before Keycloak).
A 503 is a transient server error; the client keeps its tokens.

Two measures keep even the 503 rare:
- a JWKS fetch that fails is retried for up to `jwks_wait` seconds, which covers Keycloak's startup;
- a key that has verified a token before is used even when refreshing the JWKS fails
  (stale-if-error), so a Keycloak restart alone goes unnoticed.
"""

import logging
import time

import anyio
import anyio.to_thread
import jwt
from jwt import PyJWK, PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWTError
from mcp.server.auth.provider import AccessToken, TokenVerifier
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)


class AuthServerUnavailable(Exception):
    """The JWKS couldn't be fetched: the token can be neither accepted nor rejected."""


class KeycloakTokenVerifier(TokenVerifier):
    """Validates Keycloak-issued RS256 JWTs against the realm's JWKS."""

    def __init__(self, jwks_url: str, issuer: str, *, jwks_wait: float = 20.0):
        self.issuer = issuer
        self._jwks_client = PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=300, timeout=5)
        self._jwks_wait = jwks_wait
        self._known_keys: dict[str, PyJWK] = {}

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            signing_key = await self._signing_key(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=self.issuer,
                options={"verify_aud": False},
            )
        except PyJWTError:
            return None
        return AccessToken(
            token=token,
            client_id=payload.get("azp", payload.get("client_id", "")),
            scopes=payload.get("scope", "").split(),
            expires_at=payload.get("exp"),
        )

    async def _signing_key(self, token: str) -> PyJWK:
        """The JWKS key named by the token's `kid`.

        Raises PyJWTError when the token is malformed or Keycloak has no such key, and
        AuthServerUnavailable when the JWKS stays unreachable and the key isn't known from before.
        """
        kid = jwt.get_unverified_header(token).get("kid")
        deadline = time.monotonic() + self._jwks_wait
        delay = 0.5
        while True:
            try:
                # PyJWKClient fetches with blocking urllib (on a cold or expired cache): keep it off the event loop.
                key = await anyio.to_thread.run_sync(self._jwks_client.get_signing_key_from_jwt, token)
            except PyJWKClientConnectionError as exc:
                if kid in self._known_keys:
                    logger.warning("JWKS unreachable (%s), verifying with the cached key %s", exc, kid)
                    return self._known_keys[kid]
                if time.monotonic() + delay > deadline:
                    logger.error("JWKS still unreachable after %.0f s: %s", self._jwks_wait, exc)
                    raise AuthServerUnavailable(str(exc)) from exc
                await anyio.sleep(delay)
                delay = min(delay * 2, 4.0)
            else:
                self._known_keys[key.key_id] = key
                return key


class AuthServerUnavailableMiddleware:
    """Answers AuthServerUnavailable with 503 + Retry-After instead of the 500 Starlette would send.

    It has to wrap Starlette's AuthenticationMiddleware, which calls the verifier. Add it with
    `app.add_middleware()`: that puts it first among the user middleware, outside the SDK's auth
    middleware and inside ServerErrorMiddleware. The verifier runs before the endpoint has sent
    anything, so a fresh response can always be started.
    """

    def __init__(self, app: ASGIApp, retry_after: int = 10):
        self.app = app
        self.retry_after = retry_after

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        try:
            await self.app(scope, receive, send)
        except AuthServerUnavailable:
            response = JSONResponse(
                {
                    "error": "temporarily_unavailable",
                    "error_description": "The authorization server is unreachable; retry shortly.",
                },
                status_code=503,
                headers={"Retry-After": str(self.retry_after)},
            )
            await response(scope, receive, send)
