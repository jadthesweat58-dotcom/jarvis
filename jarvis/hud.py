"""Live HUD widgets for the dashboard: market prices, headlines and football scores.

All sources are free and need no key. Each is fetched and cached on its own,
and a source that fails (or changes its format) simply disappears from the
strip instead of breaking the dashboard.

- Crypto: CoinGecko            - Stocks, indices, gold, oil: Stooq
- Headlines: Google News (UAE) - Football: ESPN scoreboards
"""

from __future__ import annotations

import csv
import io
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable
from xml.etree import ElementTree

import httpx

from jarvis.tools import Context

log = logging.getLogger("jarvis.hud")

DEFAULTS = {"tickers": ["BTC", "ETH", "GOLD", "SPX"], "leagues": ["eng.1"], "news": True}
CRYPTO = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "XRP": "ripple", "DOGE": "dogecoin",
          "BNB": "binancecoin", "ADA": "cardano", "TON": "the-open-network", "USDT": "tether",
          "AVAX": "avalanche-2", "DOT": "polkadot", "LTC": "litecoin", "TRX": "tron", "LINK": "chainlink"}
# Friendly names for Stooq symbols; anything else is treated as a US stock ticker.
STOOQ = {"GOLD": ("xauusd", "Gold"), "SILVER": ("xagusd", "Silver"), "OIL": ("cb.f", "Brent oil"),
         "SPX": ("^spx", "S&P 500"), "SP500": ("^spx", "S&P 500"), "NASDAQ": ("^ndq", "Nasdaq"),
         "DOW": ("^dji", "Dow Jones"), "EURUSD": ("eurusd", "EUR/USD"), "GBPUSD": ("gbpusd", "GBP/USD"),
         "USDJPY": ("usdjpy", "USD/JPY"), "NIKKEI": ("^nkx", "Nikkei"), "FTSE": ("^ukx", "FTSE 100")}
LEAGUES = {"eng.1": "Premier League", "esp.1": "LaLiga", "ita.1": "Serie A", "ger.1": "Bundesliga",
           "fra.1": "Ligue 1", "uefa.champions": "Champions League", "uefa.europa": "Europa League",
           "ksa.1": "Saudi Pro League", "usa.1": "MLS", "fifa.world": "World Cup"}
NEWS_URL = "https://news.google.com/rss?hl=en-AE&gl=AE&ceid=AE:en"
TTL = {"markets": 180, "news": 300, "football": 120}
MAX_TICKERS = 12

_cache: dict[str, tuple[float, Any]] = {}
_lock = threading.Lock()


def settings(ctx: Context) -> dict[str, Any]:
    try:
        stored = json.loads(ctx.db.get_kv("hud") or "{}")
    except ValueError:
        stored = {}
    return {**DEFAULTS, **{k: v for k, v in stored.items() if k in DEFAULTS}}


def save_settings(ctx: Context, values: dict[str, Any]) -> dict[str, Any]:
    current = settings(ctx)
    tickers = [str(t).strip().upper().lstrip("^$")[:12] for t in values.get("tickers", current["tickers"]) if str(t).strip()]
    leagues = [str(l).strip().lower() for l in values.get("leagues", current["leagues"]) if str(l).strip() in LEAGUES]
    merged = {"tickers": list(dict.fromkeys(tickers))[:MAX_TICKERS], "leagues": list(dict.fromkeys(leagues))[:4],
              "news": bool(values.get("news", current["news"]))}
    ctx.db.set_kv("hud", json.dumps(merged))
    with _lock:
        _cache.clear()
    return merged


def _cached(key: str, ttl: float, make: Callable[[], Any]) -> Any:
    with _lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
    try:
        value = make()
    except Exception as exc:
        log.info("HUD source %s unavailable: %s", key.split(":")[0], type(exc).__name__)
        value = hit[1] if hit else []  # keep showing the last good data
        ttl_left = 60  # try again in a minute
        with _lock:
            _cache[key] = (time.time() - ttl + ttl_left, value)
        return value
    with _lock:
        _cache[key] = (time.time(), value)
    return value


def _get(url: str, http: Any = None, **params: Any) -> httpx.Response:
    resp = (http or httpx).get(url, params=params or None, timeout=8, follow_redirects=True,
                               headers={"User-Agent": "Mozilla/5.0 (compatible; JarvisAssistant/1.0)"})
    resp.raise_for_status()
    return resp


# ------------------------------------------------------------------ markets
def crypto_quotes(symbols: list[str], http: Any = None) -> list[dict[str, Any]]:
    ids = {CRYPTO[s]: s for s in symbols if s in CRYPTO}
    if not ids:
        return []
    data = _get("https://api.coingecko.com/api/v3/simple/price", http, ids=",".join(ids),
                vs_currencies="usd", include_24hr_change="true").json()
    out = []
    for coin, sym in ids.items():
        row = data.get(coin) or {}
        if row.get("usd") is not None:
            out.append({"symbol": sym, "label": sym, "price": float(row["usd"]), "currency": "USD",
                        "change": round(float(row.get("usd_24h_change") or 0), 2)})
    return out


def stooq_quotes(symbols: list[str], http: Any = None) -> list[dict[str, Any]]:
    wanted = {}
    for sym in symbols:
        if sym in CRYPTO:
            continue
        code, label = STOOQ.get(sym, (f"{sym.lower()}.us", sym))
        wanted[code] = (sym, label)
    if not wanted:
        return []
    from urllib.parse import quote

    text = _get(f"https://stooq.com/q/l/?s={quote(','.join(wanted), safe=',^')}&f=sd2t2ohlc&h&e=csv", http).text
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        code = (row.get("Symbol") or "").lower()
        if code not in wanted:
            continue
        try:
            close, open_ = float(row["Close"]), float(row["Open"])
        except (KeyError, TypeError, ValueError):
            continue  # "N/D": unknown symbol or no trading yet
        sym, label = wanted[code]
        out.append({"symbol": sym, "label": label, "price": close, "currency": "USD",
                    "change": round((close - open_) / open_ * 100, 2) if open_ else 0.0})
    order = {s: i for i, s in enumerate(symbols)}
    return sorted(out, key=lambda q: order.get(q["symbol"], 99))


def quotes(symbols: list[str], http: Any = None) -> list[dict[str, Any]]:
    symbols = [s.upper() for s in symbols]
    found: list[dict[str, Any]] = []
    for part in (crypto_quotes, stooq_quotes):
        try:
            found += part(symbols, http)
        except Exception as exc:
            log.info("Quotes unavailable from %s: %s", part.__name__, type(exc).__name__)
    order = {s: i for i, s in enumerate(symbols)}
    return sorted(found, key=lambda q: order.get(q["symbol"], 99))


# ------------------------------------------------------------------ news
def headlines(http: Any = None, limit: int = 8) -> list[dict[str, str]]:
    root = ElementTree.fromstring(_get(NEWS_URL, http).content)
    out = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        source = (item.findtext("source") or "").strip()
        if source and title.endswith(f" - {source}"):
            title = title[: -len(source) - 3].strip()
        link = (item.findtext("link") or "").strip()
        if title and link.startswith("https://"):
            out.append({"title": title, "source": source, "link": link})
        if len(out) >= limit:
            break
    return out


# ------------------------------------------------------------------ football
def scores(leagues: list[str], http: Any = None, now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    out = []
    for league in leagues:
        data = _get(f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard", http).json()
        for ev in data.get("events", []):
            comp = (ev.get("competitions") or [{}])[0]
            teams = {c.get("homeAway"): c for c in comp.get("competitors", [])}
            home, away = teams.get("home"), teams.get("away")
            status = ((ev.get("status") or comp.get("status") or {}).get("type") or {})
            if not home or not away:
                continue
            try:
                kickoff = datetime.fromisoformat(str(ev.get("date", "")).replace("Z", "+00:00"))
            except ValueError:
                continue
            state = status.get("state", "pre")
            # Live games, results from the last day, and kick-offs in the next day.
            if abs((kickoff - now).total_seconds()) > 36 * 3600 and state != "in":
                continue
            name = lambda c: (c.get("team") or {}).get("shortDisplayName") or (c.get("team") or {}).get("displayName", "?")  # noqa: E731
            out.append({"league": LEAGUES.get(league, league), "home": name(home), "away": name(away),
                        "home_score": home.get("score"), "away_score": away.get("score"), "state": state,
                        "detail": status.get("shortDetail") or status.get("detail") or "", "kickoff": kickoff.isoformat()})
    rank = {"in": 0, "post": 1, "pre": 2}
    return sorted(out, key=lambda m: (rank.get(m["state"], 3), m["kickoff"]))[:8]


# ------------------------------------------------------------------ all together
def data(ctx: Context, http: Any = None) -> dict[str, Any]:
    prefs = settings(ctx)
    jobs = {
        "markets": lambda: _cached("markets:" + ",".join(prefs["tickers"]), TTL["markets"],
                                   lambda: quotes(prefs["tickers"], http)),
        "news": lambda: _cached("news", TTL["news"], lambda: headlines(http)) if prefs["news"] else [],
        "football": lambda: _cached("football:" + ",".join(prefs["leagues"]), TTL["football"],
                                    lambda: scores(prefs["leagues"], http)) if prefs["leagues"] else [],
    }
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {k: pool.submit(f) for k, f in jobs.items()}
        result = {k: f.result() for k, f in futures.items()}
    return {**result, "settings": prefs}
