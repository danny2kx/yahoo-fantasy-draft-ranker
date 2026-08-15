"""Yahoo OAuth2 session with durable token persistence.

Yahoo rotates the refresh token on every refresh and invalidates the old one.
A token file written non-atomically can therefore be left truncated by a crash
mid-write, which locks the account out with no way back except a manual
re-authorization. Every write here goes to a temp file and is then renamed.
"""

import json
import os
import time
import webbrowser
from pathlib import Path
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

load_dotenv()

AUTH_URL = "https://api.login.yahoo.com/oauth2/request_auth"
TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
TOKEN_PATH = Path(__file__).parent / "tokens" / "yahoo.json"

# Yahoo access tokens live one hour. Refresh early so a long job cannot expire
# mid-run.
REFRESH_MARGIN_SECONDS = 300


def _save_tokens(tokens: dict) -> None:
    TOKEN_PATH.parent.mkdir(exist_ok=True)
    tmp = TOKEN_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(tokens, indent=2))
    tmp.replace(TOKEN_PATH)


def _load_tokens() -> dict | None:
    if not TOKEN_PATH.exists():
        return None
    return json.loads(TOKEN_PATH.read_text())


def _credentials() -> tuple[str, str, str]:
    client_id = os.environ.get("YAHOO_CLIENT_ID", "")
    client_secret = os.environ.get("YAHOO_CLIENT_SECRET", "")
    redirect_uri = os.environ.get("YAHOO_REDIRECT_URI", "https://localhost:8077")
    if not client_id or not client_secret:
        raise SystemExit(
            "YAHOO_CLIENT_ID / YAHOO_CLIENT_SECRET missing.\n"
            "Copy .env.example to .env and fill them in from "
            "https://developer.yahoo.com/apps/"
        )
    return client_id, client_secret, redirect_uri


def _exchange(payload: dict) -> dict:
    client_id, client_secret, _ = _credentials()
    response = requests.post(
        TOKEN_URL, data=payload, auth=(client_id, client_secret), timeout=30
    )
    response.raise_for_status()
    tokens = response.json()
    tokens["expires_at"] = time.time() + tokens["expires_in"]
    _save_tokens(tokens)
    return tokens


def _authorize_interactively() -> dict:
    client_id, _, redirect_uri = _credentials()
    query = urlencode(
        {"client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code"}
    )
    url = f"{AUTH_URL}?{query}"
    print("Opening browser to authorize. If it does not open, visit:\n" + url)
    webbrowser.open(url)
    print(
        "\nAfter approving, the browser lands on a page that will not load "
        "(nothing is listening on that port -- this is expected).\n"
        "Copy the value of 'code=' out of the address bar and paste it here."
    )
    code = input("code: ").strip()
    return _exchange(
        {"grant_type": "authorization_code", "redirect_uri": redirect_uri, "code": code}
    )


def get_access_token() -> str:
    """Return a valid access token, authorizing or refreshing as needed."""
    tokens = _load_tokens()
    if tokens is None:
        tokens = _authorize_interactively()
    elif tokens["expires_at"] - REFRESH_MARGIN_SECONDS < time.time():
        tokens = _exchange(
            {"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"]}
        )
    return tokens["access_token"]


def api_get(path: str) -> dict:
    """GET a Yahoo Fantasy API path, e.g. 'league/nfl.l.864440/settings'."""
    url = f"https://fantasysports.yahooapis.com/fantasy/v2/{path}"
    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {get_access_token()}"},
        params={"format": "json"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()
