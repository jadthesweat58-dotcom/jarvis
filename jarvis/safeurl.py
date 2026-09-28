"""Fetching web addresses safely.

Jarvis can be asked (or tricked, by text on a web page) into fetching any URL.
On a cloud server that must never reach the server's own private network, so
every address, including each redirect, has to resolve to a public IP.
"""

from __future__ import annotations

import ipaddress
import socket
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

MAX_REDIRECTS = 5


class UnsafeURL(ValueError):
    pass


def _resolve(url: str) -> tuple[str, str]:
    """(hostname, a checked public IP) for ``url``; raises UnsafeURL otherwise."""
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise UnsafeURL("Only http and https web addresses can be opened.")
    if parts.username or parts.password:
        raise UnsafeURL("Web addresses with passwords in them aren't allowed.")
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80),
                                   type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError) as exc:
        raise UnsafeURL(f"I couldn't find the website {parts.hostname}.") from exc
    ips = []
    for info in infos:
        try:
            ip = ipaddress.ip_address(str(info[4][0]).split("%")[0])
        except ValueError as exc:
            raise UnsafeURL("That web address doesn't resolve to a normal internet address.") from exc
        if not ip.is_global or ip.is_multicast:
            raise UnsafeURL("That address points to a private network, which Jarvis won't open.")
        ips.append(ip)
    if not ips:
        raise UnsafeURL(f"I couldn't find the website {parts.hostname}.")
    return parts.hostname, str(ips[0])


def check_url(url: str) -> str:
    """Raise UnsafeURL unless ``url`` is http(s) and its host is on the public internet."""
    _resolve(url)
    return url.strip()


def _pinned(url: str) -> tuple[str, dict, dict]:
    """The request aimed at the exact IP that was checked, so a second DNS lookup
    can't send it somewhere else ("DNS rebinding"). TLS still verifies the real name."""
    parts = urlsplit(url.strip())
    host, ip = _resolve(url)
    address = f"[{ip}]" if ":" in ip else ip
    netloc = f"{address}:{parts.port}" if parts.port else address
    target = urlunsplit((parts.scheme, netloc, parts.path or "/", parts.query, ""))
    host_header = host if not parts.port else f"{host}:{parts.port}"
    extensions = {"sni_hostname": host} if parts.scheme == "https" else {}
    return target, {"Host": host_header}, extensions


def fetch(url: str, *, max_bytes: int = 2_000_000, timeout: float = 20,
          client: Any = None, headers: dict | None = None) -> tuple[str, str, bytes]:
    """GET a public URL, following redirects safely. Returns (final url, content type, body)."""
    http = client or httpx.Client(timeout=timeout, trust_env=False)
    try:
        for _ in range(MAX_REDIRECTS + 1):
            target, host_header, extensions = _pinned(url)
            with http.stream("GET", target, follow_redirects=False, extensions=extensions, headers={
                "User-Agent": "Mozilla/5.0 (compatible; JarvisAssistant/1.0)",
                "Accept": "text/html,application/xhtml+xml,text/plain,application/pdf;q=0.9,*/*;q=0.5",
                **(headers or {}), **host_header,
            }) as resp:
                if resp.status_code in (301, 302, 303, 307, 308) and resp.headers.get("location"):
                    url = urljoin(url, resp.headers["location"])  # re-checked on the next round
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
