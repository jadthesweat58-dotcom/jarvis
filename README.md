# JARVIS — your personal AI assistant

Jarvis is your own AI assistant, powered by Claude. You can **talk to it** (voice or text) from a
"command center" web dashboard on your computer or phone. It can:

- 🧠 **Remember you**: facts, preferences, people and plans, kept between conversations
- 📝 **Notes & to-dos**: save ideas and manage your task list
- 🌐 **Web search & weather**: look things up online and check the forecast
- ⏰ **Reminders & timers**: alerts on screen, spoken aloud, or by **phone call / text**
- 📞 **Phone calls**: Jarvis can call or text **you**, and call **other people** for you (it
  delivers a message, chats with them and reports back). You can also **phone Jarvis** and talk.
- 💻 **Control your computer** (when running on your own machine): open apps and websites, run
  commands, read files

Anything risky (calling or texting someone else, running a command, writing a file) shows
**Approve / Deny** buttons first. Jarvis never does it without your OK.

---

## 1. Get your keys

| What | Needed for | Where |
|---|---|---|
| **Anthropic API key** | Everything (required) | https://console.anthropic.com → API Keys |
| **Twilio** account SID, auth token and phone number | Calls & texts (optional) | https://www.twilio.com/console |

> Twilio trial accounts can only call and text numbers you have verified in the Twilio console.

## 2. Put Jarvis in the cloud (recommended first)

Jarvis ships as a Docker app, so it runs on any host. The easiest is **Render**:

1. Push this repository to GitHub (already done if you're reading this there).
2. Go to https://dashboard.render.com → **New → Blueprint** → pick this repo. Render reads
   `render.yaml` and sets everything up, including a disk so Jarvis's memory survives restarts.
3. Fill in the settings it asks for:
   - `ANTHROPIC_API_KEY`: your key
   - `MY_NAME`: what Jarvis calls you
   - `TIMEZONE`: e.g. `America/New_York`, `Europe/London`, `Asia/Karachi`
   - `HOME_CITY`: e.g. `London, UK` (for weather)
   - Twilio values and `MY_PHONE_NUMBER` (optional; format `+15551234567`)
   - `PUBLIC_BASE_URL`: your Render address, e.g. `https://jarvis-xxxx.onrender.com`
     (fill this in after the first deploy; it's needed for two-way phone conversations)
4. Deploy. Open your Render URL, and when asked for the **access token**, copy
   `JARVIS_ACCESS_TOKEN` from the service's *Environment* tab (Render generated it for you).

**Other hosts** (Railway, Fly.io, a VPS…): deploy the `Dockerfile`, set the same environment
variables (see `.env.example`), set a strong `JARVIS_ACCESS_TOKEN`, and mount a volume at `/data`.

### Let people phone Jarvis (optional)
In the Twilio console → Phone Numbers → your number → **Voice → "A call comes in"** → Webhook →
`https://YOUR-JARVIS-URL/twilio/voice` (HTTP POST). Calls from `MY_PHONE_NUMBER` get the full
Jarvis; anyone else can leave a message, which appears in your feed and notes.

## 3. Run Jarvis on your own computer (later)

1. Install Python 3.11 or newer from https://www.python.org (Windows: tick "Add Python to PATH").
2. Download/clone this repo.
3. Start it:
   - **Windows**: double-click `scripts\start.bat`
   - **Mac / Linux**: run `./scripts/start.sh` in a terminal
4. The first run creates a `.env` file. Open it, paste your `ANTHROPIC_API_KEY`, and set
   `JARVIS_MODE=local` if you want Jarvis to control your computer. Run the script again.
5. Your browser opens `http://localhost:8000`. (On your own computer no access token is needed.)

Prefer the terminal? `python -m jarvis.cli` gives you a text chat.

## 4. Talking to Jarvis

- **Type** in the "Ask Jarvis anything…" box, or tap **TALK TO JARVIS** / the mic and speak.
- Turn on **Wake Word** and just say *"Jarvis, what's on my to-do list?"*
- Voice input works in **Chrome, Edge and Safari**, and needs `https://` (the cloud) or `localhost`.
- Try:
  - "Remember that my sister's birthday is 3 March."
  - "Remind me in 20 minutes to take the pizza out."
  - "Remind me tomorrow at 9am to call the bank, and phone me for it."
  - "What's the weather this weekend?"
  - "Save Mom's number, +15551234567, and call her to say I'm running late."
  - "Give me my executive briefing."
  - (local mode) "Open Spotify" / "What's in my Downloads folder?"

## Settings (`.env`)

See `.env.example` for all of them. The main ones:

| Setting | Meaning |
|---|---|
| `JARVIS_MODE` | `cloud` (safe, no computer control) or `local` (can control this computer) |
| `JARVIS_MODEL` | Claude model, default `claude-opus-5` |
| `JARVIS_EFFORT` | `low` (fastest/cheapest) · `medium` (default) · `high` (smartest) |
| `JARVIS_ACCESS_TOKEN` | Password for the web app. **Required in the cloud.** |
| `JARVIS_FILES_ROOT` | The only folder Jarvis may read/write in local mode (default: your home folder) |

## Safety notes

- Anyone with your URL **and** access token can use Jarvis, so keep the token secret.
- Twilio webhooks are verified with your Twilio auth token, so strangers can't fake them.
- Caller ID can be spoofed. Calls "from your number" get full Jarvis, but calling or texting
  others still requires approval in the web app.
- Computer control is off in the cloud and every command/file write needs your approval.

## How it's built

```
jarvis/
  brain.py        Claude conversation loop: tools, approvals, saved history
  server.py       FastAPI web server: dashboard API, live events, Twilio webhooks
  cli.py          terminal chat
  tools/          memory, notes, web (weather), reminders, calls, computer
  phone.py        Twilio calls & texts
  scheduler.py    fires reminders
  db.py           SQLite storage (data/jarvis.db)
  static/         the command-center web app (HTML/CSS/JS, no build step)
tests/            pytest suite (uses fake Claude & Twilio, no keys needed)
```

Run the tests: `pip install -r requirements-dev.txt && python -m pytest`
