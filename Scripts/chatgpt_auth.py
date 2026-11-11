"""Local Sign in with ChatGPT authentication for the career assistant.

This module implements the open-source/local OAuth flow documented by OpenAI:
PKCE authorization through a loopback callback, token exchange, ID-token
validation, local credential storage, and refresh-token rotation.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen


AUTH_BASE_URL = "https://auth.openai.com"
API_RESOURCE = "https://api.openai.com/v1"
OAUTH_AUTHORIZE_URL = f"{AUTH_BASE_URL}/api/accounts/authorize"
OAUTH_TOKEN_URL = f"{AUTH_BASE_URL}/api/accounts/oauth/token"
OIDC_CONFIG_URL = f"{AUTH_BASE_URL}/.well-known/openid-configuration"
DEFAULT_CLIENT_ID = "dynamic_agent_client"
APP_NAME = "AI Career Assistant"
CALLBACK_PATH = "/auth/callback"
REQUIRED_SCOPE = "chatgpt.tokens.use.direct"


class ChatGPTAuthError(RuntimeError):
    """Raised when ChatGPT sign-in or token refresh cannot complete."""


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + ("=" * (-len(value) % 4)))


def _http_json(request: Request) -> dict[str, Any]:
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:500]
        raise ChatGPTAuthError(
            f"OpenAI authentication request failed ({error.code}): {detail}"
        ) from error
    except URLError as error:
        raise ChatGPTAuthError(
            "Could not reach OpenAI authentication services. Check your network connection."
        ) from error

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as error:
        raise ChatGPTAuthError("OpenAI authentication returned invalid JSON.") from error

    if not isinstance(payload, dict):
        raise ChatGPTAuthError("OpenAI authentication returned an unexpected response.")

    return payload


def _post_form(url: str, values: dict[str, str]) -> dict[str, Any]:
    request = Request(
        url,
        data=urlencode(values).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    return _http_json(request)


def _decode_jwt_part(value: str) -> dict[str, Any]:
    try:
        decoded = json.loads(_b64url_decode(value).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ChatGPTAuthError("OpenAI returned an invalid ID token.") from error

    if not isinstance(decoded, dict):
        raise ChatGPTAuthError("OpenAI returned an invalid ID token payload.")

    return decoded


def _verify_rs256_signature(signing_input: bytes, signature: bytes, jwk: dict[str, Any]) -> bool:
    """Verify an RS256 JWT signature using only Python's standard library."""

    try:
        modulus = int.from_bytes(_b64url_decode(jwk["n"]), "big")
        exponent = int.from_bytes(_b64url_decode(jwk["e"]), "big")
    except (KeyError, ValueError) as error:
        raise ChatGPTAuthError("OpenAI published an unusable signing key.") from error

    digest_info = bytes.fromhex(
        "3031300d060960864801650304020105000420"
    ) + hashlib.sha256(signing_input).digest()
    key_size = (modulus.bit_length() + 7) // 8
    padding_length = key_size - len(digest_info) - 3

    if padding_length < 8:
        return False

    expected_encoded = (
        b"\x00\x01" + b"\xff" * padding_length + b"\x00" + digest_info
    )
    actual_encoded = pow(
        int.from_bytes(signature, "big"), exponent, modulus
    ).to_bytes(key_size, "big")
    return hmac.compare_digest(actual_encoded, expected_encoded)


def _validate_id_token(id_token: str, client_id: str, nonce: str) -> dict[str, Any]:
    parts = id_token.split(".")
    if len(parts) != 3:
        raise ChatGPTAuthError("OpenAI returned a malformed ID token.")

    header = _decode_jwt_part(parts[0])
    claims = _decode_jwt_part(parts[1])

    if header.get("alg") != "RS256" or not header.get("kid"):
        raise ChatGPTAuthError("OpenAI returned an unsupported ID-token signature.")

    oidc_config = _http_json(Request(OIDC_CONFIG_URL))
    issuer = oidc_config.get("issuer")
    jwks_uri = oidc_config.get("jwks_uri")
    if not isinstance(issuer, str) or not isinstance(jwks_uri, str):
        raise ChatGPTAuthError("OpenAI authentication metadata is incomplete.")

    jwks = _http_json(Request(jwks_uri))
    keys = jwks.get("keys")
    if not isinstance(keys, list):
        raise ChatGPTAuthError("OpenAI authentication signing keys are unavailable.")

    signing_key = next(
        (
            key
            for key in keys
            if isinstance(key, dict) and key.get("kid") == header["kid"]
        ),
        None,
    )
    if signing_key is None or not _verify_rs256_signature(
        f"{parts[0]}.{parts[1]}".encode("ascii"),
        _b64url_decode(parts[2]),
        signing_key,
    ):
        raise ChatGPTAuthError("OpenAI ID-token signature validation failed.")

    if claims.get("iss") != issuer:
        raise ChatGPTAuthError("OpenAI ID-token issuer validation failed.")

    audience = claims.get("aud")
    if not (
        audience == client_id
        or isinstance(audience, list)
        and client_id in audience
    ):
        raise ChatGPTAuthError("OpenAI ID-token audience validation failed.")

    if claims.get("nonce") != nonce:
        raise ChatGPTAuthError("OpenAI ID-token nonce validation failed.")

    try:
        if float(claims["exp"]) <= time.time():
            raise ChatGPTAuthError("OpenAI ID token has expired.")
    except (KeyError, TypeError, ValueError) as error:
        raise ChatGPTAuthError("OpenAI ID-token expiry is invalid.") from error

    if not claims.get("sub"):
        raise ChatGPTAuthError("OpenAI ID token has no account subject.")

    return claims


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Captures one OAuth callback without logging its query parameters."""

    result: dict[str, list[str]] = {}
    completed = False

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        parsed = urlparse(self.path)
        if parsed.path != CALLBACK_PATH:
            self.send_error(404)
            return

        type(self).result = parse_qs(parsed.query, keep_blank_values=True)
        type(self).completed = True
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            b"<html><body><h2>Sign-in complete</h2>"
            b"<p>You can close this browser tab and return to the terminal.</p>"
            b"</body></html>"
        )

    def log_message(self, format: str, *args: Any) -> None:
        return


class ChatGPTAuth:
    """Manage one local ChatGPT-plan authorization for this application."""

    def __init__(self, credentials_path: Path | None = None):
        local_app_data = Path(
            os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
        )
        self.credentials_path = credentials_path or (
            local_app_data / "AI Career Assistant" / "chatgpt_auth.json"
        )

    def has_credentials(self) -> bool:
        return self.credentials_path.exists()

    def get_status(self) -> dict[str, Any]:
        """Return local sign-in status without making a network request."""

        credentials = self._load()
        if not credentials:
            return {"signed_in": False, "email": "", "expires_at": 0}

        expires_at = float(credentials.get("expires_at", 0) or 0)
        return {
            "signed_in": True,
            "email": str(credentials.get("email", "")),
            "expires_at": expires_at,
            "refreshable": bool(credentials.get("refresh_token")),
            "plan_usage_authorized": REQUIRED_SCOPE in set(credentials.get("scopes", [])),
        }

    def sign_out(self) -> None:
        """Remove the local refresh/access tokens for this application."""

        try:
            self.credentials_path.unlink(missing_ok=True)
        except OSError as error:
            raise ChatGPTAuthError("Could not remove the saved ChatGPT sign-in.") from error

    def _load(self) -> dict[str, Any] | None:
        if not self.credentials_path.exists():
            return None

        try:
            value = json.loads(self.credentials_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ChatGPTAuthError(
                "Saved ChatGPT sign-in data could not be read. Run sign-in again."
            ) from error

        if not isinstance(value, dict):
            raise ChatGPTAuthError("Saved ChatGPT sign-in data is invalid. Run sign-in again.")

        return value

    def _save(self, credentials: dict[str, Any]) -> None:
        self.credentials_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.credentials_path.with_suffix(".tmp")
        temporary_path.write_text(
            json.dumps(credentials, indent=2),
            encoding="utf-8",
        )
        os.replace(temporary_path, self.credentials_path)
        try:
            os.chmod(self.credentials_path, 0o600)
        except OSError:
            pass

    def _refresh(self, credentials: dict[str, Any]) -> str:
        refresh_token = credentials.get("refresh_token")
        client_id = credentials.get("client_id")
        if not refresh_token or not client_id:
            raise ChatGPTAuthError(
                "ChatGPT sign-in has expired. Run `python Scripts/sign_in_with_chatgpt.py`."
            )

        token_response = _post_form(
            OAUTH_TOKEN_URL,
            {
                "grant_type": "refresh_token",
                "client_id": str(client_id),
                "refresh_token": str(refresh_token),
                "resource": API_RESOURCE,
            },
        )
        access_token = token_response.get("access_token")
        if not access_token:
            raise ChatGPTAuthError(
                "ChatGPT sign-in could not be refreshed. Run the sign-in command again."
            )

        credentials.update(
            {
                "access_token": access_token,
                "refresh_token": token_response.get("refresh_token", refresh_token),
                "token_type": token_response.get("token_type", "Bearer"),
                "expires_at": time.time() + float(token_response.get("expires_in", 3600)),
                "saved_at": time.time(),
            }
        )
        self._save(credentials)
        return str(access_token)

    def get_access_token(self) -> str:
        credentials = self._load()
        if not credentials:
            raise ChatGPTAuthError(
                "ChatGPT sign-in is required. Run `python Scripts/sign_in_with_chatgpt.py`."
            )

        scopes = set(credentials.get("scopes", []))
        if REQUIRED_SCOPE not in scopes:
            raise ChatGPTAuthError(
                "ChatGPT plan usage was not authorized. Run the sign-in command again "
                "and approve plan usage."
            )

        access_token = credentials.get("access_token")
        expires_at = float(credentials.get("expires_at", 0))
        if access_token and expires_at > time.time() + 60:
            return str(access_token)

        return self._refresh(credentials)

    def sign_in(self) -> dict[str, Any]:
        credentials = self._load() or {}
        host_id = credentials.get("ext_agent_host_id") or f"urn:uuid:{uuid.uuid4()}"
        saved_client_id = credentials.get("client_id")
        client_id = str(saved_client_id or DEFAULT_CLIENT_ID)
        state = _b64url_encode(secrets.token_bytes(32))
        nonce = _b64url_encode(secrets.token_bytes(32))
        code_verifier = _b64url_encode(secrets.token_bytes(48))
        code_challenge = _b64url_encode(hashlib.sha256(code_verifier.encode()).digest())

        class CallbackHandler(_OAuthCallbackHandler):
            result = {}
            completed = False

        try:
            server = ThreadingHTTPServer(("127.0.0.1", 1455), CallbackHandler)
        except OSError:
            server = ThreadingHTTPServer(("127.0.0.1", 0), CallbackHandler)

        port = server.server_address[1]
        redirect_uri = f"http://127.0.0.1:{port}{CALLBACK_PATH}"
        authorization_values = {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct",
            "resource": API_RESOURCE,
            "state": state,
            "nonce": nonce,
            "code_challenge_method": "S256",
            "code_challenge": code_challenge,
            "ext_agent_host_id": host_id,
        }
        if not saved_client_id:
            authorization_values["agent_name_hint"] = APP_NAME
        else:
            if credentials.get("id_token"):
                authorization_values["id_token_hint"] = str(credentials["id_token"])
            if credentials.get("email"):
                authorization_values["login_hint"] = str(credentials["email"])

        authorization_url = f"{OAUTH_AUTHORIZE_URL}?{urlencode(authorization_values)}"
        print("Opening OpenAI sign-in in your browser...")
        if not webbrowser.open(authorization_url):
            print("Open this URL manually:")
            print(authorization_url)

        server.timeout = 1
        deadline = time.time() + 300
        try:
            while not CallbackHandler.completed and time.time() < deadline:
                server.handle_request()
        finally:
            server.server_close()

        if not CallbackHandler.completed:
            raise ChatGPTAuthError("Timed out waiting for the ChatGPT sign-in callback.")

        callback = CallbackHandler.result
        returned_state = callback.get("state", [""])[0]
        if not hmac.compare_digest(returned_state, state):
            raise ChatGPTAuthError("ChatGPT sign-in state validation failed.")

        callback_error = callback.get("error", [""])[0]
        if callback_error:
            description = callback.get("error_description", [callback_error])[0]
            raise ChatGPTAuthError(f"ChatGPT sign-in was not completed: {description}")

        code = callback.get("code", [""])[0]
        issued_client_id = callback.get("client_id", [client_id])[0]
        if not code or not issued_client_id or issued_client_id == DEFAULT_CLIENT_ID:
            raise ChatGPTAuthError("ChatGPT sign-in did not return a usable authorization code.")

        token_response = _post_form(
            OAUTH_TOKEN_URL,
            {
                "grant_type": "authorization_code",
                "client_id": issued_client_id,
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
                "resource": API_RESOURCE,
            },
        )
        access_token = token_response.get("access_token")
        refresh_token = token_response.get("refresh_token")
        id_token = token_response.get("id_token")
        if not access_token or not refresh_token or not id_token:
            raise ChatGPTAuthError("ChatGPT sign-in returned incomplete credentials.")

        claims = _validate_id_token(str(id_token), issued_client_id, nonce)
        scopes = set(str(token_response.get("scope", "")).split())
        scopes.update(callback.get("scope", [""])[0].split())
        if REQUIRED_SCOPE not in scopes:
            raise ChatGPTAuthError(
                "ChatGPT plan usage was not authorized. Run sign-in again and approve it."
            )

        stored_credentials = {
            "email": claims.get("email", ""),
            "issuer": claims.get("iss", ""),
            "subject": claims["sub"],
            "client_id": issued_client_id,
            "ext_agent_host_id": host_id,
            "id_token": id_token,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": token_response.get("token_type", "Bearer"),
            "expires_at": time.time() + float(token_response.get("expires_in", 3600)),
            "scopes": sorted(scopes),
            "saved_at": time.time(),
        }
        self._save(stored_credentials)
        return stored_credentials
