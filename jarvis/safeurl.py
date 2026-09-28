"""Fetching web addresses safely.

Jarvis can be asked (or tricked, by text on a web page) into fetching any URL.
On a cloud server that must never reach the server's own private network, so
every address, including each redirect, has to resolve to a public IP.
"""

from __future__ import annotations

import ipaddress
import socket
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

MAX_REDIRECTS = 5


class UnsafeURL(ValueError):
    pass


def check_url(url: str) -> str:
    """Raise UnsafeURL unless ``url`` is http(s) and its host is on the public internet."""
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise UnsafeURL("Only http and https web addresses can be opened.")
    if parts.username or parts.password:
        raise UnsafeURL("Web addresses with passwords in them aren't allowed.")
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80),
                                   type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeURL(f"I couldn't find the website {parts.hostname}.") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if not ip.is_global or ip.is_multicast:
            raise UnsafeURL("That address points to a private network, which Jarvis won't open.")
    return url.strip()


def fetch(url: str, *, max_bytes: int = 2_000_000, timeout: float = 20,
          client: Any = None, headers: dict | None = None) -> tuple[str, str, bytes]:
    """GET a public URL, following redirects safely. Returns (final url, content type, body)."""
    http = client or httpx.Client(timeout=timeout)
    try:
        for _ in range(MAX_REDIRECTS + 1):
            check_url(url)
            with http.stream("GET", url, follow_redirects=False, headers={
                "User-Agent": "Mozilla/5.0 (compatible; JarvisAssistant/1.0)",
                "Accept": "text/html,application/xhtml+xml,text/plain,application/pdf;q=0.9,*/*;q=0.5",
                **(headers or {}),
            }) as resp:
                if resp.status_code in (301, 302, 303, 307, 308) and resp.headers.get("location"):
                    url = urljoin(url, resp.headers["location"])
                    continue
                if resp.status_code >= 400:
                    raise UnsafeURL(f"The website answered with error {resp.status_code}.")
                body = bytearray()
                for chunk in resp.iter_bytes():
                    body += chunk
                    if len(body) > max_bytes:
                        break
                return url, resp.headers.get("content-type", ""), bytes(body[:max_bytes])
        raise UnsafeURL("Too many redirects.")
    finally:
        if client is None:
            http.close()
