"""Jarvis web server: the browser app, its API, and Twilio phone-call webhooks.

Run it with:  uvicorn jarvis.server:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import hmac
import time
from collections import deque
import json
import logging
import re
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import Gather, VoiceResponse

from jarvis.app import build_context
from jarvis.brain import Brain, create_brain, resolve_action
from jarvis.db import utcnow
from jarvis.phone import say
from jarvis.scheduler import ReminderLoop
from jarvis.tools import Context, ToolError, available_tools
from jarvis.tools.web import fetch_weather

log = logging.getLogger("jarvis.server")
STATIC = Path(__file__).parent / "static"
LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}
HANGUP = "[HANGUP]"


class ChatIn(BaseModel):
    text: str


class ActionIn(BaseModel):
    approve: bool


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


def create_app(ctx: Context | None = None, brain_factory: Callable[..., Brain] | None = None) -> FastAPI:
    ctx = ctx or build_context()
    make_brain = brain_factory or (lambda **kw: create_brain(ctx, **kw))
    main_brain = make_brain(conversation_id="main")
    call_brains: dict[int, Brain] = {}
    feed: deque[dict] = deque(maxlen=30)  # recent notifications, for the live feed
    ctx.notifier.subscribe(feed.appendleft)
    weather_cache: dict[str, Any] = {}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        loop = ReminderLoop(ctx)
        loop.start()
        if not ctx.settings.access_token:
            log.warning("JARVIS_ACCESS_TOKEN is not set: only this computer (localhost) can use Jarvis.")
        yield
        loop.stop()

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

    def run_chat(brain: Brain, text: str) -> dict[str, Any]:
        try:
            reply = brain.chat(text)
        except Exception as exc:
            log.exception("Chat failed")
            raise HTTPException(500, f"Jarvis hit a problem: {exc}") from exc
        return {"reply": reply.text, "actions": reply.actions}

    # --- browser app -------------------------------------------------------------
    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html")

    @app.get("/api/status", dependencies=[Depends(require_user)])
    def status() -> dict[str, Any]:
        s = ctx.settings
        return {"name": s.my_name, "mode": s.mode, "model": s.model,
                "phone": s.twilio_enabled, "computer_control": s.is_local,
                "two_way_calls": s.twilio_enabled and bool(s.public_base_url),
                "ai_name": s.provider_name, "ai_ready": bool(s.ai_key), "web_search": bool(s.ai_key),
                "home_city": s.home_city, "timezone": s.timezone}

    @app.post("/api/chat", dependencies=[Depends(require_user)])
    def chat(body: ChatIn) -> dict[str, Any]:
        if not body.text.strip():
            raise HTTPException(400, "Say something first.")
        return run_chat(main_brain, body.text.strip())

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
        reminders = ctx.db.query(
            "SELECT id, message, due_at FROM reminders WHERE status = 'pending' ORDER BY due_at LIMIT 10")
        for r in reminders:
            r["due_local"] = datetime.fromisoformat(r["due_at"]).astimezone(tz).strftime("%a %H:%M")
        count = lambda sql: ctx.db.one(sql)["n"]  # noqa: E731
        blocks = [b for m in main_brain.messages if isinstance(m.get("content"), list) for b in m["content"]]
        return {
            "reminders": reminders,
            "todos": ctx.db.query("SELECT id, task, due FROM todos WHERE done = 0 ORDER BY id LIMIT 10"),
            "actions": ctx.db.query(
                "SELECT id, summary FROM pending_actions WHERE status = 'pending' ORDER BY id"),
            "facts": count("SELECT COUNT(*) AS n FROM facts"),
            "counts": {
                "facts": count("SELECT COUNT(*) AS n FROM facts"),
                "notes": count("SELECT COUNT(*) AS n FROM notes"),
                "todos": count("SELECT COUNT(*) AS n FROM todos WHERE done = 0"),
                "reminders": count("SELECT COUNT(*) AS n FROM reminders WHERE status = 'pending'"),
                "contacts": count("SELECT COUNT(*) AS n FROM contacts"),
                "calls": count("SELECT COUNT(*) AS n FROM phone_calls"),
                "turns": sum(1 for m in main_brain.messages if m["role"] == "user"
                             and any(b.get("type") == "text" for b in m["content"])),
                "tool_calls": sum(1 for b in blocks if b.get("type") in ("tool_use", "server_tool_use")),
                "tools": len(available_tools(ctx.settings)) + 1,  # +1 for web search
            },
            "system": system_stats(),
            "feed": list(feed),
        }

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

    @app.get("/api/list/{kind}", dependencies=[Depends(require_user)])
    def list_items(kind: str) -> list[dict[str, Any]]:
        queries = {
            "facts": "SELECT id, fact AS title, category AS detail FROM facts ORDER BY id DESC",
            "notes": "SELECT id, title, body AS detail FROM notes ORDER BY id DESC LIMIT 100",
            "todos": "SELECT id, task AS title, COALESCE(due, '') AS detail, done FROM todos ORDER BY done, id DESC LIMIT 100",
            "reminders": "SELECT id, message AS title, due_at AS detail, status FROM reminders ORDER BY due_at DESC LIMIT 100",
            "contacts": "SELECT id, name AS title, phone || ' ' || relationship AS detail FROM contacts ORDER BY name",
            "calls": "SELECT id, contact_name AS title, direction || ' · ' || status || ' · ' || created_at AS detail FROM phone_calls ORDER BY id DESC LIMIT 50",
        }
        if kind == "tools":
            tools = [{"id": i, "title": t.name, "detail": t.description} for i, t in enumerate(available_tools(ctx.settings))]
            return tools + [{"id": len(tools), "title": "web_search", "detail": "Search the web (built into Claude)."}]
        if kind not in queries:
            raise HTTPException(404, "Unknown list.")
        rows = ctx.db.query(queries[kind])
        if kind == "reminders":
            for r in rows:
                r["detail"] = datetime.fromisoformat(r["detail"]).astimezone(ctx.settings.tz).strftime("%a %d %b %H:%M") + f" · {r['status']}"
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
