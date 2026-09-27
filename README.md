# JARVIS — your personal AI assistant

Jarvis is your own AI assistant, powered by Google Gemini (or Claude, if you prefer). You can **talk to it** (voice or text) from a
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
| **Gemini API key** | Everything (required) | https://aistudio.google.com/apikey → Create API key |
| **Twilio** account SID, auth token and phone number | Calls & texts (optional) | https://www.twilio.com/console |

> Twilio trial accounts can only call and text numbers you have verified in the Twilio console.

## 2. Put Jarvis in the cloud for free (recommended first)

Jarvis ships as a Docker app, so it runs on any host. This setup costs nothing: **Render**'s free
plan runs Jarvis, and a free **Supabase** database holds its memory (Render's free plan wipes its
disk on every restart, so the memory lives online instead).

**A. Create the memory database (Supabase, free)**
1. Sign up at https://supabase.com and create a **new project** (any name, e.g. `jarvis`).
   Choose a **database password** using only letters and numbers (symbols like `@` or `#` break
   the connection string) and save it somewhere safe. Pick the region closest to you.
2. When the project is ready, click **Connect** (top of the page) and choose
   **Session pooler**. Copy the connection string; it looks like
   `postgresql://postgres.abcdefgh:[YOUR-PASSWORD]@aws-0-….pooler.supabase.com:5432/postgres`.
   (Use the *pooler* one: Render can't reach Supabase's "direct connection".)
3. Replace `[YOUR-PASSWORD]` with your database password. That full line is your `DATABASE_URL`.
   Jarvis creates its tables automatically on first start.

**B. Deploy Jarvis (Render, free)**
1. Go to https://dashboard.render.com → **New → Blueprint** → pick this repo. Render reads
   `render.yaml` and sets everything up.
2. Fill in the settings it asks for:
   - `GEMINI_API_KEY`: your Gemini key
   - `DATABASE_URL`: the Supabase connection string from step A
   - `MY_NAME`: what Jarvis calls you
   - `TIMEZONE`: e.g. `Asia/Dubai`, `Europe/London`, `America/New_York`
   - `HOME_CITY`: e.g. `Dubai` (for weather)
   - Twilio values and `MY_PHONE_NUMBER`: optional, leave empty to skip phone calls
   - `PUBLIC_BASE_URL`: leave empty on Render (Jarvis detects its address automatically).
3. Deploy. Open your Render URL, and when asked for the **access token**, copy
   `JARVIS_ACCESS_TOKEN` from the service's *Environment* tab (Render generated it for you).

**C. Keep it awake (free)**
Render's free plan puts Jarvis to sleep after about 15 minutes without visitors, and a sleeping
Jarvis can't fire reminders. A free monitor such as https://uptimerobot.com can visit
`https://YOUR-JARVIS-URL/healthz` every 5 minutes to keep it awake.

Want no sleeping and no Supabase? Change `plan: free` to `plan: starter` in `render.yaml` (paid)
and add a disk mounted at `/data` instead. (Turso also works as the online database: set
`TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` instead of `DATABASE_URL`.)

**Other hosts** (Railway, Fly.io, a VPS…): deploy the `Dockerfile`, set the same environment
variables (see `.env.example`), set a strong `JARVIS_ACCESS_TOKEN` and `PUBLIC_BASE_URL`, and either
set `DATABASE_URL` or mount a volume at `/data`.

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
4. The first run creates a `.env` file. Open it, paste your `GEMINI_API_KEY`, and set
   `JARVIS_MODE=local` if you want Jarvis to control your computer. To share memories with your
   cloud Jarvis, also paste the same `DATABASE_URL` (if both run at once, reminders may pop up
   on both). Run the script again.
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

## Clap twice to open Jarvis (your own computer)

Like Tony Stark: clap twice and Jarvis opens in your browser and greets you out loud.

1. Set up Jarvis on your computer (section 3), or just clone the repo if you only want to open
   your cloud Jarvis: then set `JARVIS_URL=https://your-jarvis.onrender.com` in `.env`.
2. Start the clap listener:
   - **Mac**: double-click `scripts/clap.command` (the first time macOS asks to let Terminal use
     the microphone: click **Allow**)
   - **Windows**: double-click `scripts\clap.bat`
3. Clap twice, about a quarter to half a second apart.

Tuning: run `scripts/clap.command --test` to see when it hears claps without opening anything,
or `--levels` to watch the sound level. Set `CLAP_SENSITIVITY` (1-10, default 5) in `.env`:
higher hears quieter claps. To have it always ready, add the script to your Mac's
**Login Items** (System Settings > General) or Windows' Startup folder.

Privacy: the microphone is only checked for the clap pattern, a tiny slice at a time; nothing
is recorded, saved or sent anywhere.

## Jarvis's voice (ElevenLabs, optional)

By default Jarvis speaks with your browser's built-in voice. For a realistic voice:

1. Sign up at https://elevenlabs.io and create an API key (Profile / **API Keys**).
2. Open the **Voice Library**, pick a voice you like (a calm British male suits Jarvis) and copy
   its **Voice ID**.
3. Add `ELEVENLABS_API_KEY` and `ELEVENLABS_VOICE_ID` in Render → your service → **Environment**
   (or in `.env` on your computer). Render redeploys by itself.

The key stays on the server. Long replies are cut at 1,000 characters to save your monthly
quota, and if ElevenLabs stops working (quota used up, bad key) Jarvis says so once and
switches back to the built-in voice.

## Settings (`.env`)

See `.env.example` for all of them. The main ones:

| Setting | Meaning |
|---|---|
| `JARVIS_MODE` | `cloud` (safe, no computer control) or `local` (can control this computer) |
| `JARVIS_PROVIDER` | `gemini` (default) or `claude`. With `claude`, set `ANTHROPIC_API_KEY` instead |
| `JARVIS_MODEL` | Leave empty for the default (`gemini-3.8-flash`); `gemini-3.1-flash-lite` is cheaper |
| `JARVIS_EFFORT` | `low` (fastest/cheapest) · `medium` (default) · `high` (smartest) |
| `JARVIS_ACCESS_TOKEN` | Password for the web app. **Required in the cloud.** |
| `JARVIS_FILES_ROOT` | The only folder Jarvis may read/write in local mode (default: your home folder) |

## Safety notes

- Anyone with your URL **and** access token can use Jarvis, so keep the token secret.
- Twilio webhooks are verified with your Twilio auth token, so strangers can't fake them.
- Caller ID can be spoofed. Calls "from your number" get full Jarvis, but calling or texting
  others still requires approval in the web app.
- Computer control is off in the cloud. On your computer, opening apps/websites, running
  commands and writing files all need your approval, and hidden files (`.ssh`, `.env`, …) are
  off limits.
- Without an access token, Jarvis only answers requests from this computer's own browser
  (other websites can't talk to it).

## How it's built

```
jarvis/
  brain.py        conversation loop (Claude): tools, approvals, saved history
  gemini_brain.py the same loop on Google Gemini
  server.py       FastAPI web server: dashboard API, live events, Twilio webhooks
  cli.py          terminal chat
  tools/          memory, notes, web (weather), reminders, calls, computer
  phone.py        Twilio calls & texts
  scheduler.py    fires reminders
  db.py           storage: SQLite file (data/jarvis.db), or Supabase/Postgres or Turso online
  static/         the command-center web app (HTML/CSS/JS, no build step)
tests/            pytest suite (uses fake Gemini, Claude & Twilio; no keys needed)
```

Run the tests: `pip install -r requirements-dev.txt && python -m pytest`
