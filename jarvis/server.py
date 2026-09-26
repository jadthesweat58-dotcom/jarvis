"""Jarvis web server: the browser app, its API, and Twilio phone-call webhooks.

Run it with:  uvicorn jarvis.server:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import hmac
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
from jarvis.brain import Brain, resolve_action
from jarvis.db import utcnow
from jarvis.phone import say
from jarvis.scheduler import ReminderLoop
from jarvis.tools import Context, ToolError

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
    make_brain = brain_factory or (lambda **kw: Brain(ctx, **kw))
    main_brain = make_brain(conversation_id="main")
    call_brains: dict[int, Brain] = {}

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
    def require_user(request: Request) -> None:
        token = ctx.settings.access_token
        supplied = request.query_params.get("token", "")
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            supplied = auth[7:].strip()
        if token:
            if supplied and hmac.compare_digest(supplied, token):
                return
            raise HTTPException(401, "Wrong or missing access token.")
        host = request.client.host if request.client else ""
        if host not in LOCAL_HOSTS:
            raise HTTPException(401, "Set JARVIS_ACCESS_TOKEN to use Jarvis from other devices.")

    async def twilio_form(request: Request) -> dict[str, str]:
        form = {k: str(v) for k, v in (await request.form()).items()}
        if ctx.settings.twilio_auth_token:
            base = ctx.settings.public_base_url or str(request.base_url).rstrip("/")
            url = base + request.url.path + (f"?{request.url.query}" if request.url.query else "")
            signature = request.headers.get("x-twilio-signature", "")
            if not RequestValidator(ctx.settings.twilio_auth_token).validate(url, form, signature):
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
    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html")

    @app.get("/api/status", dependencies=[Depends(require_user)])
    def status() -> dict[str, Any]:
        s = ctx.settings
        return {"name": s.my_name, "mode": s.mode, "model": s.model,
                "phone": s.twilio_enabled, "computer_control": s.is_local}

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
        return {
            "reminders": reminders,
            "todos": ctx.db.query("SELECT id, task, due FROM todos WHERE done = 0 ORDER BY id LIMIT 10"),
            "actions": ctx.db.query(
                "SELECT id, summary FROM pending_actions WHERE status = 'pending' ORDER BY id"),
            "facts": ctx.db.one("SELECT COUNT(*) AS n FROM facts")["n"],
        }

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
    def base_url(request: Request) -> str:
        return ctx.settings.public_base_url or str(request.base_url).rstrip("/")

    def listen(vr: VoiceResponse, request: Request, call_id: int) -> VoiceResponse:
        gather = Gather(input="speech", action=f"{base_url(request)}/twilio/gather?call_id={call_id}",
                        method="POST", speech_timeout="auto", language="en-US")
        vr.append(gather)
        say(vr, "I didn't hear anything, so I'll hang up now. Goodbye.")
        vr.hangup()
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
            return twiml(vr)
        return twiml(listen(vr, request, call_id))

    @app.post("/twilio/status")
    async def twilio_status(request: Request) -> Response:
        form = await twilio_form(request)
        call_id = int(request.query_params.get("call_id", "0"))
        status = form.get("CallStatus", "")
        call = ctx.db.one("SELECT * FROM phone_calls WHERE id = ?", (call_id,))
        if call and status:
            ctx.db.execute("UPDATE phone_calls SET status = ? WHERE id = ?", (status, call_id))
            finish_call(call, status)
        return Response(status_code=204)

    def finish_call(call: dict, status: str) -> None:
        call_brains.pop(call["id"], None)
        who = call["contact_name"] or call["number"]
        if status in ("busy", "no-answer", "failed", "canceled"):
            if not call["with_owner"]:
                ctx.notifier.publish("call", f"{who} didn't pick up ({status}).")
            return
        if status != "completed" or call["with_owner"]:
            return
        lines = json.loads(call["transcript"])
        if not any(line["speaker"] == "Caller" for line in lines):
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
