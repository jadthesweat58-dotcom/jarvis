# JARVIS — your personal AI assistant

Jarvis is your own AI assistant, powered by Google Gemini (or Claude, if you prefer). You can **talk to it** (voice or text) from a
"command center" web dashboard on your computer or phone. It can:

- 🧠 **Remember you**: facts, preferences, people and plans, kept between conversations
- 📝 **Notes & to-dos**: save ideas and manage your task list
- 🌐 **Web search & weather**: look things up online and check the forecast
- ⏰ **Reminders & timers**: one-off or repeating (daily, weekdays, weekly, monthly); alerts on
  screen, spoken aloud, as a **phone notification**, on **Telegram**, or by **phone call / text**
- 📎 **Read your files**: drop a PDF, Word document, picture or text file into the chat
- 📅 **Your calendar** (optional): today's meetings in the timeline and the morning briefing
- 🧮 **Handy extras**: exact maths, currency conversion, world clock, prayer times, reading web pages
- 🔁 **Routines**: jobs Jarvis does by itself on a schedule and sends you the result
- 🔎 **Watchers**: "tell me when this drops below 500 AED" or "when this page changes"
- 📈 **Live ticker**: prices, football scores and headlines across the dashboard
- 📚 **Second brain**: every file you share is saved to a searchable library
- 🎨 **Pictures**: "make me a poster of…", "turn this photo into a cartoon"
- 🌙 **Evening wrap-up**: what you got done, what's left, tomorrow's plan, and a gentle nudge
- 📧 **Gmail** (optional): "any important emails today?", draft replies, send with your approval
- 🎙️ **Hands-free conversation**: talk back and forth without pressing anything
- 🖥️ **On your computer**: music, volume, brightness, Do Not Disturb, lock screen, WhatsApp
  messages, and a menu-bar icon that starts with your Mac
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
  - "Give me my briefing."
  - "Remind me every weekday at 8am to take my vitamins."
  - "How much is 250 dollars in dirhams?" / "What time is it in Tokyo?"
  - "Summarise this article: https://…"
  - (local mode) "Open Spotify" / "What's in my Downloads folder?"
- **Attach a file**: click the 📎 next to the message box (or drag a file onto the chat box, or
  paste a picture), then ask about it or just press **Send** for a summary. PDFs, Word
  documents, pictures and text/code files up to 10 MB. Jarvis keeps only the text it reads.

## Install Jarvis as an app + phone notifications

- **iPhone**: open your Jarvis address in Safari → **Share** → **Add to Home Screen**. Open Jarvis
  from the new icon, enter your access token once, then gear ⚙ → tick **Notifications on this
  device** and allow. (iOS 16.4 or newer.)
- **Android / Chrome / Edge**: gear ⚙ → **Install Jarvis as an app** (or the install icon in the
  address bar), then tick **Notifications on this device**.
- Reminders, the morning briefing and call reports then pop up even when Jarvis is closed.
  **Send a test notification** checks it works. No account or key is needed for this.

## Telegram (optional)

Message Jarvis from Telegram, send it photos, documents and voice notes (voice needs Gemini),
approve actions with buttons, and get reminders and your briefing there.
1. In Telegram, open **@BotFather**, send `/newbot`, pick a name, and copy the token.
2. Render → your service → **Environment** → add `TELEGRAM_BOT_TOKEN` (never paste it in a chat).
3. In Jarvis: gear ⚙ → **Link Telegram** → **Open Telegram and press Start**. Only your chat is
   ever answered; everyone else is ignored. Send `/new` to start a fresh conversation.

## Your calendar (optional, read-only)

Google Calendar → ⚙ Settings → click your calendar on the left → **Integrate calendar** → copy
**Secret address in iCal format**. Put it in Render → **Environment** as `CALENDAR_ICS_URL`
(several calendars: separate with commas). Today's events then show in the Mission Timeline (◆),
in the morning briefing, and Jarvis can answer "what's on my calendar this week?". Outlook and
iCloud calendars work too with their published .ics link. Treat the link like a password.

## Evening wrap-up

Every evening at **21:00** (`WRAPUP_TIME`, or `off`) Jarvis sends a short wrap-up: what you
finished today, what's still open, a kind nudge about important tasks that have waited 3+ days,
and tomorrow's reminders and calendar. Ask any time: *"How did my day go?"* / *"What's tomorrow?"*

## Hands-free conversation

Tap the **waves** button next to Send and just talk: Jarvis answers, then listens again by itself.
Say *"stop"*, *"that's all"* or *"thanks Jarvis"* to end, or tap the button. It also ends after two
silences. Tap **Talk** while Jarvis is speaking to cut it short. (Chrome, Edge or Safari.)

## Routines and watchers

- **Routines** are jobs Jarvis does on its own and sends you: *"Every Friday at 6pm, find fun
  things to do in Dubai this weekend"*, *"Every weekday at 7:45, give me the top tech news"*.
  They can search the web, read pages, and check weather, prices and currencies. They can't see your
  private data (notes, library, contacts, calendar) or change anything, so a web page with hidden
  instructions can't trick a routine into leaking or doing things. You approve each new routine
  and watcher with the same Approve button as calls.
- **Watchers** check a web page every few hours: *"Watch this page and tell me when it's under 500
  AED: https://…"* or *"Tell me when this page changes"*. Jarvis ignores trivial changes (dates,
  counters) and doesn't use the AI when the page hasn't changed. Some shops block automatic
  checks; after 3 failures Jarvis tells you and pauses.
- Results arrive in the chat box, as a phone notification and on Telegram. See, run, pause or
  delete them under **Automations** in the sidebar. Up to 20 of each. Each run uses a little
  Gemini, so keep an eye on the usage meter.
- They run while the server is awake, so keep the UptimeRobot monitor on.

## Live ticker, library and pictures

- **Live ticker** (under the clock): crypto and stock prices, gold, football scores and UAE
  headlines, all from free sources. Change it with ⚙ → **Customize the live ticker**, or just say
  *"add Tesla and Solana to my ticker"* / *"show LaLiga scores"*. Ask *"what's Bitcoin at?"* any time.
- **Library** (sidebar): every file you attach is saved as text so you can ask later: *"what did
  the lease say about the notice period?"*. *"Save this article to my library: https://…"* works
  too. Remove documents from the Library view. Search understands meaning (with the Gemini key)
  and falls back to keywords.
- **Pictures**: *"Make me a poster for my birthday party, neon style"*, then *"make it purple"*.
  Send a photo and ask *"turn this into a cartoon"*. Pictures show in the chat (and on Telegram);
  the newest 40 are kept. Uses Google's image model on your Gemini key and costs a few cents each
  (`IMAGE_MODEL` can pick a specific model).

## Gmail (optional, one-time Google setup)

Jarvis uses your **own** Google Cloud app, so your mail goes only between Google and your Jarvis.
1. Go to https://console.cloud.google.com, sign in, and **create a project** (e.g. "Jarvis").
2. **APIs & Services → Library** → search **Gmail API** → **Enable**.
3. **APIs & Services → OAuth consent screen** (Google Auth Platform): app name "Jarvis", your
   email, **External**. Under **Audience**, add your Gmail address as a **test user**, then click
   **Publish app** (otherwise Google logs Jarvis out every 7 days). You don't need to submit it
   for verification.
4. **Clients → Create client → Web application**. Under **Authorized redirect URIs** add
   `https://jarvis-hzqs.onrender.com/google/callback` (and `http://localhost:8000/google/callback`
   for your computer). Create, then copy the **Client ID** and **Client secret**.
5. Render → your service → **Environment**: add `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`
   (never paste them in a chat). Save; Render restarts.
6. In Jarvis: gear ⚙ → **Connect Gmail** → sign in → Google warns the app isn't verified (it's
   yours): **Advanced → Go to Jarvis** → **Allow**.

**Safety:** emails and web pages are written by other people and can contain hidden instructions.
After Jarvis reads one, anything else it wants to do in that turn (open a link, save something,
draft a reply…) shows an **Approve** button first. Phone calls to Jarvis never get your email.

Then: *"Any important emails today?"*, *"Read the one from the bank"*, *"Draft a reply saying
I'll pay Friday"*, *"Send it"* (you approve every email). The morning briefing mentions important
unread mail. Disconnect any time from the same menu.

## On your own computer: Mac controls, WhatsApp, start at login

With `JARVIS_MODE=local`, Jarvis can also:
- **Music:** *"pause the music"*, *"next song"*, *"what's playing?"* (Spotify or Apple Music)
- **Volume and brightness:** *"volume 30"*, *"mute"*, *"brightness down"*
- **Do Not Disturb:** in the Shortcuts app, make two shortcuts named **Jarvis Focus On** and
  **Jarvis Focus Off**, each with the action *Set Focus* (Do Not Disturb on / off). Then
  *"turn on do not disturb"*. Jarvis can also run any other Shortcut you name (you approve it).
- **Lock the screen**, and **empty the Trash** (you approve it)
- **WhatsApp:** *"WhatsApp Ahmed: running 10 minutes late"*. You approve it; it opens WhatsApp on
  that chat with the message typed in. If WhatsApp was already open on your Mac, Jarvis presses
  Enter for you; otherwise (and on Windows) you press Enter, so a message can never go to the
  wrong chat while WhatsApp is still loading. Uses saved contacts or +971… numbers.
- The first time, macOS asks to let Terminal/Python control your Mac: **System Settings →
  Privacy & Security → Accessibility** (and **Automation**) → allow it.

**Start with your Mac:** double-click `scripts/autostart.command` once (Windows:
`scripts\autostart.bat`). Jarvis then starts at login with an icon in the menu bar (Windows: by
the clock): **Open Jarvis**, **Listen for claps**, **Hear today's briefing**, **Quit**. Undo with
`./scripts/autostart.command off`. Logs: `~/Library/Logs/Jarvis.log`.

## Usage meter and backup

The System Monitor panel shows today's AI calls and tokens and, with ElevenLabs, this month's
voice characters against your plan's quota (`ELEVENLABS_MONTHLY_CHARS`, default 10,000). The bar
turns amber at 80%. Gear ⚙ → **Download my data** saves everything Jarvis remembers (facts,
notes, tasks, reminders, contacts, calls) as a JSON file.

## Daily briefing

Every morning at **7:30** (your `TIMEZONE`), Jarvis puts together a short spoken briefing:
- the weather in your `HOME_CITY`
- today's calendar events (if you've connected a calendar)
- today's reminders
- your most important open tasks
- the top 3 news headlines (UAE and your city, plus one world story)

It appears in the chat box and as a notification, and is read aloud if the dashboard is open.

- Hear it any time: click **Briefing** above the chat box, or just ask "Jarvis, give me my
  briefing".
- Change the time with `BRIEFING_TIME` (e.g. `06:45`), or set it to `off`. Render → your service →
  **Environment**.
- On your own computer, a **double clap** greets you and then reads the briefing out loud
  (`CLAP_BRIEFING=off` to skip it; for the cloud Jarvis also put `JARVIS_ACCESS_TOKEN` in `.env`).
- On Render's free plan, keep the UptimeRobot monitor running so Jarvis is awake at 7:30. If
  it was asleep, the briefing goes out as soon as it wakes, as long as it's still morning.

## Let Jarvis see your screen

- **In the dashboard (cloud or local):** click the **eye** button next to the chat box and pick
  the screen or window to share. While sharing, each message you send (typed or spoken) carries
  a snapshot of your screen, so you can ask "what does this error mean?" or "summarize this
  page". Click the eye again (or the browser's own **Stop sharing**) to stop. Works in desktop
  Chrome, Edge and Safari.
- **Jarvis on your own computer (`JARVIS_MODE=local`):** just ask "Jarvis, what's on my
  screen?" and it takes a screenshot itself. Install the extras with
  `pip install -r requirements-local.txt`; on a Mac, allow **Screen Recording** for Terminal in
  System Settings > Privacy & Security the first time.

Jarvis looks at each screenshot once and keeps a short written note of what it saw; the picture
itself isn't saved.

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
| `CALENDAR_ICS_URL` | Your calendar's secret iCal link(s), comma-separated (optional) |
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather, to chat with Jarvis on Telegram (optional) |
| `WRAPUP_TIME` | Evening wrap-up time (default `21:00`), or `off` |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Your Google OAuth client, for Gmail (optional) |

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
- When Jarvis reads a web page for you, it refuses addresses on private networks (including
  after redirects), so a web page can't trick it into poking at the server's own network.
- The Telegram bot only answers the one chat linked with a one-time code; Telegram's messages are
  checked with a secret header. Approvals from Telegram need the same Approve tap.

## How it's built

```
jarvis/
  brain.py        conversation loop (Claude): tools, approvals, saved history
  gemini_brain.py the same loop on Google Gemini
  server.py       FastAPI web server: dashboard API, live events, Twilio webhooks
  cli.py          terminal chat
  tools/          memory, notes, web (weather), reminders, calls, computer, extras
  files.py        reading attached files (PDF, Word, pictures, text)
  push.py         phone notifications (Web Push)
  telegram.py     Telegram bot
  agenda.py       calendar (iCal link)
  usage.py        usage meter
  automations.py  routines and watchers (run by the scheduler)
  hud.py          live ticker data (prices, headlines, football)
  library.py      the searchable document library
  images.py       pictures Jarvis makes
  google_ai.py    Gemini embeddings and picture generation
  wrapup.py       evening wrap-up
  gmail.py        Gmail (OAuth, read, draft, send)
  tray.py         menu-bar / tray app; autostart.py starts it at login
  safeurl.py      safe fetching of web pages
  phone.py        Twilio calls & texts
  scheduler.py    fires reminders
  db.py           storage: SQLite file (data/jarvis.db), or Supabase/Postgres or Turso online
  static/         the command-center web app (HTML/CSS/JS, no build step)
tests/            pytest suite (uses fake Gemini, Claude & Twilio; no keys needed)
```

Run the tests: `pip install -r requirements-dev.txt && python -m pytest`
