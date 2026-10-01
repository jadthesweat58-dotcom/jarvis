"""Gmail: read your inbox, draft replies, and send emails you approve.

Uses your own Google Cloud OAuth client (GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET),
so nobody else is in the middle. You connect once from Settings > Connect Gmail.
Jarvis keeps a refresh token in the database, encrypted with a key derived from
your client secret, so the database alone can't be used to open your mail.

Permissions asked for: read mail, and compose (drafts and sending). Jarvis never
sends without your Approve tap.
"""

from __future__ import annotations

import base64
import hashlib
import html
import hmac
import secrets
import threading
import time
from email.message import EmailMessage
from email.utils import getaddresses, parseaddr
from typing import Any
from urllib.parse import urlencode

import httpx

from jarvis.tools import Context

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
API = "https://gmail.googleapis.com/gmail/v1/users/me"
SCOPES = "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.compose"
STATE_SECONDS = 10 * 60
MAX_BODY_CHARS = 12_000

http: Any = httpx.Client(timeout=20)
_tokens: dict[str, tuple[float, str]] = {}   # client id -> (expires at, access token)
_lock = threading.Lock()


class GmailError(Exception):
    pass


# ------------------------------------------------------------------ connecting
def _fernet(ctx: Context):
    from cryptography.fernet import Fernet

    digest = hashlib.sha256(b"jarvis-gmail:" + ctx.settings.google_client_secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def connected_email(ctx: Context) -> str:
    return ctx.db.get_kv("gmail_email") if ctx.db.get_kv("gmail_refresh") else ""


def start(ctx: Context, base_url: str) -> str:
    """The Google sign-in address to send the user to."""
    if not ctx.settings.gmail_configured:
        raise GmailError("Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to the server settings first.")
    state = secrets.token_urlsafe(24)
    redirect = base_url.rstrip("/") + "/google/callback"
    ctx.db.set_kv("gmail_oauth_state", f"{state}|{int(time.time()) + STATE_SECONDS}|{redirect}")
    return AUTH_URL + "?" + urlencode({
        "client_id": ctx.settings.google_client_id, "redirect_uri": redirect, "response_type": "code",
        "scope": SCOPES, "access_type": "offline", "prompt": "consent", "state": state,
        "include_granted_scopes": "true",
    })


def finish(ctx: Context, code: str, state: str) -> str:
    """Complete the sign-in Google redirected back with. Returns the Gmail address."""
    stored = ctx.db.get_kv("gmail_oauth_state")
    expected, _, rest = stored.partition("|")
    expires, _, redirect = rest.partition("|")
    if not (expected and state and hmac.compare_digest(expected.encode(), state.encode())) or int(expires or 0) < time.time():
        raise GmailError("That sign-in link has expired. Start again from Settings > Connect Gmail.")
    ctx.db.set_kv("gmail_oauth_state", "")  # one use only
    resp = http.post(TOKEN_URL, data={
        "code": code, "client_id": ctx.settings.google_client_id, "client_secret": ctx.settings.google_client_secret,
        "redirect_uri": redirect, "grant_type": "authorization_code"})
    data = resp.json() if resp.status_code == 200 else {}
    if not data.get("refresh_token"):
        raise GmailError("Google didn't give Jarvis access. Please try connecting again.")
    ctx.db.set_kv("gmail_refresh", _fernet(ctx).encrypt(data["refresh_token"].encode()).decode())
    with _lock:
        _tokens[ctx.settings.google_client_id] = (time.time() + int(data.get("expires_in", 3600)) - 60,
                                                  data["access_token"])
    email = str(_api(ctx, "GET", "/profile").get("emailAddress", ""))
    ctx.db.set_kv("gmail_email", email)
    return email


def disconnect(ctx: Context) -> None:
    token = _refresh_token(ctx)
    if token:
        try:
            http.post(REVOKE_URL, params={"token": token})
        except Exception:
            pass  # forgetting it locally is what matters
    ctx.db.set_kv("gmail_refresh", "")
    ctx.db.set_kv("gmail_email", "")
    with _lock:
        _tokens.pop(ctx.settings.google_client_id, None)


def _refresh_token(ctx: Context) -> str:
    stored = ctx.db.get_kv("gmail_refresh")
    if not stored or not ctx.settings.gmail_configured:
        return ""
    try:
        return _fernet(ctx).decrypt(stored.encode()).decode()
    except Exception:
        return ""  # the client secret changed: reconnect


def _access_token(ctx: Context) -> str:
    with _lock:
        cached = _tokens.get(ctx.settings.google_client_id)
        if cached and time.time() < cached[0]:
            return cached[1]
    refresh = _refresh_token(ctx)
    if not refresh:
        raise GmailError("Gmail isn't connected. Connect it from Settings (gear) > Connect Gmail.")
    resp = http.post(TOKEN_URL, data={"client_id": ctx.settings.google_client_id,
                                      "client_secret": ctx.settings.google_client_secret,
                                      "refresh_token": refresh, "grant_type": "refresh_token"})
    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    if resp.status_code != 200 or "access_token" not in data:
        if data.get("error") == "invalid_grant":
            ctx.db.set_kv("gmail_refresh", "")
            raise GmailError("Gmail access has expired or was removed. Reconnect it from Settings > Connect Gmail.")
        raise GmailError(f"Google didn't answer properly ({resp.status_code}). Try again shortly.")
    with _lock:
        _tokens[ctx.settings.google_client_id] = (time.time() + int(data.get("expires_in", 3600)) - 60,
                                                  data["access_token"])
    return data["access_token"]


def _api(ctx: Context, method: str, path: str, **kw: Any) -> dict:
    resp = http.request(method, API + path, headers={"Authorization": f"Bearer {_access_token(ctx)}"}, **kw)
    if resp.status_code == 401:
        with _lock:
            _tokens.pop(ctx.settings.google_client_id, None)
        raise GmailError("Gmail refused the request; try again, or reconnect Gmail in Settings.")
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("error", {}).get("message", "")
        except ValueError:
            detail = ""
        raise GmailError(f"Gmail error {resp.status_code}{': ' + detail if detail else ''}")
    return resp.json() if resp.content else {}


# ------------------------------------------------------------------ reading
def _headers(msg: dict) -> dict[str, str]:
    return {h["name"].lower(): h["value"] for h in (msg.get("payload") or {}).get("headers", [])}


def search(ctx: Context, query: str, limit: int = 10) -> list[dict[str, str]]:
    found = _api(ctx, "GET", "/messages", params={"q": query, "maxResults": min(max(limit, 1), 20)})
    out = []
    for ref in found.get("messages", []):
        msg = _api(ctx, "GET", f"/messages/{ref['id']}", params=[("format", "metadata"), ("metadataHeaders", "From"),
                                                                 ("metadataHeaders", "Subject"), ("metadataHeaders", "Date")])
        h = _headers(msg)
        out.append({"id": msg["id"], "from": h.get("from", ""), "subject": h.get("subject", "(no subject)"),
                    "date": h.get("date", ""), "snippet": html.unescape(msg.get("snippet", "")),
                    "unread": "UNREAD" in msg.get("labelIds", [])})
    return out


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")


def _body(payload: dict) -> str:
    """The message text: the plain-text part, or the HTML part turned into text."""
    parts, plain, rich = [payload], [], []
    while parts:
        part = parts.pop(0)
        parts.extend(part.get("parts") or [])
        data = (part.get("body") or {}).get("data")
        if not data:
            continue
        if part.get("mimeType") == "text/plain":
            plain.append(_decode(data))
        elif part.get("mimeType") == "text/html":
            rich.append(_decode(data))
    if plain:
        return "\n".join(plain)
    if rich:
        from jarvis.tools.extras import html_to_text

        return html_to_text("\n".join(rich))[1]
    return ""


def read(ctx: Context, message_id: str) -> dict[str, str]:
    msg = _api(ctx, "GET", f"/messages/{message_id}", params={"format": "full"})
    h = _headers(msg)
    body = _body(msg.get("payload") or {}).strip()
    if len(body) > MAX_BODY_CHARS:
        body = body[:MAX_BODY_CHARS] + "\n[… email cut here]"
    return {"id": msg["id"], "thread": msg.get("threadId", ""), "from": h.get("from", ""), "to": h.get("to", ""),
            "subject": h.get("subject", ""), "date": h.get("date", ""), "body": body,
            "message_id": h.get("message-id", ""), "references": h.get("references", "")}


# ------------------------------------------------------------------ writing
def build(ctx: Context, to: str, subject: str, body: str, reply_to: str | None = None) -> dict:
    """The Gmail API message for a new email or a reply (kept in the same thread)."""
    addresses = [a for _, a in getaddresses([to]) if "@" in a]
    if not addresses:
        raise GmailError("I need a valid email address to write to.")
    msg = EmailMessage()
    msg["To"] = ", ".join(addresses)
    sender = connected_email(ctx)
    if sender:
        msg["From"] = sender
    thread = None
    if reply_to:
        original = read(ctx, reply_to)
        thread = original["thread"]
        if not subject:
            subject = original["subject"] if original["subject"].lower().startswith("re:") else f"Re: {original['subject']}"
        if original["message_id"]:
            msg["In-Reply-To"] = original["message_id"]
            msg["References"] = f"{original['references']} {original['message_id']}".strip()
    msg["Subject"] = subject or "(no subject)"
    msg.set_content(body)
    out: dict = {"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}
    if thread:
        out["threadId"] = thread
    return out


def create_draft(ctx: Context, to: str, subject: str, body: str, reply_to: str | None = None) -> str:
    return _api(ctx, "POST", "/drafts", json={"message": build(ctx, to, subject, body, reply_to)}).get("id", "")


def send(ctx: Context, to: str, subject: str, body: str, reply_to: str | None = None) -> str:
    return _api(ctx, "POST", "/messages/send", json=build(ctx, to, subject, body, reply_to)).get("id", "")


def sender_name(value: str) -> str:
    name, address = parseaddr(value)
    return name or address or value
