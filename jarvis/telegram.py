"""Text Jarvis from your phone with Telegram (optional: set TELEGRAM_BOT_TOKEN).

Make a bot with @BotFather, put its token in the server's settings, then link
it from the dashboard (Settings > Link Telegram): Jarvis shows a one-time code
and only the chat that sends it is ever answered. Everyone else is ignored.

Messages, photos, voice notes and documents go to Jarvis; approvals come back
as Approve / Deny buttons; reminders and the morning briefing are sent too.

On a public server Telegram delivers messages to /telegram/webhook (checked
with a secret header). Without a public address (e.g. at home) Jarvis asks
Telegram for new messages itself instead.
"""

from __future__ import annotations

import hmac
import logging
import secrets
import threading
import time
from collections import deque
from typing import Any, Callable

import httpx

from jarvis.tools import Context, ToolError

log = logging.getLogger("jarvis.telegram")

API = "https://api.telegram.org"
LINK_CODE_SECONDS = 15 * 60
MAX_WRONG_CODES = 5          # then the code stops working and a new one must be made
MAX_MESSAGE = 4000
FORWARD_KINDS = {"reminder", "briefing", "call", "error"}
ICONS = {"reminder": "⏰", "briefing": "🌅", "call": "📞", "error": "⚠️"}


def _same(a: str, b: str) -> bool:
    """Constant-time comparison that also copes with non-ASCII input."""
    return hmac.compare_digest(a.encode(), b.encode())


class TelegramBot:
    def __init__(self, ctx: Context, make_brain: Callable[..., Any], client: Any = None):
        self.ctx = ctx
        self.make_brain = make_brain
        self._http = client or httpx.Client(timeout=40)
        self._brain: Any = None
        self._brain_lock = threading.Lock()
        self._seen: deque[int] = deque(maxlen=200)  # update ids already handled (Telegram retries)
        self._seen_lock = threading.Lock()
        self._stop = threading.Event()
        self._username = ""

    # --- Telegram API ------------------------------------------------------------
    @property
    def enabled(self) -> bool:
        return self.ctx.settings.telegram_enabled

    def call(self, method: str, **params: Any) -> Any:
        resp = self._http.post(f"{API}/bot{self.ctx.settings.telegram_bot_token}/{method}", json=params)
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        if not data.get("ok"):
            raise RuntimeError(f"Telegram {method} failed: {data.get('description') or resp.status_code}")
        return data.get("result")

    def send(self, chat_id: int, text: str, buttons: list[list[dict]] | None = None) -> None:
        text = text.strip() or "…"
        chunks = [text[i:i + MAX_MESSAGE] for i in range(0, len(text), MAX_MESSAGE)]
        for n, chunk in enumerate(chunks):
            extra = {"reply_markup": {"inline_keyboard": buttons}} if buttons and n == len(chunks) - 1 else {}
            self.call("sendMessage", chat_id=chat_id, text=chunk, **extra)

    def username(self) -> str:
        if not self._username:
            self._username = str(self.call("getMe").get("username", ""))
        return self._username

    # --- linking the owner's chat ---------------------------------------------------
    @property
    def owner_chat(self) -> int | None:
        value = self.ctx.db.get_kv("telegram_chat_id")
        return int(value) if value.lstrip("-").isdigit() else None

    def new_link_code(self) -> str:
        # Long and random (it travels inside the t.me link), so it can't be guessed.
        code = secrets.token_urlsafe(18)
        self.ctx.db.set_kv("telegram_link_code", f"{code}:{int(time.time()) + LINK_CODE_SECONDS}:0")
        return code

    def _claim_code(self, supplied: str) -> bool:
        stored = self.ctx.db.get_kv("telegram_link_code")
        code, _, rest = stored.partition(":")
        expires, _, wrong = rest.partition(":")
        if not code or not supplied or int(expires or 0) < time.time():
            return False
        if not _same(code, supplied.strip()):
            tries = int(wrong or 0) + 1
            # Too many wrong guesses: throw the code away.
            self.ctx.db.set_kv("telegram_link_code", "" if tries >= MAX_WRONG_CODES else f"{code}:{expires}:{tries}")
            return False
        self.ctx.db.set_kv("telegram_link_code", "")  # one use only
        return True

    def unlink(self) -> None:
        self.ctx.db.set_kv("telegram_chat_id", "")

    # --- webhook -----------------------------------------------------------------------
    def secret(self) -> str:
        value = self.ctx.db.get_kv("telegram_secret")
        if not value:
            value = secrets.token_urlsafe(32)
            self.ctx.db.set_kv("telegram_secret", value)
        return value

    def check_secret(self, supplied: str) -> bool:
        stored = self.ctx.db.get_kv("telegram_secret")
        return bool(stored and supplied) and _same(stored, supplied)

    def start(self) -> None:
        """Connect to Telegram: a webhook on a public server, polling otherwise."""
        if not self.enabled:
            return
        base = self.ctx.settings.public_base_url
        try:
            if base.startswith("https://"):
                self.call("setWebhook", url=f"{base}/telegram/webhook", secret_token=self.secret(),
                          allowed_updates=["message", "callback_query"], drop_pending_updates=False)
                log.info("Telegram webhook set")
            else:
                info = self.call("getWebhookInfo") or {}
                if info.get("url"):
                    log.info("Telegram is connected to your cloud Jarvis, so this one won't read messages.")
                    return
                threading.Thread(target=self._poll, name="telegram", daemon=True).start()
        except Exception:
            log.exception("Couldn't connect to Telegram (check TELEGRAM_BOT_TOKEN)")

    def stop(self) -> None:
        self._stop.set()

    def _poll(self) -> None:
        offset = 0
        while not self._stop.is_set():
            try:
                updates = self.call("getUpdates", offset=offset, timeout=30,
                                    allowed_updates=["message", "callback_query"]) or []
                for update in updates:
                    offset = max(offset, int(update["update_id"]) + 1)
                    self.handle(update)
            except Exception:
                log.warning("Telegram polling error", exc_info=True)
                self._stop.wait(10)

    # --- incoming messages ---------------------------------------------------------------
    def handle_async(self, update: dict) -> None:
        """Answer in the background so Telegram gets its 200 OK straight away."""
        threading.Thread(target=self.handle, args=(update,), name="telegram-msg", daemon=True).start()

    def handle(self, update: dict) -> None:
        update_id = update.get("update_id")
        with self._seen_lock:
            if update_id in self._seen:
                return
            self._seen.append(update_id)
        try:
            if "callback_query" in update:
                self._on_button(update["callback_query"])
            elif "message" in update:
                self._on_message(update["message"])
        except Exception:
            log.exception("Telegram update failed")

    def brain(self) -> Any:
        with self._brain_lock:  # two messages at once must share one conversation
            if self._brain is None:
                self._brain = self.make_brain(conversation_id="telegram")
            return self._brain

    def _on_message(self, msg: dict) -> None:
        chat_id = (msg.get("chat") or {}).get("id")
        if chat_id is None or (msg.get("chat") or {}).get("type") != "private":
            return
        text = (msg.get("text") or msg.get("caption") or "").strip()
        owner = self.owner_chat
        if text.startswith("/start"):
            code = text[len("/start"):].strip()
            if self._claim_code(code):
                self.ctx.db.set_kv("telegram_chat_id", str(chat_id))
                self.send(chat_id, f"Linked. Good to meet you here, {self.ctx.settings.my_name}. "
                                   "Message me any time; reminders and your morning briefing will come here too.")
            elif chat_id == owner:
                self.send(chat_id, "At your service.")
            else:
                self.send(chat_id, "This is a private assistant. To link it, open Jarvis > Settings > "
                                   "Link Telegram and send the code shown there.")
            return
        if chat_id != owner:
            return  # strangers get nothing
        if text == "/new":
            self.brain().reset()
            self.send(chat_id, "Fresh conversation started.")
            return
        try:
            attachment = self._attachment(msg)
        except Exception as exc:
            self.send(chat_id, f"Sorry, I couldn't get that file: {exc}")
            return
        if not text and not attachment:
            return
        self.call("sendChatAction", chat_id=chat_id, action="typing")
        try:
            if attachment and attachment[2].startswith("audio/"):
                heard = self.brain().describe_image(attachment[1], attachment[2], "", prompt=(
                    "Transcribe this voice message exactly. Reply with only the words spoken."))
                reply = self.brain().chat(heard.strip() or "(an empty voice message)")
            else:
                reply = self.brain().chat(text or "What is this?", attachment=attachment) if attachment \
                    else self.brain().chat(text)
        except Exception as exc:
            log.exception("Telegram chat failed")
            self.send(chat_id, f"Sorry, I hit a problem: {exc}")
            return
        self.send(chat_id, reply.text)
        for action in reply.actions:
            self.send(chat_id, f"Approval needed: {action['summary']}", buttons=[[
                {"text": "✅ Approve", "callback_data": f"a:{action['id']}:1"},
                {"text": "✖️ Deny", "callback_data": f"a:{action['id']}:0"},
            ]])

    def _attachment(self, msg: dict) -> tuple[str, bytes, str] | None:
        if msg.get("photo"):
            biggest = max(msg["photo"], key=lambda p: p.get("file_size", 0) or p.get("width", 0))
            return "photo.jpg", self._download(biggest["file_id"]), "image/jpeg"
        if msg.get("document"):
            doc = msg["document"]
            return doc.get("file_name") or "file", self._download(doc["file_id"]), doc.get("mime_type", "")
        voice = msg.get("voice") or msg.get("audio")
        if voice:
            if self.ctx.settings.provider != "gemini":
                self.send((msg.get("chat") or {}).get("id"),
                          "Voice messages need the Gemini brain; please type instead.")
                return None
            return "voice.ogg", self._download(voice["file_id"]), voice.get("mime_type") or "audio/ogg"
        return None

    def _download(self, file_id: str) -> bytes:
        info = self.call("getFile", file_id=file_id)
        if int(info.get("file_size") or 0) > 10 * 1024 * 1024:
            raise ToolError("That file is too large (10 MB max).")
        resp = self._http.get(f"{API}/file/bot{self.ctx.settings.telegram_bot_token}/{info['file_path']}")
        if resp.status_code != 200:  # (not raise_for_status: its message would carry the bot token)
            raise RuntimeError(f"Telegram answered with error {resp.status_code}.")
        return resp.content

    def _on_button(self, query: dict) -> None:
        from jarvis.brain import resolve_action

        chat_id = ((query.get("message") or {}).get("chat") or {}).get("id")
        owner = self.owner_chat
        if owner is None or chat_id != owner or (query.get("from") or {}).get("id") != owner:
            self.call("answerCallbackQuery", callback_query_id=query["id"], text="Not allowed.")
            return
        kind, _, rest = str(query.get("data", "")).partition(":")
        action_id, _, approve = rest.partition(":")
        if kind != "a" or not action_id.isdigit():
            return
        approve_it = approve == "1"
        self.call("answerCallbackQuery", callback_query_id=query["id"],
                  text="Approved" if approve_it else "Denied")
        message = query.get("message") or {}
        try:
            self.call("editMessageReplyMarkup", chat_id=chat_id, message_id=message.get("message_id"),
                      reply_markup={"inline_keyboard": []})
        except Exception:
            pass
        try:
            row, result = resolve_action(self.ctx, int(action_id), approve_it)
        except ToolError as exc:
            self.send(chat_id, str(exc))
            return
        verdict = "approved" if approve_it else "denied"
        reply = self.brain().chat(f"(I {verdict} action #{action_id}: {row['summary']}. Result: {result})")
        self.send(chat_id, reply.text)

    # --- notifications -------------------------------------------------------------------
    def forward(self, event: dict) -> None:
        """Notifier listener: send reminders, briefings and call reports to the linked chat."""
        if event.get("kind") not in FORWARD_KINDS or not self.enabled:
            return
        owner = self.owner_chat
        if owner is None:
            return
        text = f"{ICONS.get(event['kind'], '🔔')} {event.get('message', '')}"

        def run() -> None:
            try:
                self.send(owner, text)
            except Exception:
                log.warning("Couldn't send a Telegram notification", exc_info=True)

        threading.Thread(target=run, name="telegram-notify", daemon=True).start()
