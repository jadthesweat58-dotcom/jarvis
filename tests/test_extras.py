import socket

import httpx
import pytest

from jarvis import safeurl
from jarvis.tools import REGISTRY, ToolError, load_all
from jarvis.tools import extras
from jarvis.tools.extras import calc, format_number, html_to_text


def run(ctx, tool_name, **args):
    load_all()
    return REGISTRY[tool_name].handler(ctx, args)


class Resp:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


# ---------------------------------------------------------------- calculator
@pytest.mark.parametrize("expr, expected", [
    ("2+2", 4), ("15% of 80", 12), ("1,250 * 0.05", 62.5), ("max(3, 4)", 4), ("sqrt(16)", 4),
    ("2^10", 1024), ("(100 - 20) / 3", 80 / 3), ("-5 // 2", -3), ("round(2.567, 2)", 2.57),
])
def test_calculator(expr, expected):
    assert calc(expr) == pytest.approx(expected)


@pytest.mark.parametrize("expr", ["__import__('os')", "(1).real", "open('x')", "9**9**9", "a + 1",
                                  "(((10**1000)**50)**50)**50", "((10**3000)*(10**3000))*(10**3000)*(10**9000)",
                                  "[1, 2]", "lambda: 1", "factorial(100000)", "1/0", "x" * 400])
def test_calculator_refuses_anything_but_maths(expr):
    with pytest.raises(ToolError):
        calc(expr)


def test_calculate_tool_formats(ctx):
    assert run(ctx, "calculate", expression="1200*1.05") == "1200*1.05 = 1,260"
    assert format_number(10 / 3) == "3.333333"


# ---------------------------------------------------------------- currency, clocks, prayer times
def test_convert_currency(ctx, monkeypatch):
    extras._rates.clear()
    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        return Resp({"result": "success", "rates": {"AED": 3.6725, "USD": 1}, "time_last_update_utc": "Mon, 28 Sep 2026"})

    monkeypatch.setattr(extras.httpx, "get", fake_get)
    out = run(ctx, "convert_currency", amount=100, from_currency="usd", to_currency="AED")
    assert out.startswith("100.00 USD = 367.25 AED")
    run(ctx, "convert_currency", amount=5, from_currency="USD", to_currency="AED")
    assert len(calls) == 1  # cached for an hour
    with pytest.raises(ToolError):
        run(ctx, "convert_currency", amount=5, from_currency="USD", to_currency="XYZ")
    with pytest.raises(ToolError):
        run(ctx, "convert_currency", amount=5, from_currency="dollars", to_currency="AED")


def test_world_time(ctx, monkeypatch):
    ctx.settings.timezone = "Asia/Dubai"
    assert "Asia/Tokyo" in run(ctx, "world_time", place="Asia/Tokyo")
    assert "5 hours ahead of you" in run(ctx, "world_time", place="Asia/Tokyo")
    monkeypatch.setattr("jarvis.tools.web.geocode",
                        lambda place: {"name": "London", "country": "United Kingdom", "timezone": "Europe/London"})
    out = run(ctx, "world_time", place="London")
    assert out.startswith("In London, United Kingdom it's") and "behind you" in out


def test_prayer_times(ctx, monkeypatch):
    ctx.settings.home_city = "Dubai"
    monkeypatch.setattr("jarvis.tools.web.geocode", lambda place: {
        "name": "Dubai", "country": "United Arab Emirates", "latitude": 25.2, "longitude": 55.3,
        "timezone": "Asia/Dubai"})
    seen = {}

    def fake_get(url, params, timeout):
        seen.update(url=url, params=params)
        return Resp({"data": {"timings": {"Fajr": "04:41", "Sunrise": "05:56", "Dhuhr": "12:03", "Asr": "15:27",
                                          "Maghrib": "18:05", "Isha": "19:19 (+04)"},
                              "meta": {"method": {"name": "Gulf Region"}}}})

    monkeypatch.setattr(extras.httpx, "get", fake_get)
    out = run(ctx, "prayer_times", date="2026-10-01")
    assert "Dubai" in out and "Fajr 04:41" in out and "Isha 19:19," not in out and "Isha 19:19." in out
    assert seen["url"].endswith("/01-10-2026") and seen["params"]["timezonestring"] == "Asia/Dubai"


# ---------------------------------------------------------------- safe web fetching
@pytest.fixture
def dns(monkeypatch):
    table = {"localhost": "127.0.0.1", "example.com": "93.184.216.34", "internal.example": "10.0.0.5", "meta.example": "169.254.169.254"}

    def fake_getaddrinfo(host, port, *a, **kw):
        ip = table.get(host, host)
        family = socket.AF_INET6 if ":" in ip else socket.AF_INET
        return [(family, socket.SOCK_STREAM, 6, "", (ip, port))]

    monkeypatch.setattr(safeurl.socket, "getaddrinfo", fake_getaddrinfo)
    return table


@pytest.mark.parametrize("url", [
    "http://localhost/admin", "http://127.0.0.1:8000/api/status", "http://10.1.2.3/", "http://[::1]/",
    "http://169.254.169.254/latest/meta-data", "http://internal.example/", "http://meta.example/",
    "file:///etc/passwd", "ftp://example.com/x", "http://user:pw@example.com/", "http://192.168.1.1/",
])
def test_private_addresses_are_blocked(dns, url):
    with pytest.raises(safeurl.UnsafeURL):
        safeurl.check_url(url)


def test_public_address_allowed(dns):
    assert safeurl.check_url("https://example.com/page") == "https://example.com/page"


def test_redirect_to_private_address_is_blocked(dns):
    def handler(request):
        if request.headers["host"] == "example.com":
            return httpx.Response(302, headers={"location": "http://internal.example/secret"})
        return httpx.Response(200, text="secret stuff")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(safeurl.UnsafeURL):
        safeurl.fetch("https://example.com/", client=client)


def test_fetch_follows_safe_redirects_and_caps_size(dns):
    def handler(request):
        if request.url.path == "/old":
            return httpx.Response(301, headers={"location": "/new"})
        return httpx.Response(200, content=b"x" * 5000, headers={"content-type": "text/plain"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    final, ctype, body = safeurl.fetch("https://example.com/old", client=client, max_bytes=1000)
    assert final == "https://example.com/new" and ctype == "text/plain" and len(body) == 1000


def test_fetch_connects_to_the_checked_ip(dns):
    """DNS rebinding: the request goes to the IP that passed the check, not a fresh lookup."""
    seen = []

    def handler(request):
        seen.append((str(request.url), request.headers["host"], request.extensions.get("sni_hostname")))
        return httpx.Response(200, text="ok")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    safeurl.fetch("https://example.com:8443/a?b=1", client=client)
    assert seen == [("https://93.184.216.34:8443/a?b=1", "example.com:8443", "example.com")]


def test_read_webpage(ctx, monkeypatch):
    page = b"<html><head><title>News &amp; Views</title><script>var x</script></head><body><nav>Menu</nav>" \
           b"<h1>Big story</h1><p>First paragraph.</p></body></html>"
    monkeypatch.setattr(safeurl, "fetch", lambda url: (url, "text/html; charset=utf-8", page))
    out = run(ctx, "read_webpage", url="example.com/story")
    assert out.startswith("News & Views\nhttps://example.com/story")
    assert "Big story" in out and "First paragraph." in out and "var x" not in out and "Menu" not in out

    def blocked(url):
        raise safeurl.UnsafeURL("That address points to a private network, which Jarvis won't open.")

    monkeypatch.setattr(safeurl, "fetch", blocked)
    with pytest.raises(ToolError, match="private network"):
        run(ctx, "read_webpage", url="http://10.0.0.1")


def test_html_to_text():
    title, body = html_to_text("<title>T</title><div>a<br>b</div><style>p{}</style><p>c &lt; d</p>")
    assert title == "T" and body == "a\nb\n\nc < d"


def test_calendar_tool_without_calendar(ctx):
    with pytest.raises(ToolError, match="CALENDAR_ICS_URL"):
        run(ctx, "get_calendar")
