import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from jarvis import hud
from jarvis.brain import Brain
from jarvis.server import create_app
from jarvis.tools import REGISTRY, ToolError, load_all
from tests.conftest import FakeClaude

NOW = datetime(2026, 9, 29, 18, 0, tzinfo=timezone.utc)
COINGECKO = {"bitcoin": {"usd": 63120.5, "usd_24h_change": 2.137}, "ethereum": {"usd": 2410.1, "usd_24h_change": -1.5}}
STOOQ = ("Symbol,Date,Time,Open,High,Low,Close\n"
         "XAUUSD,2026-09-29,17:59:00,2650.1,2672,2640,2665.3\n"
         "^SPX,2026-09-29,17:59:00,5800,5850,5790,5829\n"
         "FAKE.US,N/D,N/D,N/D,N/D,N/D,N/D\n")
RSS = """<?xml version="1.0"?><rss><channel>
<item><title>Dubai Metro Blue Line opens - Gulf News</title><link>https://news.google.com/a1</link><source url="x">Gulf News</source></item>
<item><title>Oil steadies as OPEC meets - Reuters</title><link>https://news.google.com/a2</link><source url="y">Reuters</source></item>
<item><title>Bad link</title><link>javascript:alert(1)</link></item>
</channel></rss>"""


def espn(events):
    return {"events": events}


def match(home, away, hs, as_, state, detail, when):
    return {"date": when.strftime("%Y-%m-%dT%H:%MZ"), "status": {"type": {"state": state, "shortDetail": detail}},
            "competitions": [{"competitors": [
                {"homeAway": "home", "score": hs, "team": {"shortDisplayName": home}},
                {"homeAway": "away", "score": as_, "team": {"shortDisplayName": away}}]}]}


class FakeHTTP:
    def __init__(self, fail=()):
        self.urls, self.fail = [], set(fail)

    def get(self, url, params=None, **kw):
        self.urls.append(url)
        host = httpx.URL(url).host
        if host in self.fail:
            raise httpx.ConnectError("down")
        if "coingecko" in host:
            body = json.dumps(COINGECKO)
        elif "stooq" in host:
            body = STOOQ
        elif "news.google" in host:
            body = RSS
        else:
            body = json.dumps(espn([
                match("Arsenal", "Chelsea", "2", "1", "post", "FT", NOW - timedelta(hours=3)),
                match("Liverpool", "Spurs", "1", "1", "in", "67'", NOW - timedelta(hours=1)),
                match("Everton", "Fulham", "0", "0", "pre", "Sat 7:30 PM", NOW + timedelta(hours=20)),
                match("Old", "Game", "3", "0", "post", "FT", NOW - timedelta(days=5)),
            ]))
        return SimpleNamespace(json=lambda: json.loads(body), text=body, content=body.encode(), raise_for_status=lambda: None)


@pytest.fixture(autouse=True)
def fresh():
    hud._cache.clear()
    yield
    hud._cache.clear()


def test_parsers():
    http = FakeHTTP()
    assert hud.quotes(["BTC", "GOLD", "ETH", "SPX", "FAKE"], http) == [
        {"symbol": "BTC", "label": "BTC", "price": 63120.5, "currency": "USD", "change": 2.14},
        {"symbol": "GOLD", "label": "Gold", "price": 2665.3, "currency": "USD", "change": 0.57},
        {"symbol": "ETH", "label": "ETH", "price": 2410.1, "currency": "USD", "change": -1.5},
        {"symbol": "SPX", "label": "S&P 500", "price": 5829.0, "currency": "USD", "change": 0.5},
    ]
    assert hud.headlines(http) == [
        {"title": "Dubai Metro Blue Line opens", "source": "Gulf News", "link": "https://news.google.com/a1"},
        {"title": "Oil steadies as OPEC meets", "source": "Reuters", "link": "https://news.google.com/a2"},
    ]
    games = hud.scores(["eng.1"], http, now=NOW)
    assert [(g["home"], g["state"]) for g in games] == [("Liverpool", "in"), ("Arsenal", "post"), ("Everton", "pre")]
    assert games[0]["league"] == "Premier League" and games[1]["home_score"] == "2"


def test_one_broken_source_doesnt_break_the_rest(ctx):
    http = FakeHTTP(fail={"api.coingecko.com", "news.google.com"})
    data = hud.data(ctx, http)
    assert [q["symbol"] for q in data["markets"]] == ["GOLD", "SPX"]
    assert data["news"] == [] and data["settings"]["tickers"] == hud.DEFAULTS["tickers"]


def test_results_are_cached(ctx):
    http = FakeHTTP()
    hud.data(ctx, http)
    count = len(http.urls)
    hud.data(ctx, http)
    assert len(http.urls) == count


def test_settings_and_tools(ctx, monkeypatch):
    load_all()
    out = REGISTRY["set_hud"].handler(ctx, {"add_tickers": ["tsla", "$NVDA"], "remove_tickers": ["SPX"],
                                            "leagues": ["esp.1", "uefa.champions"], "news": False})
    assert "Tickers: BTC, ETH, GOLD, TSLA, NVDA" in out and "LaLiga, Champions League" in out and "Headlines: off" in out
    assert hud.settings(ctx)["news"] is False
    with pytest.raises(ToolError, match="Unknown league"):
        REGISTRY["set_hud"].handler(ctx, {"leagues": ["moon.1"]})
    monkeypatch.setattr(hud, "quotes", lambda symbols, http=None: [
        {"symbol": "BTC", "label": "BTC", "price": 63120.5, "currency": "USD", "change": 2.14}])
    out = REGISTRY["market_quote"].handler(ctx, {"symbols": ["btc", "xyz"]})
    assert out == "BTC: $63,120.50 (+2.14% today)\nNo price found for: XYZ"


def test_hud_endpoints(ctx, monkeypatch):
    monkeypatch.setattr(hud, "data", lambda c, http=None: {"markets": [], "news": [], "football": [], "settings": hud.settings(c)})
    app = create_app(ctx, brain_factory=lambda **kw: Brain(ctx, client=FakeClaude(), **kw))
    client = TestClient(app, base_url="http://localhost", client=("127.0.0.1", 5000))
    assert client.get("/api/hud").json()["settings"]["leagues"] == ["eng.1"]
    saved = client.post("/api/hud", json={"tickers": ["sol", "gold", "sol"], "leagues": ["ger.1", "fake"]}).json()
    assert saved == {"tickers": ["SOL", "GOLD"], "leagues": ["ger.1"], "news": True}
    ctx.settings.access_token = "tok"
    assert client.get("/api/hud").status_code == 401
