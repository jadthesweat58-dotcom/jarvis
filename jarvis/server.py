"""Jarvis web server: the browser app, its API, and Twilio phone-call webhooks.

Run it with:  uvicorn jarvis.server:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import hmac
import threading
import time
from collections import deque
import json
import logging
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import Gather, VoiceResponse

from jarvis import agenda, automations, briefing, hud, images, library, push, usage
from jarvis.app import build_context
from jarvis.brain import Brain, create_brain, resolve_action
from jarvis.db import utcnow
from jarvis.files import FileError
from jarvis.phone import say
from jarvis.scheduler import ReminderLoop
from jarvis.telegram import TelegramBot
from jarvis.tools import Context, ToolError, available_tools
from jarvis.tools.reminders import describe_repeat
from jarvis.tools.web import fetch_weather
from jarvis.voice import ElevenLabsVoice, VoiceError

log = logging.getLogger("jarvis.server")
STATIC = Path(__file__).parent / "static"
LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}
HANGUP = "[HANGUP]"


class FileIn(BaseModel):
    name: str
    data: str  # the file as a data: URL


class ChatIn(BaseModel):
    text: str = ""
    image: str | None = None  # optional screenshot as a data: URL (screen sharing)
    file: FileIn | None = None  # optional attached file (PDF, picture, document…)


MAX_IMAGE_BYTES = 5 * 1024 * 1024
IMAGE_URL = re.compile(r"^data:(image/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=\s]+)$")


def decode_image(data_url: str) -> tuple[bytes, str]:
    import base64
    import binascii

    match = IMAGE_URL.match(data_url or "")
    if not match:
        raise HTTPException(400, "The screenshot must be a JPEG, PNG or WebP image.")
    try:
        data = base64.b64decode(match.group(2), validate=False)
    except binascii.Error as exc:
        raise HTTPException(400, "The screenshot couldn't be read.") from exc
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "The screenshot is too large (5 MB max).")
    return data, match.group(1)


MAX_FILE_BYTES = 10 * 1024 * 1024
DATA_URL = re.compile(r"^data:([\w.+-]+/[\w.+-]+)?(?:;[\w.+-]+=[^;,]*)*;base64,([A-Za-z0-9+/=\s]*)$")


def decode_file(data_url: str) -> tuple[bytes, str]:
    import base64
    import binascii

    match = DATA_URL.match(data_url or "")
    if not match:
        raise HTTPException(400, "The file couldn't be read.")
    if len(match.group(2)) > MAX_FILE_BYTES * 4 // 3 + 16:
        raise HTTPException(413, "That file is too large (10 MB max).")
    try:
        data = base64.b64decode(match.group(2), validate=False)
    except binascii.Error as exc:
        raise HTTPException(400, "The file couldn't be read.") from exc
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(413, "That file is too large (10 MB max).")
    return data, match.group(1) or ""


class HudIn(BaseModel):
    tickers: list[str] | None = None
    leagues: list[str] | None = None
    news: bool | None = None


class AutomationIn(BaseModel):
    action: str  # run | pause | resume | delete


class PushSubIn(BaseModel):
    endpoint: str
    keys: dict[str, str] = {}


class EndpointIn(BaseModel):
    endpoint: str


class ActionIn(BaseModel):
    approve: bool


class TaskIn(BaseModel):
    task: str
    priority: str = "med"


class DoneIn(BaseModel):
    done: bool


class SpeakIn(BaseModel):
    text: str


def contact_call_prompt(ctx: Context, call: dict) -> str:
    owner = ctx.settings.my_name
    who = call["contact_name"] or "the caller"
    if call["direction"] == "inbound":
        task = (f"{owner} isn't available. Take a message: who is calling, what it's about, and a "
                "callback number if they want one.")
    else:
        task = (f"You placed this call and have already introduced yourself and delivered this "
                f"message: \"{call['purpose']}\". Answer questions about it briefly and, if they "
                f"want to reply, take their message for {owner} accurately.")
    return f"""You are JARVIS, the AI assistant of {owner}, speaking on a phone call with {who}.
{task}
Don't share any other private information about {owner} and don't make commitments on their
behalf. Be polite and natural. Keep every reply to one or two short spoken sentences with no
formatting. When the conversation is over, say a brief goodbye and end your reply with {HANGUP}."""


def create_app(ctx: Context | None = None, brain_factory: Callable[..., Brain] | None = None,
               voice: ElevenLabsVoice | None = None) -> FastAPI:
    ctx = ctx or build_context()
    voice = voice or ElevenLabsVoice(ctx.settings, on_usage=lambda n: usage.record(ctx, {"tts_chars": n}))
    make_brain = brain_factory or (lambda **kw: create_brain(ctx, **kw))
    main_brain = make_brain(conversation_id="main")
    telegram = TelegramBot(ctx, make_brain)
    ctx.notifier.subscribe(lambda e: push.forward(ctx, e))  # phone notifications
    ctx.notifier.subscribe(telegram.forward)
    call_brains: dict[int, Brain] = {}
    feed: deque[dict] = deque(maxlen=30)  # recent notifications, for the live feed
    ctx.notifier.subscribe(feed.appendleft)
    weather_cache: dict[str, Any] = {}
    started_at = utcnow()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        busy: dict[str, threading.Lock] = {k: threading.Lock() for k in ("briefing", "routines", "watchers")}

        def once(name: str, job: Callable[[], Any]) -> None:
            """Run a scheduled job in the background, never two copies at the same time."""
            if not busy[name].acquire(blocking=False):
                return

            def run() -> None:
                try:
                    job()
                except Exception:
                    log.exception("Scheduled %s failed", name)
                finally:
                    busy[name].release()

            threading.Thread(target=run, name=name, daemon=True).start()

        def every_minute() -> None:
            # These take a few seconds each (AI, web pages): don't hold up reminders.
            once("briefing", lambda: briefing.send_if_due(ctx, make_brain))
            once("routines", lambda: automations.run_due_routines(ctx, make_brain))
            once("watchers", lambda: automations.run_due_watchers(ctx, make_brain))

        loop = ReminderLoop(ctx, on_tick=every_minute)
        loop.start()
        threading.Thread(target=telegram.start, name="telegram-setup", daemon=True).start()
        if not ctx.settings.access_token:
            log.warning("JARVIS_ACCESS_TOKEN is not set: only this computer (localhost) can use Jarvis.")
        yield
        loop.stop()
        telegram.stop()

    app = FastAPI(title="Jarvis", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    # --- security ----------------------------------------------------------------
    def host_name(value: str) -> str:
        """'localhost:8000' -> 'localhost', '[::1]:8000' -> '::1'."""
        value = value.strip().lower()
        if value.startswith("["):
            return value[1:value.find("]")] if "]" in value else value
        return value.rsplit(":", 1)[0] if value.count(":") == 1 else value

    def require_user(request: Request) -> None:
        # Block cross-site requests: a page on another site must never drive Jarvis.
        origin = request.headers.get("origin")
        if origin and origin != "null":
            if host_name(origin.split("://", 1)[-1]) != host_name(request.headers.get("host", "")):
                raise HTTPException(403, "Cross-site requests are not allowed.")
        token = ctx.settings.access_token
        supplied = ""
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            supplied = auth[7:].strip()
        elif request.url.path == "/api/events":  # EventSource can't send headers
            supplied = request.query_params.get("token", "")
        if token:
            if supplied and hmac.compare_digest(supplied, token):
                return
            raise HTTPException(401, "Wrong or missing access token.")
        # No token set: only this computer may use Jarvis. Checking the Host header
        # too stops "DNS rebinding" tricks where a website pretends to be localhost.
        peer = request.client.host if request.client else ""
        if peer not in LOCAL_HOSTS or host_name(request.headers.get("host", "")) not in LOCAL_HOSTS:
            raise HTTPException(401, "Set JARVIS_ACCESS_TOKEN to use Jarvis from other devices.")

    def external_base(request: Request) -> str:
        """The https address Twilio uses to reach us."""
        if ctx.settings.public_base_url:
            return ctx.settings.public_base_url
        scheme = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
        return f"{scheme}://{request.headers.get('host', request.url.netloc)}"

    async def twilio_form(request: Request) -> dict[str, str]:
        # Phone webhooks only exist when Twilio is set up, and every request must
        # carry a valid Twilio signature (made with your secret auth token).
        if not (ctx.settings.twilio_enabled and ctx.settings.twilio_auth_token):
            raise HTTPException(404, "Phone features aren't set up.")
        form = {k: str(v) for k, v in (await request.form()).items()}
        suffix = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        candidates = {external_base(request), str(request.base_url).rstrip("/")}
        candidates |= {c.replace("http://", "https://", 1) for c in candidates}
        signature = request.headers.get("x-twilio-signature", "")
        validator = RequestValidator(ctx.settings.twilio_auth_token)
        if not any(validator.validate(base + suffix, form, signature) for base in candidates):
            raise HTTPException(403, "Invalid Twilio signature.")
        return form

    def run_chat(brain: Brain, text: str, image: tuple[bytes, str] | None = None,
                 attachment: tuple[str, bytes, str] | None = None) -> dict[str, Any]:
        extra: dict[str, Any] = {}
        if image:
            extra["image"] = image
        if attachment:
            extra["attachment"] = attachment
        before = images.latest_id(ctx)
        try:
            reply = brain.chat(text, **extra)
        except HTTPException:
            raise
        except FileError as exc:  # e.g. a file type Jarvis can't read
            raise HTTPException(400, str(exc)) from exc
        except Exception as exc:
            log.exception("Chat failed")
            raise HTTPException(500, f"Jarvis hit a problem: {exc}") from exc
        return {"reply": reply.text, "actions": reply.actions, "images": images.made_since(ctx, before)}

    # --- browser app -------------------------------------------------------------
    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html")

    # Served from the site root so it can show notifications for the whole app.
    @app.get("/sw.js")
    def service_worker() -> FileResponse:
        return FileResponse(STATIC / "sw.js", media_type="text/javascript",
                            headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})

    @app.get("/manifest.webmanifest")
    def manifest() -> FileResponse:
        return FileResponse(STATIC / "manifest.webmanifest", media_type="application/manifest+json")

    @app.get("/api/status", dependencies=[Depends(require_user)])
    def status() -> dict[str, Any]:
        s = ctx.settings
        return {"name": s.my_name, "mode": s.mode, "model": s.model,
                "phone": s.twilio_enabled, "computer_control": s.is_local,
                "two_way_calls": s.twilio_enabled and bool(s.public_base_url),
                "ai_name": s.provider_name, "ai_ready": bool(s.ai_key), "web_search": bool(s.ai_key),
                "home_city": s.home_city, "timezone": s.timezone, "started_at": started_at,
                "tts": "elevenlabs" if voice.enabled else "browser", "calendar": bool(s.calendar_urls),
                "telegram": {"enabled": s.telegram_enabled, "linked": telegram.owner_chat is not None},
                "pictures": bool(s.gemini_api_key)}

    @app.post("/api/chat", dependencies=[Depends(require_user)])
    def chat(body: ChatIn) -> dict[str, Any]:
        text = body.text.strip()
        if not text and not body.file:
            raise HTTPException(400, "Say something first.")
        image = decode_image(body.image) if body.image else None
        attachment = None
        if body.file:
            data, mime = decode_file(body.file.data)
            attachment = (body.file.name, data, mime)
            text = text or "Please read this and give me a short summary of what matters."
        return run_chat(main_brain, text, image, attachment)

    @app.post("/api/reset", dependencies=[Depends(require_user)])
    def reset() -> dict[str, bool]:
        main_brain.reset()
        return {"ok": True}

    @app.post("/api/actions/{action_id}", dependencies=[Depends(require_user)])
    def action(action_id: int, body: ActionIn) -> dict[str, Any]:
        try:
            row, result = resolve_action(ctx, action_id, body.approve)
        except ToolError as exc:
            raise HTTPException(409, str(exc)) from exc
        verdict = "approved" if body.approve else "denied"
        note = f"(I {verdict} action #{action_id}: {row['summary']}. Result: {result})"
        return {**run_chat(main_brain, note), "result": result}

    @app.get("/api/dashboard", dependencies=[Depends(require_user)])
    def dashboard() -> dict[str, Any]:
        tz = ctx.settings.tz
        local = lambda iso: datetime.fromisoformat(iso).astimezone(tz)  # noqa: E731
        reminders = ctx.db.query(
            "SELECT id, message, due_at FROM reminders WHERE status = 'pending' ORDER BY due_at LIMIT 10")
        for r in reminders:
            r["due_local"] = local(r["due_at"]).strftime("%a %H:%M")
        # Today's reminders, done and upcoming, for the mission timeline.
        midnight = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
        timeline = ctx.db.query(
            "SELECT id, message, due_at, status FROM reminders WHERE due_at >= ? AND status <> 'cancelled' "
            "ORDER BY due_at LIMIT 12", (midnight.astimezone(timezone.utc).isoformat(timespec="seconds"),))
        for r in timeline:
            r["time_local"] = local(r["due_at"]).strftime("%H:%M")
            r["kind"] = "reminder"
        timeline = sorted(timeline + calendar_today(), key=lambda r: r["due_at"])[:14]
        # One round trip for every count (matters when the database is online).
        counts = ctx.db.one(
            "SELECT (SELECT COUNT(*) FROM facts) AS facts, (SELECT COUNT(*) FROM notes) AS notes, "
            "(SELECT COUNT(*) FROM todos WHERE done = 0) AS todos, "
            "(SELECT COUNT(*) FROM todos WHERE done = 1) AS todos_done, "
            "(SELECT COUNT(*) FROM reminders WHERE status = 'pending') AS reminders, "
            "(SELECT COUNT(*) FROM contacts) AS contacts, (SELECT COUNT(*) FROM phone_calls) AS calls, "
            "(SELECT COUNT(*) FROM documents) AS library, "
            "(SELECT COUNT(*) FROM routines WHERE enabled = 1) + (SELECT COUNT(*) FROM watchers WHERE status = 'active') AS automations")
        counts = {k: int(v or 0) for k, v in counts.items()}
        turns, tool_calls = conversation_stats(main_brain.messages)
        counts.update(turns=turns, tool_calls=tool_calls, tools=len(main_brain.tools) + (
            0 if any(t.name == "web_search" for t in main_brain.tools) else 1))
        return {
            "reminders": reminders,
            "timeline": timeline,
            "todos": [t for t in tasks() if not t["done"]][:10],
            "tasks": tasks(),
            "actions": ctx.db.query(
                "SELECT id, summary FROM pending_actions WHERE status = 'pending' ORDER BY id"),
            "facts": counts["facts"],
            "counts": counts,
            "system": system_stats(),
            "feed": list(feed),
        }

    def calendar_today() -> list[dict[str, Any]]:
        """Today's calendar events, shaped like timeline reminders."""
        if not ctx.settings.calendar_urls:
            return []
        try:
            events = agenda.today(ctx)
        except Exception:
            log.warning("Calendar unavailable", exc_info=True)
            return []
        now = datetime.now(timezone.utc)
        items = []
        for i, e in enumerate(events):
            start = datetime.fromisoformat(e["start"])
            finished = datetime.fromisoformat(e["end"]) <= now
            items.append({"id": f"event-{i}", "kind": "event", "message": e["title"],
                          "location": e["location"], "all_day": e["all_day"],
                          "due_at": start.astimezone(timezone.utc).isoformat(timespec="seconds"),
                          "time_local": "All day" if e["all_day"] else start.strftime("%H:%M"),
                          "status": "fired" if finished else "pending"})
        return items

    def tasks() -> list[dict[str, Any]]:
        return ctx.db.query(
            "SELECT id, task, due, priority, done FROM todos ORDER BY done, "
            "CASE priority WHEN 'high' THEN 0 WHEN 'med' THEN 1 ELSE 2 END, id DESC LIMIT 30")

    def conversation_stats(messages: list[dict]) -> tuple[int, int]:
        """(user turns, tool calls) in a Claude- or Gemini-format history."""
        turns = tool_calls = 0
        for m in messages:
            blocks = m.get("content") if isinstance(m.get("content"), list) else m.get("parts") or []
            if m.get("role") == "user" and any(b.get("type") == "text" or "text" in b for b in blocks):
                turns += 1
            tool_calls += sum(1 for b in blocks if b.get("type") in ("tool_use", "server_tool_use")
                              or "function_call" in b)
        return turns, tool_calls

    def system_stats() -> dict[str, float]:
        try:
            import psutil

            return {
                "cpu": psutil.cpu_percent(interval=None),
                "ram": psutil.virtual_memory().percent,
                "disk": psutil.disk_usage(str(ctx.settings.data_dir.resolve().anchor or "/")).percent,
            }
        except Exception:
            return {}

    @app.get("/api/system", dependencies=[Depends(require_user)])
    def system() -> dict[str, float]:
        return system_stats()

    # --- HUD ----------------------------------------------------------------------------
    @app.get("/api/hud", dependencies=[Depends(require_user)])
    def get_hud() -> dict[str, Any]:
        return hud.data(ctx)

    @app.post("/api/hud", dependencies=[Depends(require_user)])
    def set_hud(body: HudIn) -> dict[str, Any]:
        values = {k: v for k, v in body.model_dump().items() if v is not None}
        return hud.save_settings(ctx, values)

    # --- pictures -----------------------------------------------------------------------
    @app.get("/api/images/{image_id}", dependencies=[Depends(require_user)])
    def get_image(image_id: int) -> Response:
        found = images.get(ctx, image_id)
        if not found:
            raise HTTPException(404, "No such picture (only the newest 40 are kept).")
        return Response(found[0], media_type=found[1], headers={"Cache-Control": "private, max-age=86400"})

    # --- library + automations ----------------------------------------------------------
    @app.post("/api/library/{doc_id}/delete", dependencies=[Depends(require_user)])
    def delete_document(doc_id: int) -> dict[str, bool]:
        if not library.forget(ctx, doc_id):
            raise HTTPException(404, "No such document.")
        return {"ok": True}

    @app.get("/api/automations", dependencies=[Depends(require_user)])
    def list_automations() -> dict[str, Any]:
        local = lambda iso: datetime.fromisoformat(iso).astimezone(ctx.settings.tz).strftime("%a %d %b %H:%M") if iso else ""  # noqa: E731
        routines = ctx.db.query("SELECT id, title, prompt, rule, next_run, last_run, last_result, enabled FROM routines ORDER BY id")
        for r in routines:
            r["schedule"] = describe_repeat(r["rule"]) + f" at {r['rule'].partition('@')[2]}" if "@" in r["rule"] else describe_repeat(r["rule"])
            r["next_local"], r["last_local"] = local(r["next_run"]), local(r["last_run"])
        watchers = ctx.db.query("SELECT id, url, condition, every_hours, status, last_note, last_checked, next_check "
                                "FROM watchers ORDER BY id")
        for w in watchers:
            w["last_local"] = local(w["last_checked"])
        return {"routines": routines, "watchers": watchers}

    @app.post("/api/automations/{kind}/{item_id}", dependencies=[Depends(require_user)])
    def change_automation(kind: str, item_id: int, body: AutomationIn) -> dict[str, bool]:
        from jarvis.tools.automations import queue_now

        table = {"routine": "routines", "watcher": "watchers"}.get(kind)
        if not table:
            raise HTTPException(404, "Unknown automation.")
        if body.action == "run":
            changed = queue_now(ctx, kind, item_id)
        elif body.action == "delete":
            changed = ctx.db.execute(f"DELETE FROM {table} WHERE id = ?", (item_id,))
        elif body.action in ("pause", "resume") and kind == "routine":
            changed = ctx.db.execute("UPDATE routines SET enabled = ? WHERE id = ?", (int(body.action == "resume"), item_id))
        elif body.action in ("pause", "resume"):
            changed = ctx.db.execute("UPDATE watchers SET status = ?, fails = 0 WHERE id = ?",
                                     ("active" if body.action == "resume" else "paused", item_id))
        else:
            raise HTTPException(400, "Unknown action.")
        if not changed:
            raise HTTPException(404, f"No such {kind}.")
        return {"ok": True}

    @app.get("/api/usage", dependencies=[Depends(require_user)])
    def get_usage() -> dict[str, Any]:
        return usage.summary(ctx)

    @app.get("/api/export", dependencies=[Depends(require_user)])
    def export() -> Response:
        """Everything Jarvis remembers about you, as a JSON file (no keys or secrets)."""
        data = {"exported_at": utcnow(), "name": ctx.settings.my_name}
        for table in ("facts", "notes", "todos", "reminders", "contacts", "phone_calls", "routines"):
            data[table] = ctx.db.query(f"SELECT * FROM {table} ORDER BY id")
        data["watchers"] = ctx.db.query(
            "SELECT id, url, condition, every_hours, status, last_note, created_at FROM watchers ORDER BY id")
        data["library"] = library.documents(ctx)
        stamp = datetime.now(ctx.settings.tz).strftime("%Y-%m-%d")
        return Response(json.dumps(data, indent=2, default=str), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="jarvis-memory-{stamp}.json"',
                                 "Cache-Control": "no-store"})

    # --- phone notifications (Web Push) ---------------------------------------------
    @app.get("/api/push/key", dependencies=[Depends(require_user)])
    def push_key() -> dict[str, Any]:
        return {"key": push.public_key(ctx), "subscribers": push.count(ctx)}

    @app.post("/api/push/subscribe", dependencies=[Depends(require_user)])
    def push_subscribe(body: PushSubIn) -> dict[str, bool]:
        try:
            push.save_subscription(ctx, body.model_dump())
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"ok": True}

    @app.post("/api/push/unsubscribe", dependencies=[Depends(require_user)])
    def push_unsubscribe(body: EndpointIn) -> dict[str, bool]:
        return {"ok": push.remove_subscription(ctx, body.endpoint)}

    @app.post("/api/push/test", dependencies=[Depends(require_user)])
    def push_test() -> dict[str, int]:
        sent = push.send_all(ctx, "Jarvis", f"Notifications are working, {ctx.settings.my_name}.", tag="test")
        if not sent:
            raise HTTPException(409, "No device accepted the test notification. Turn notifications on first.")
        return {"sent": sent}

    # --- Telegram --------------------------------------------------------------------------
    @app.post("/api/telegram/link", dependencies=[Depends(require_user)])
    def telegram_link() -> dict[str, Any]:
        if not telegram.enabled:
            raise HTTPException(404, "Add TELEGRAM_BOT_TOKEN to the server settings first.")
        code = telegram.new_link_code()
        try:
            bot = telegram.username()
        except Exception as exc:
            raise HTTPException(502, f"Telegram didn't accept the bot token: {exc}") from exc
        return {"code": code, "bot": bot, "link": f"https://t.me/{bot}?start={code}"}

    @app.post("/api/telegram/unlink", dependencies=[Depends(require_user)])
    def telegram_unlink() -> dict[str, bool]:
        telegram.unlink()
        return {"ok": True}

    @app.post("/telegram/webhook")
    async def telegram_webhook(request: Request) -> Response:
        # Only Telegram knows the secret (it was given it when the webhook was set).
        if not telegram.enabled or not telegram.check_secret(
                request.headers.get("x-telegram-bot-api-secret-token", "")):
            raise HTTPException(404, "Not found.")
        try:
            update = await request.json()
        except ValueError:
            return Response(status_code=200)
        if isinstance(update, dict):
            telegram.handle_async(update)
        return Response(status_code=200)

    @app.post("/api/briefing", dependencies=[Depends(require_user)])
    def get_briefing() -> dict[str, str]:
        try:
            return {"text": briefing.compose(ctx, make_brain)}
        except Exception as exc:
            log.exception("Briefing failed")
            raise HTTPException(500, f"Couldn't put the briefing together: {exc}") from exc

    @app.post("/api/tts", dependencies=[Depends(require_user)])
    def tts(body: SpeakIn) -> Response:
        if not voice.enabled:
            raise HTTPException(404, "ElevenLabs isn't set up.")
        try:
            audio = voice.speak(body.text)
        except VoiceError as exc:
            raise HTTPException(502, str(exc)) from exc
        except Exception as exc:
            log.exception("ElevenLabs request failed")
            raise HTTPException(502, "Couldn't reach ElevenLabs.") from exc
        return Response(audio, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})

    @app.post("/api/todos", dependencies=[Depends(require_user)])
    def add_task(body: TaskIn) -> dict[str, Any]:
        from jarvis.tools.notes import add_todo

        try:
            return {"ok": True, "result": add_todo(ctx, {"task": body.task, "priority": body.priority})}
        except ToolError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/todos/{todo_id}", dependencies=[Depends(require_user)])
    def set_task_done(todo_id: int, body: DoneIn) -> dict[str, bool]:
        if not ctx.db.execute("UPDATE todos SET done = ? WHERE id = ?", (int(body.done), todo_id)):
            raise HTTPException(404, "No such task.")
        return {"ok": True}

    @app.get("/api/list/{kind}", dependencies=[Depends(require_user)])
    def list_items(kind: str) -> list[dict[str, Any]]:
        queries = {
            "facts": "SELECT id, fact AS title, category AS detail FROM facts ORDER BY id DESC",
            "notes": "SELECT id, title, body AS detail FROM notes ORDER BY id DESC LIMIT 100",
            "todos": "SELECT id, task AS title, COALESCE(due, '') AS detail, done FROM todos ORDER BY done, id DESC LIMIT 100",
            "reminders": "SELECT id, message AS title, due_at AS detail, status, repeat_rule FROM reminders ORDER BY due_at DESC LIMIT 100",
            "contacts": "SELECT id, name AS title, phone || ' ' || relationship AS detail FROM contacts ORDER BY name",
            "calls": "SELECT id, contact_name AS title, direction || ' · ' || status || ' · ' || created_at AS detail FROM phone_calls ORDER BY id DESC LIMIT 50",
            "library": "SELECT id, name AS title, summary AS detail, chars, created_at FROM documents ORDER BY id DESC LIMIT 200",
        }
        if kind == "tools":
            tools = [{"id": i, "title": t.name, "detail": t.description} for i, t in enumerate(available_tools(ctx.settings))]
            if not any(t["title"] == "web_search" for t in tools):
                tools.append({"id": len(tools), "title": "web_search", "detail": "Search the web for current information."})
            return tools
        if kind not in queries:
            raise HTTPException(404, "Unknown list.")
        rows = ctx.db.query(queries[kind])
        if kind == "reminders":
            for r in rows:
                r["detail"] = datetime.fromisoformat(r["detail"]).astimezone(ctx.settings.tz).strftime("%a %d %b %H:%M") + f" · {r['status']}"
                rule = r.pop("repeat_rule", None)
                if rule and r["status"] == "pending":
                    r["detail"] += f" · repeats {describe_repeat(rule)}"
        return rows

    @app.get("/api/weather", dependencies=[Depends(require_user)])
    def weather() -> dict[str, Any]:
        city = ctx.settings.home_city
        if not city:
            return {"available": False, "reason": "Set HOME_CITY in .env"}
        cached = weather_cache.get(city)
        if cached and time.time() - cached[0] < 600:
            return cached[1]
        try:
            data = {"available": True, **fetch_weather(city)}
        except Exception as exc:
            data = {"available": False, "reason": str(exc)}
        weather_cache[city] = (time.time(), data)
        return data

    @app.get("/api/events", dependencies=[Depends(require_user)])
    async def events(request: Request) -> StreamingResponse:
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()
        unsubscribe = ctx.notifier.subscribe(lambda e: loop.call_soon_threadsafe(queue.put_nowait, e))

        async def stream():
            try:
                yield ": connected\n\n"
                while not await request.is_disconnected():
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=15)
                        yield f"data: {json.dumps(event)}\n\n"
                    except asyncio.TimeoutError:
                        yield ": ping\n\n"
            finally:
                unsubscribe()

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # --- phone calls (Twilio webhooks) ---------------------------------------------
    def listen(vr: VoiceResponse, request: Request, call_id: int) -> VoiceResponse:
        gather = Gather(input="speech", action=f"{external_base(request)}/twilio/gather?call_id={call_id}",
                        method="POST", speech_timeout="auto", language="en-US")
        vr.append(gather)
        # Reached only if the caller says nothing: wrap the call up.
        vr.redirect(f"{external_base(request)}/twilio/gather?call_id={call_id}&silent=1", method="POST")
        return vr

    def twiml(vr: VoiceResponse) -> Response:
        return Response(str(vr), media_type="application/xml")

    def add_transcript(call_id: int, speaker: str, text: str) -> None:
        row = ctx.db.one("SELECT transcript FROM phone_calls WHERE id = ?", (call_id,))
        lines = json.loads(row["transcript"]) if row else []
        lines.append({"speaker": speaker, "text": text})
        ctx.db.execute("UPDATE phone_calls SET transcript = ? WHERE id = ?", (json.dumps(lines), call_id))

    def call_brain(call: dict) -> Brain:
        if call["id"] not in call_brains:
            conv = f"call-{call['id']}"
            if call["with_owner"]:
                call_brains[call["id"]] = make_brain(conversation_id=conv, voice=True, effort="low")
            else:
                call_brains[call["id"]] = make_brain(
                    conversation_id=conv, tools=[], web_search=False, remember_facts=False,
                    effort="low", system_prompt=contact_call_prompt(ctx, call))
        return call_brains[call["id"]]

    def is_owner(number: str) -> bool:
        mine = re.sub(r"\D", "", ctx.settings.my_phone_number)
        return bool(mine) and re.sub(r"\D", "", number) == mine

    @app.post("/twilio/voice")
    async def twilio_voice(request: Request) -> Response:
        form = await twilio_form(request)
        vr = VoiceResponse()
        call_id = request.query_params.get("call_id")
        if call_id:  # an outbound call we placed has been answered
            call = ctx.db.one("SELECT * FROM phone_calls WHERE id = ?", (int(call_id),))
            if not call:
                say(vr, "Sorry, something went wrong. Goodbye.")
                vr.hangup()
                return twiml(vr)
            greeting = call["purpose"]
        else:  # someone is calling Jarvis's number
            caller = form.get("From", "")
            owner = is_owner(caller)
            contact = ctx.db.one("SELECT name FROM contacts WHERE phone = ?", (caller,))
            name = ctx.settings.my_name
            if owner:
                greeting = f"Hello {name}. How can I help?"
            else:
                greeting = (f"Hello, you've reached {name}'s assistant, Jarvis. {name} isn't available "
                            "right now. May I take a message?")
            call_id = ctx.db.execute(
                "INSERT INTO phone_calls (call_sid, direction, number, contact_name, purpose, with_owner, created_at) "
                "VALUES (?, 'inbound', ?, ?, ?, ?, ?)",
                (form.get("CallSid", ""), caller, "you" if owner else (contact["name"] if contact else caller),
                 greeting, int(owner), utcnow()),
            )
        add_transcript(int(call_id), "Jarvis", greeting)
        say(vr, greeting)
        return twiml(listen(vr, request, int(call_id)))

    @app.post("/twilio/gather")
    async def twilio_gather(request: Request) -> Response:
        form = await twilio_form(request)
        call_id = int(request.query_params.get("call_id", "0"))
        call = ctx.db.one("SELECT * FROM phone_calls WHERE id = ?", (call_id,))
        vr = VoiceResponse()
        if not call:
            vr.hangup()
            return twiml(vr)
        speech = form.get("SpeechResult", "").strip()
        if not speech:
            if request.query_params.get("silent"):
                say(vr, "I didn't hear anything, so I'll hang up now. Goodbye.")
                vr.hangup()
                finish_call(call_id, "completed")
                return twiml(vr)
            say(vr, "Sorry, I didn't catch that.")
            return twiml(listen(vr, request, call_id))
        add_transcript(call_id, "Caller", speech)
        brain = call_brain(call)
        text = speech
        if not brain.messages and call["with_owner"]:
            text = f"(We're on a phone call. You opened with: \"{call['purpose']}\")\n{speech}"
        try:
            reply = await asyncio.to_thread(brain.chat, text)
            answer = reply.text
        except Exception:
            log.exception("Phone brain failed")
            answer = f"I'm sorry, I'm having trouble thinking right now. Goodbye. {HANGUP}"
        done = HANGUP in answer
        answer = answer.replace(HANGUP, "").strip() or "Goodbye."
        add_transcript(call_id, "Jarvis", answer)
        say(vr, answer)
        if done:
            vr.hangup()
            finish_call(call_id, "completed")
            return twiml(vr)
        return twiml(listen(vr, request, call_id))

    @app.post("/twilio/status")
    async def twilio_status(request: Request) -> Response:
        form = await twilio_form(request)
        status = form.get("CallStatus", "")
        call_id = request.query_params.get("call_id")
        if call_id:
            call = ctx.db.one("SELECT id FROM phone_calls WHERE id = ?", (int(call_id),))
        else:  # a status webhook configured on the Twilio number itself
            call = ctx.db.one("SELECT id FROM phone_calls WHERE call_sid = ?", (form.get("CallSid", ""),))
        if call and status in ("completed", "busy", "no-answer", "failed", "canceled"):
            finish_call(call["id"], status)
        return Response(status_code=204)

    def finish_call(call_id: int, status: str) -> None:
        """Report how a call went. Runs once per call, however many webhooks arrive."""
        call_brains.pop(call_id, None)
        if not ctx.db.execute(
            "UPDATE phone_calls SET status = ? WHERE id = ? AND status NOT LIKE 'done:%'",
            (f"done:{status}", call_id),
        ):
            return
        call = ctx.db.one("SELECT * FROM phone_calls WHERE id = ?", (call_id,))
        who = call["contact_name"] or call["number"]
        if status != "completed":
            if not call["with_owner"]:
                ctx.notifier.publish("call", f"{who} didn't pick up ({status}).")
            return
        if call["with_owner"]:
            return
        lines = json.loads(call["transcript"])
        if not any(line["speaker"] == "Caller" for line in lines):
            if call["direction"] == "inbound":
                ctx.notifier.publish("call", f"Missed call from {who}; they didn't leave a message.")
            else:
                ctx.notifier.publish("call", f"Call to {who} finished; I delivered the message.")
            return
        transcript = "\n".join(f"{line['speaker']}: {line['text']}" for line in lines)
        title = f"Phone call with {who} ({datetime.now(ctx.settings.tz):%d %b %H:%M})"
        ctx.db.execute("INSERT INTO notes (title, body, created_at) VALUES (?, ?, ?)",
                       (title, transcript, utcnow()))
        said = " / ".join(line["text"] for line in lines if line["speaker"] == "Caller")
        ctx.notifier.publish("call", f"Call with {who} finished. They said: {said}")

    return app


def __getattr__(name: str):
    # `uvicorn jarvis.server:app` builds the real app lazily, so importing this
    # module (e.g. in tests) doesn't open the database or need API keys.
    if name == "app":
        globals()["app"] = create_app()
        return globals()["app"]
    raise AttributeError(name)
