"""Handy extras that need no API keys: a calculator, currency rates, world
clocks, prayer times, reading a web page, and your calendar."""

from __future__ import annotations

import ast
import html
import math
import operator
import re
import threading
import time
from datetime import datetime
from html.parser import HTMLParser
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from jarvis.tools import Context, ToolError, tool

# ---------------------------------------------------------------- calculator
_BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
           ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCS = {"sqrt": math.sqrt, "abs": abs, "round": round, "floor": math.floor, "ceil": math.ceil,
          "log": math.log, "log10": math.log10, "log2": math.log2, "exp": math.exp, "min": min, "max": max,
          "sin": math.sin, "cos": math.cos, "tan": math.tan, "asin": math.asin, "acos": math.acos,
          "atan": math.atan, "radians": math.radians, "degrees": math.degrees, "factorial": math.factorial}
_NAMES = {"pi": math.pi, "e": math.e, "tau": math.tau}
MAX_BITS = 12_000   # biggest whole number allowed (~3,600 digits): keeps every sum instant


def _fits(value):
    if isinstance(value, int) and value.bit_length() > MAX_BITS:
        raise ToolError("That number is too large to work out.")
    return value


def calc(expression: str) -> float | int:
    """Evaluate plain arithmetic safely (no names, attributes or code)."""
    expr = expression.strip().replace("^", "**").replace("×", "*").replace("÷", "/")
    expr = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", expr)  # thousands separators: 1,250 -> 1250
    expr = re.sub(r"(\d+(?:\.\d+)?)\s*%\s*of\s*", r"\1/100*", expr, flags=re.I)  # "15% of 80"
    if not expr or len(expr) > 300:
        raise ToolError("Give a math expression under 300 characters.")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise ToolError(f"That isn't a math expression I understand: {expression}") from exc

    def ev(node: ast.AST):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
            left, right = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 1 and abs(left) > 1 and (
                    abs(right) > MAX_BITS or math.log2(abs(left)) * abs(right) > MAX_BITS):
                raise ToolError("That number is too large to work out.")
            return _fits(_BINARY[type(node.op)](left, right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
            return _UNARY[type(node.op)](ev(node.operand))
        if isinstance(node, ast.Name) and node.id in _NAMES:
            return _NAMES[node.id]
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS
                and not node.keywords and len(node.args) <= 5):
            args = [ev(a) for a in node.args]
            if node.func.id == "factorial" and (not args or args[0] > 500):
                raise ToolError("That number is too large to work out.")
            return _fits(_FUNCS[node.func.id](*args))
        raise ToolError("Only numbers, + - * / // % ** and math functions like sqrt() are allowed.")

    try:
        result = ev(tree)
    except ZeroDivisionError as exc:
        raise ToolError("That divides by zero.") from exc
    except (ValueError, OverflowError, TypeError) as exc:
        raise ToolError(f"Can't work that out: {exc}") from exc
    if isinstance(result, float) and result.is_integer() and abs(result) < 1e15:
        return int(result)
    return round(result, 10) if isinstance(result, float) else result


@tool(
    "calculate",
    "Exact arithmetic: use it for any sum that matters (bills, splits, tips, percentages, "
    "unit maths) instead of working it out in your head. Supports + - * / // % ** ( ), "
    "'15% of 80', sqrt, log, sin, round, min, max, pi.",
    {"expression": {"type": "string", "description": "e.g. (1250*0.05)+99 or 15% of 80"}},
    ["expression"],
)
def calculate(ctx: Context, args: dict) -> str:
    value = calc(str(args.get("expression", "")))
    return f"{args['expression']} = {format_number(value)}"


def format_number(value: float | int) -> str:
    if isinstance(value, int):
        return f"{value:,}"
    if value != 0 and (abs(value) < 1e-4 or abs(value) >= 1e15):
        return f"{value:.6g}"
    return f"{value:,.6f}".rstrip("0").rstrip(".")


# ---------------------------------------------------------------- currency
_rates: dict[str, tuple[float, dict]] = {}
_rates_lock = threading.Lock()


def exchange_rates(base: str) -> dict:
    base = base.upper()
    with _rates_lock:
        cached = _rates.get(base)
        if cached and time.time() - cached[0] < 3600:
            return cached[1]
    resp = httpx.get(f"https://open.er-api.com/v6/latest/{base}", timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get("result") != "success":
        raise ToolError(f"I don't have exchange rates for {base}.")
    with _rates_lock:
        _rates[base] = (time.time(), data)
    return data


@tool(
    "convert_currency",
    "Convert money between currencies at today's exchange rate (e.g. USD to AED).",
    {
        "amount": {"type": "number"},
        "from_currency": {"type": "string", "description": "3-letter code, e.g. USD"},
        "to_currency": {"type": "string", "description": "3-letter code, e.g. AED"},
    },
    ["amount", "from_currency", "to_currency"],
)
def convert_currency(ctx: Context, args: dict) -> str:
    src, dst = str(args["from_currency"]).strip().upper(), str(args["to_currency"]).strip().upper()
    if not (re.fullmatch(r"[A-Z]{3}", src) and re.fullmatch(r"[A-Z]{3}", dst)):
        raise ToolError("Use 3-letter currency codes like USD, AED, EUR.")
    data = exchange_rates(src)
    rate = data.get("rates", {}).get(dst)
    if rate is None:
        raise ToolError(f"I don't have a rate from {src} to {dst}.")
    amount = float(args["amount"])
    updated = str(data.get("time_last_update_utc", ""))[:16]
    return (f"{amount:,.2f} {src} = {amount * rate:,.2f} {dst} (1 {src} = {rate:.4f} {dst}"
            + (f"; rates from {updated}" if updated else "") + ")")


# ---------------------------------------------------------------- world clock
def zone_for(place: str) -> tuple[ZoneInfo, str]:
    place = place.strip()
    if "/" in place or place.upper() in ("UTC", "GMT"):
        try:
            return ZoneInfo(place), place
        except (ZoneInfoNotFoundError, ValueError):
            pass
    from jarvis.tools.web import geocode

    found = geocode(place)
    if not found.get("timezone"):
        raise ToolError(f"I couldn't work out the time zone for {place}.")
    label = ", ".join(p for p in (found.get("name"), found.get("country")) if p)
    return ZoneInfo(found["timezone"]), label


@tool(
    "world_time",
    "The current local time (and time difference) in any city or time zone.",
    {"place": {"type": "string", "description": "City ('Tokyo', 'London, UK') or zone ('America/New_York')."}},
    ["place"],
)
def world_time(ctx: Context, args: dict) -> str:
    zone, label = zone_for(str(args.get("place", "")))
    there = datetime.now(zone)
    here = datetime.now(ctx.settings.tz)
    diff = (there.utcoffset() - here.utcoffset()).total_seconds() / 3600
    if diff == 0:
        rel = "the same time as you"
    else:
        hours = f"{abs(diff):g} hour{'s' if abs(diff) != 1 else ''}"
        rel = f"{hours} {'ahead of' if diff > 0 else 'behind'} you"
    return f"In {label} it's {there:%H:%M on %A %d %B} ({there.tzname()}), {rel}."


# ---------------------------------------------------------------- prayer times
PRAYERS = ("Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha")


def fetch_prayer_times(city: str, day: datetime) -> dict:
    from jarvis.tools.web import geocode

    place = geocode(city)
    resp = httpx.get(
        f"https://api.aladhan.com/v1/timings/{day:%d-%m-%Y}",
        params={"latitude": place["latitude"], "longitude": place["longitude"],
                **({"timezonestring": place["timezone"]} if place.get("timezone") else {})},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json().get("data") or {}
    timings = data.get("timings") or {}
    if not timings:
        raise ToolError("Prayer times aren't available right now.")
    return {"place": ", ".join(p for p in (place.get("name"), place.get("country")) if p),
            "times": {p: str(timings.get(p, "")).split(" ")[0] for p in PRAYERS},
            "method": ((data.get("meta") or {}).get("method") or {}).get("name", "")}


@tool(
    "prayer_times",
    "Today's (or another day's) Islamic prayer times for a city: Fajr, Sunrise, Dhuhr, Asr, "
    "Maghrib, Isha. Defaults to the user's home city.",
    {
        "city": {"type": "string"},
        "date": {"type": "string", "description": "YYYY-MM-DD; default today."},
    },
)
def prayer_times(ctx: Context, args: dict) -> str:
    city = (args.get("city") or ctx.settings.home_city or "").strip()
    if not city:
        raise ToolError("Which city? (No HOME_CITY is configured.)")
    try:
        day = datetime.fromisoformat(args["date"]) if args.get("date") else datetime.now(ctx.settings.tz)
    except ValueError as exc:
        raise ToolError("date must look like 2026-10-01.") from exc
    info = fetch_prayer_times(city, day)
    times = ", ".join(f"{p} {t}" for p, t in info["times"].items() if t)
    return f"Prayer times in {info['place']} on {day:%A %d %B}: {times}." + (
        f" (Method: {info['method']}.)" if info["method"] else "")


# ---------------------------------------------------------------- read a web page
class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "template", "head", "nav", "footer", "form", "iframe"}
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article",
             "blockquote", "pre", "table", "ul", "ol", "header", "main"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title = ""
        self._skip = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        elif tag == "title":
            self._in_title = False
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip:
            self.parts.append(data)


def html_to_text(page: str) -> tuple[str, str]:
    parser = _TextExtractor()
    parser.feed(page)
    text = "".join(parser.parts)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return html.unescape(parser.title).strip(), text.strip()


MAX_PAGE_CHARS = 20_000


@tool(
    "read_webpage",
    "Open a web page (or online PDF) and read its text, e.g. to summarise an article or check "
    "details on a site the user mentions. Use web_search to find pages; use this to read one.",
    {"url": {"type": "string", "description": "Full http(s) address."}},
    ["url"],
)
def read_webpage(ctx: Context, args: dict) -> str:
    final, title, text = fetch_page(str(args.get("url", "")))
    if len(text) > MAX_PAGE_CHARS:
        text = text[:MAX_PAGE_CHARS] + "\n[… page cut here]"
    return f"{title or final}\n{final}\n\n{text or '(no readable text on that page)'}"


def fetch_page(url: str) -> tuple[str, str, str]:
    """(final address, title, readable text) of a public web page or online PDF."""
    from jarvis import safeurl

    url = url.strip()
    if url and "://" not in url:
        url = "https://" + url
    try:
        final, ctype, body = safeurl.fetch(url)
    except safeurl.UnsafeURL as exc:
        raise ToolError(str(exc)) from exc
    except httpx.HTTPError as exc:
        raise ToolError(f"Couldn't open that page ({type(exc).__name__}).") from exc
    ctype = ctype.split(";")[0].strip().lower()
    if ctype == "application/pdf" or final.lower().endswith(".pdf"):
        from jarvis import files

        try:
            text, pages = files.pdf_text(body)
        except files.FileError as exc:
            raise ToolError(str(exc)) from exc
        return final, f"PDF, {pages} pages", text
    if ctype.startswith("text/html") or ctype in ("application/xhtml+xml", ""):
        title, text = html_to_text(body.decode("utf-8", "replace"))
        return final, title, text
    if ctype.startswith("text/") or ctype in ("application/json", "application/xml"):
        return final, "", body.decode("utf-8", "replace")
    raise ToolError(f"That link is a {ctype} file, which I can't read as text.")


# ---------------------------------------------------------------- calendar
@tool(
    "get_calendar",
    "Events from the user's calendar for today and the coming days (meetings, appointments, "
    "birthdays). Read-only.",
    {"days": {"type": "integer", "description": "How many days ahead, including today (1-31). Default 1."}},
)
def get_calendar(ctx: Context, args: dict) -> str:
    from jarvis import agenda

    if not ctx.settings.calendar_urls:
        raise ToolError("No calendar is connected. The user can add their calendar's private iCal link "
                        "as CALENDAR_ICS_URL in the server settings.")
    days = min(max(int(args.get("days") or 1), 1), 31)
    events = agenda.upcoming(ctx, days)
    if not events:
        return f"Nothing on the calendar for the next {days} day{'s' if days != 1 else ''}."
    return "\n".join(agenda.describe(e) for e in events)


# ---------------------------------------------------------------- markets + HUD
@tool(
    "market_quote",
    "Live price of crypto (BTC, ETH, SOL…), stocks (TSLA, AAPL, NVDA…), indices (SPX, NASDAQ, DOW), "
    "gold, silver or oil. Prices marked $ are US dollars (convert with convert_currency if asked); "
    "indices are in points and currency pairs are exchange rates.",
    {"symbols": {"type": "array", "items": {"type": "string"}, "description": "e.g. [\"BTC\", \"TSLA\", \"GOLD\"]"}},
    ["symbols"],
)
def market_quote(ctx: Context, args: dict) -> str:
    from jarvis import hud

    symbols = [str(s).strip().upper().lstrip("^$") for s in (args.get("symbols") or []) if str(s).strip()][:10]
    if not symbols:
        raise ToolError("Which symbols?")
    found = hud.quotes(symbols)
    if not found:
        raise ToolError("I couldn't get those prices right now.")
    missing = [s for s in symbols if s not in {q["symbol"] for q in found}]
    lines = [f"{q['label']}: {q.get('unit', '$')}{q['price']:,.{2 if q['price'] >= 1 else 4}f} ({q['change']:+.2f}% today)"
             for q in found]
    return "\n".join(lines) + (f"\nNo price found for: {', '.join(missing)}" if missing else "")


@tool(
    "set_hud",
    "Change the live ticker strip on the dashboard: which prices it shows (crypto, stocks, GOLD, SPX, "
    "OIL…), which football leagues (eng.1 Premier League, esp.1 LaLiga, ita.1, ger.1, fra.1, "
    "uefa.champions, ksa.1 Saudi Pro League), and whether headlines show.",
    {
        "add_tickers": {"type": "array", "items": {"type": "string"}},
        "remove_tickers": {"type": "array", "items": {"type": "string"}},
        "leagues": {"type": "array", "items": {"type": "string"}, "description": "Replaces the list; [] for none."},
        "news": {"type": "boolean"},
    },
)
def set_hud(ctx: Context, args: dict) -> str:
    from jarvis import hud

    current = hud.settings(ctx)
    drop = {str(t).upper().lstrip("^$") for t in args.get("remove_tickers") or []}
    tickers = [t for t in current["tickers"] if t not in drop] + [str(t) for t in args.get("add_tickers") or []]
    values: dict = {"tickers": tickers}
    if args.get("leagues") is not None:
        unknown = [l for l in args["leagues"] if l not in hud.LEAGUES]
        if unknown:
            raise ToolError(f"Unknown league codes: {', '.join(unknown)}. Use: {', '.join(hud.LEAGUES)}.")
        values["leagues"] = args["leagues"]
    if args.get("news") is not None:
        values["news"] = args["news"]
    saved = hud.save_settings(ctx, values)
    leagues = ", ".join(hud.LEAGUES[l] for l in saved["leagues"]) or "none"
    return (f"HUD updated. Tickers: {', '.join(saved['tickers']) or 'none'}. Football: {leagues}. "
            f"Headlines: {'on' if saved['news'] else 'off'}.")
