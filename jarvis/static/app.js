// JARVIS Command Center: chat, voice in/out, tasks, timeline, approvals,
// live notifications, system monitor and the animated AI core.
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  };

  // ------------------------------------------------------------------ icons
  const ICONS = {
    grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    message: '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/>',
    check: '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="m8 12 3 3 5-6"/>',
    calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/>',
    database: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
    file: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6M8 13h8M8 17h6"/>',
    users: '<circle cx="9" cy="8" r="4"/><path d="M2 21v-1a6 6 0 0 1 12 0v1M16 3.5a4 4 0 0 1 0 9M22 21v-1a6 6 0 0 0-4-5.6"/>',
    phone: '<path d="M22 16.9v3a2 2 0 0 1-2.2 2A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z"/>',
    tool: '<path d="M14.7 6.3a4 4 0 0 0-5.4 5.1L3 17.7V21h3.3l6.3-6.3a4 4 0 0 0 5.1-5.4l-2.5 2.5-2.7-.6-.6-2.7z"/>',
    mic: '<rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10a7 7 0 0 0 14 0M12 17v5M8 22h8"/>',
    zap: '<path d="M13 2 3 14h9l-1 8 10-12h-9z"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    bell: '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21v-1a7 7 0 0 1 14 0v1"/>',
    cpu: '<rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>',
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
    shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
    monitor: '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    cloud: '<path d="M18 10h-1.3A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"/>',
    wifi: '<path d="M5 12.6a11 11 0 0 1 14 0M8.5 16.1a6 6 0 0 1 7 0M2 8.8a16 16 0 0 1 20 0"/><circle cx="12" cy="20" r="1"/>',
    pin: '<path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 0 1 16 0z"/><circle cx="12" cy="10" r="3"/>',
    play: '<circle cx="12" cy="12" r="10"/><path d="m10 8 6 4-6 4z"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    x: '<path d="M18 6 6 18M6 6l12 12"/>',
    brain: '<path d="M9 3a3 3 0 0 0-3 3 3 3 0 0 0-2 5 3 3 0 0 0 2 5 3 3 0 0 0 6 1V4a3 3 0 0 0-3-1zM15 3a3 3 0 0 1 3 3 3 3 0 0 1 2 5 3 3 0 0 1-2 5 3 3 0 0 1-6 1"/>',
    speaker: '<path d="M11 5 6 9H2v6h4l5 4z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M19 5a10 10 0 0 1 0 14"/>',
    alert: '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
    book: '<path d="M4 19V5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2zm0 0a2 2 0 0 0 2 2h13"/><path d="M9 7h6"/>',
    stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/>',
  };
  const icon = (name) => `<svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ICONS.grid}</svg>`;
  const iconEl = (name) => { const i = el("i"); i.dataset.icon = name; i.innerHTML = icon(name); return i; };
  const paintIcons = (root = document) => root.querySelectorAll("i[data-icon]").forEach((i) => { i.innerHTML = icon(i.dataset.icon); });
  paintIcons();

  // ------------------------------------------------------------------ storage
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch { /* blocked */ } },
    del(k) { try { localStorage.removeItem(k); } catch { /* blocked */ } },
  };
  let token = store.get("jarvis-token") || "";
  const speakToggle = $("speakToggle"), wakeToggle = $("wakeToggle");
  speakToggle.checked = store.get("jarvis-speak") !== "0";
  speakToggle.onchange = () => store.set("jarvis-speak", speakToggle.checked ? "1" : "0");

  // ------------------------------------------------------------------ api
  async function api(path, body) {
    const res = await fetch(path, {
      method: body === undefined ? "GET" : "POST",
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (res.status === 401) { askToken(); throw new Error("locked"); }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `Error ${res.status}`);
    return data;
  }
  function askToken() { if (!$("login").open) $("login").showModal(); }
  $("loginForm").addEventListener("submit", () => {
    token = $("token").value.trim();
    store.set("jarvis-token", token);
    boot();
  });

  function toast(text, err) {
    const t = el("div", `toast${err ? " err" : ""}`, text);
    $("toasts").appendChild(t);
    setTimeout(() => t.remove(), 6000);
  }

  // ------------------------------------------------------------------ state
  let status = {}, dash = null;
  const events = [];          // notifications received this session (newest first)
  let unread = 0;
  const voiceOut = "speechSynthesis" in window;
  const core = { mode: "idle" };

  const STATE_TEXT = { idle: "STANDING BY", listening: "LISTENING …", thinking: "THINKING …", speaking: "SPEAKING …" };
  function setMode(mode, note) {
    core.mode = mode || "idle";
    $("coreState").textContent = STATE_TEXT[core.mode];
    const vs = $("voiceState");
    vs.textContent = core.mode === "idle" ? (wakeOn() ? "Wake word on" : "Standby") : core.mode[0].toUpperCase() + core.mode.slice(1);
    vs.classList.toggle("on", core.mode !== "idle" || wakeOn());
    const busyVoice = core.mode === "listening" || core.mode === "speaking";
    $("talkLabel").textContent = busyVoice ? "Stop" : "Talk";
    $("talkIcon").dataset.icon = busyVoice ? "stop" : "mic";
    paintIcons($("talkBtn"));
    $("talkBtn").classList.toggle("on", busyVoice);
    $("drawerMic").classList.toggle("on", core.mode === "listening");
    if (note !== undefined) live(note);
    else if (core.mode === "idle") live("");
  }

  // ------------------------------------------------------------------ conversation
  const chatLog = $("chatLog"), boxLog = $("boxLog");
  // A status line above the chat box input: "Listening…", what you're saying, "Thinking…".
  const live = (text) => { $("capUser").textContent = text || ""; };
  function addMsg(kind, text, mirror = true) {
    if (mirror) {  // the dashboard chat box shows the recent conversation
      boxLog.appendChild(el("div", `msg ${kind}`, text));
      while (boxLog.children.length > 40) boxLog.firstChild.remove();
      boxLog.scrollTop = boxLog.scrollHeight;
    }
    const m = el("div", `msg ${kind}`, text);
    chatLog.appendChild(m);
    $("drawerBody").scrollTop = 1e9;
    return m;
  }
  function approvalButtons(action, container) {
    const row = el("div", "row");
    row.dataset.action = action.id;
    for (const [label, ok, cls] of [["Approve", true, "ok"], ["Deny", false, "no"]]) {
      const b = el("button", `btn-sm ${cls}`, label);
      b.onclick = () => decide(action.id, ok);
      row.appendChild(b);
    }
    container.appendChild(row);
  }
  function showApprovals(actions) {
    const caps = $("capActions");
    caps.innerHTML = "";
    for (const a of actions || []) {
      approvalButtons(a, addMsg("system", `Approval needed: ${a.summary}`, false));
      const box = el("div", "approval");
      box.appendChild(el("span", "", a.summary));
      approvalButtons(a, box);
      caps.appendChild(box);
    }
  }

  async function handleReply(data, userText) {
    addMsg("jarvis", data.reply);
    live("");
    showApprovals(data.actions);
    refresh();
    await speak(data.reply);
  }

  let busy = false;
  async function send(text) {
    text = (text || "").trim();
    if (!text) return;
    addMsg("user", text);
    busy = true;
    setMode("thinking", "Jarvis is thinking…");
    try {
      await handleReply(await api("/api/chat", { text }), text);
    } catch (e) {
      if (e.message !== "locked") { addMsg("system", e.message); toast(e.message, true); live(""); }
    } finally {
      busy = false;
      if (core.mode === "thinking") setMode("idle");
    }
  }

  async function decide(id, approve) {
    document.querySelectorAll(`[data-action="${id}"]`).forEach((n) => (n.closest(".approval") || n).remove());
    setMode("thinking", approve ? "Working on it…" : "Cancelling…");
    try {
      await handleReply(await api(`/api/actions/${id}`, { approve }));
    } catch (e) {
      toast(e.message, true);
    } finally {
      if (core.mode === "thinking") setMode("idle");
    }
  }

  $("askForm").addEventListener("submit", (e) => { e.preventDefault(); const v = $("ask").value; $("ask").value = ""; send(v); });
  $("boxForm").addEventListener("submit", (e) => { e.preventDefault(); const v = $("boxInput").value; $("boxInput").value = ""; send(v); });
  $("drawerForm").addEventListener("submit", (e) => { e.preventDefault(); const v = $("drawerInput").value; $("drawerInput").value = ""; send(v); });

  // ------------------------------------------------------------------ drawer: conversation, lists, notifications
  const TITLES = { chat: "CONVERSATIONS", todos: "TASKS", reminders: "REMINDERS", facts: "MEMORY", notes: "NOTES",
                   contacts: "CONTACTS", calls: "PHONE CALLS", tools: "TOOLS & SKILLS", alerts: "NOTIFICATIONS" };
  function selectNav(name) {
    document.querySelectorAll("#nav button").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  }
  function openDrawer(title, showChat) {
    $("drawerTitle").textContent = title;
    chatLog.hidden = !showChat;
    $("itemList").hidden = showChat;
    $("drawerForm").hidden = !showChat;
    $("drawer").classList.add("open");
    $("drawer").setAttribute("aria-hidden", "false");
    $("scrim").hidden = false;
  }
  async function openView(name) {
    selectNav(name);
    if (name === "dashboard") return closeDrawer();
    openDrawer(TITLES[name] || name.toUpperCase(), name === "chat");
    if (name === "chat") { setTimeout(() => $("drawerInput").focus(), 200); return; }
    if (name === "alerts") return renderAlerts();
    const list = $("itemList");
    list.innerHTML = '<li class="empty">Loading…</li>';
    try {
      const rows = await api(`/api/list/${name}`);
      list.innerHTML = "";
      if (!rows.length) list.appendChild(el("li", "empty", "Nothing here yet. Just ask Jarvis."));
      for (const r of rows) {
        const li = el("li", r.done ? "done" : "");
        li.appendChild(el("strong", "", r.title || "(untitled)"));
        if (r.detail) li.appendChild(el("small", "", r.detail));
        list.appendChild(li);
      }
    } catch (e) { list.innerHTML = ""; list.appendChild(el("li", "empty", e.message)); }
  }
  function renderAlerts() {
    const list = $("itemList");
    list.innerHTML = "";
    for (const a of (dash && dash.actions) || []) {
      const li = el("li");
      li.append(el("strong", "", a.summary), el("small", "", "Waiting for your approval"));
      approvalButtons(a, li);
      list.appendChild(li);
    }
    const seen = new Set();
    for (const e of [...events, ...((dash && dash.feed) || [])]) {
      const key = `${e.kind}|${e.message}|${e.at}`;
      if (seen.has(key)) continue;
      seen.add(key);
      const li = el("li");
      li.append(el("strong", "", e.message), el("small", "", e.at ? timeAgo(e.at) : ""));
      list.appendChild(li);
    }
    if (!list.children.length) list.appendChild(el("li", "empty", "No notifications yet."));
  }
  function closeDrawer() {
    $("drawer").classList.remove("open");
    $("drawer").setAttribute("aria-hidden", "true");
    $("scrim").hidden = true;
    selectNav("dashboard");
  }
  $("nav").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) openView(b.dataset.view); });
  document.querySelectorAll("[data-open]").forEach((b) => (b.onclick = () => openView(b.dataset.open)));
  $("drawerClose").onclick = closeDrawer;
  $("scrim").onclick = closeDrawer;
  $("bellBtn").onclick = () => {
    unread = 0; $("bellCount").textContent = "";
    if ("Notification" in window && Notification.permission === "default") Notification.requestPermission();
    openView("alerts");
  };
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") { closeDrawer(); $("menu").hidden = true; } });

  // ------------------------------------------------------------------ settings menu
  $("gearBtn").onclick = (e) => { e.stopPropagation(); $("menu").hidden = !$("menu").hidden; };
  document.addEventListener("click", (e) => { if (!$("menu").contains(e.target)) $("menu").hidden = true; });
  $("newChat").onclick = async () => {
    await api("/api/reset", {});
    chatLog.innerHTML = "";
    boxLog.innerHTML = "";
    live("");
    addMsg("system", "New conversation started.");
    refresh();
  };
  $("lockBtn").onclick = () => { store.del("jarvis-token"); token = ""; location.reload(); };

  // ------------------------------------------------------------------ voice out
  let voice = null;
  function pickVoice() {
    const vs = speechSynthesis.getVoices();
    const prefs = ["Daniel", "Google UK English Male", "Microsoft Ryan", "Arthur", "Microsoft George", "George"];
    voice = prefs.map((p) => vs.find((v) => v.name.includes(p))).find(Boolean)
      || vs.find((v) => v.lang === "en-GB") || vs.find((v) => v.lang.startsWith("en")) || null;
  }
  if (voiceOut) { pickVoice(); speechSynthesis.onvoiceschanged = pickVoice; }

  const clean = (text) => text.replace(/[*_#`>]/g, "").replace(/https?:\/\/\S+/g, "the link");
  let utteranceId = 0;

  // Replies are spoken by ElevenLabs when the server has it set up, otherwise by the
  // browser's own voice. ElevenLabs audio plays through Web Audio: once the page has
  // been tapped, Safari allows it to play later (after the reply arrives).
  let audioCtx = null, playing = null, elevenFailed = false;
  function getAudioCtx() {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!audioCtx && Ctx) audioCtx = new Ctx();
    return audioCtx;
  }
  for (const evt of ["pointerdown", "keydown", "touchend"]) {
    window.addEventListener(evt, () => {
      const c = getAudioCtx();
      if (c && c.state === "suspended") c.resume().catch(() => {});
    }, { passive: true });
  }
  function stopAudio() {
    if (playing) { playing.onended = null; try { playing.stop(); } catch { /* not started */ } playing = null; }
    if (voiceOut) speechSynthesis.cancel();
  }

  function finish(id, resolve) {
    if (id === utteranceId) { setMode("idle"); resumeListening(); }
    resolve();
  }

  function speakBrowser(text, id) {
    return new Promise((resolve) => {
      if (!voiceOut) return finish(id, resolve);
      const u = new SpeechSynthesisUtterance(clean(text));
      if (voice) u.voice = voice;
      u.rate = 1.03;
      // cancel() fires the previous utterance's end event; only the newest one counts.
      u.onend = u.onerror = () => finish(id, resolve);
      speechSynthesis.speak(u);
    });
  }

  async function speakEleven(text, id) {
    const res = await fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify({ text: clean(text) }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || `Error ${res.status}`);
    }
    const bytes = await res.arrayBuffer();
    if (id !== utteranceId) return;  // something newer started meanwhile
    const c = getAudioCtx();
    if (!c) throw new Error("This browser can't play the audio.");
    if (c.state === "suspended") await c.resume().catch(() => {});
    const buffer = await c.decodeAudioData(bytes);
    if (id !== utteranceId) return;
    await new Promise((resolve) => {
      playing = c.createBufferSource();
      playing.buffer = buffer;
      playing.connect(c.destination);
      playing.onended = () => { playing = null; finish(id, resolve); };
      playing.start();
    });
  }

  async function speak(text) {
    if (!speakToggle.checked || !text) return;
    pauseListening();
    const id = ++utteranceId;
    stopAudio();
    setMode("speaking");
    if (status.tts === "elevenlabs" && !elevenFailed) {
      try { return await speakEleven(text, id); } catch (e) {
        elevenFailed = true;  // don't keep retrying; the built-in voice takes over
        toast(`${e.message} Using the built-in voice instead.`, true);
        if (id !== utteranceId) return;
      }
    }
    return speakBrowser(text, id);
  }
  function stopSpeaking() { utteranceId++; stopAudio(); setMode("idle"); resumeListening(); }

  // ------------------------------------------------------------------ voice in
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let rec = null, listening = false, awaitingCommand = false, paused = false, awaitTimer = null, failures = 0;
  const wakeOn = () => wakeToggle.checked;

  function startRecognition(continuous) {
    if (!Recognition) { toast(window.JARVIS_NO_VOICE_MSG || "Voice input needs Chrome, Edge or Safari. You can still type.", true); return; }
    stopRecognition();
    rec = new Recognition();
    rec.lang = navigator.language || "en-US";
    rec.continuous = continuous;
    rec.interimResults = true;
    rec.onresult = (e) => {
      failures = 0;
      const result = e.results[e.results.length - 1];
      const said = result[0].transcript.trim();
      if (!result.isFinal) { if (!continuous || awaitingCommand) live(`“${said}…”`); return; }
      if (!continuous) { send(said); return; }
      onWakeResult(said);
    };
    rec.onend = () => {
      listening = false;
      const delay = Math.min(300 * 2 ** failures, 30000);  // back off if the mic keeps failing
      if (wakeOn() && !paused) setTimeout(() => { if (wakeOn() && !paused && !listening) startRecognition(true); }, delay);
      else if (core.mode === "listening") setMode("idle");
    };
    rec.onerror = (e) => {
      if (e.error === "not-allowed" || e.error === "service-not-allowed") {
        setWake(false);
        toast("Microphone access was blocked. Allow it in your browser (Jarvis must be on https or localhost).", true);
      } else if (e.error === "audio-capture") {
        setWake(false);
        toast("No microphone found.", true);
      } else if (e.error !== "no-speech" && e.error !== "aborted") {
        failures++;
        if (failures >= 6) { setWake(false); toast(`Voice recognition keeps failing (${e.error}). Wake word turned off.`, true); }
      }
    };
    try { rec.start(); } catch { return; }
    listening = true;
    if (continuous) setMode("idle"); else setMode("listening", "Listening…");
  }
  function stopRecognition() {
    if (rec) { rec.onend = null; try { rec.abort(); } catch { /* already stopped */ } }
    rec = null; listening = false;
  }
  function onWakeResult(said) {
    if (awaitingCommand) { awaitingCommand = false; clearTimeout(awaitTimer); send(said); return; }
    const m = said.match(/\bjarvis\b[,.!?]?\s*(.*)$/i);
    if (!m) return;
    if (m[1]) { send(m[1]); return; }
    awaitingCommand = true;
    clearTimeout(awaitTimer);
    awaitTimer = setTimeout(() => { awaitingCommand = false; }, 10000);  // forget after 10s
    speak("Yes?");
  }
  function pauseListening() { paused = true; if (listening) stopRecognition(); }
  function resumeListening() { paused = false; if (wakeOn() && !listening) startRecognition(true); }

  function talkOrStop() {
    if (core.mode === "speaking") return stopSpeaking();
    if (core.mode === "listening") { stopRecognition(); setMode("idle"); return; }
    utteranceId++;
    stopAudio();
    startRecognition(false);
  }
  function setWake(on) {
    wakeToggle.checked = on;
    if (on) startRecognition(true); else stopRecognition();
    setMode(core.mode === "listening" ? "idle" : core.mode);
  }
  $("talkBtn").onclick = talkOrStop;
  $("coreBtn").onclick = talkOrStop;
  $("operatorBtn").onclick = talkOrStop;
  $("drawerMic").onclick = talkOrStop;
  wakeToggle.onchange = () => setWake(wakeToggle.checked);

  // ------------------------------------------------------------------ tasks
  function renderTasks() {
    const list = $("tasks");
    const tasks = dash.tasks || [];
    list.innerHTML = "";
    const open = tasks.filter((t) => !t.done).length;
    $("taskCount").textContent = `${open} open · ${tasks.length - open} done`;
    if (!tasks.length) list.appendChild(el("li", "empty", 'No tasks yet. Add one below, or say "Jarvis, add a task…"'));
    for (const t of tasks) {
      const pr = ["high", "med", "low"].includes(t.priority) ? t.priority : "med";
      const li = el("li", `task pr-${pr}${t.done ? " done" : ""}`);
      const check = el("button", "check");
      check.setAttribute("aria-label", t.done ? `Mark "${t.task}" not done` : `Mark "${t.task}" done`);
      check.onclick = () => toggleTask(t);
      li.append(check, el("div", "task-title", t.task), el("span", `badge ${pr}`, pr[0].toUpperCase() + pr.slice(1)));
      if (t.due) li.appendChild(el("div", "task-sub", `due ${t.due}`));
      list.appendChild(li);
    }
  }
  async function toggleTask(t) {
    t.done = t.done ? 0 : 1;
    renderTasks();
    try { await api(`/api/todos/${t.id}`, { done: !!t.done }); } catch (e) { toast(e.message, true); }
    refresh();
  }
  $("taskForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const task = $("taskInput").value.trim();
    if (!task) return;
    $("taskInput").value = "";
    try { await api("/api/todos", { task, priority: $("taskPriority").value }); } catch (err) { toast(err.message, true); }
    refresh();
  });
  $("taskPriority").addEventListener("change", () => $("taskInput").focus());

  // ------------------------------------------------------------------ mission timeline
  function renderTimeline() {
    const ol = $("timeline");
    ol.innerHTML = "";
    const items = dash.timeline || [];
    if (!items.length) {
      ol.appendChild(el("li", "empty", 'Nothing scheduled today. Try "Remind me at 6pm to call Mom."'));
      return;
    }
    // Show up to five: the last finished one, then what's next.
    const nextIdx = items.findIndex((r) => r.status === "pending");
    const start = Math.max(0, Math.min((nextIdx < 0 ? items.length : nextIdx) - 1, items.length - 5));
    items.slice(start, start + 5).forEach((r) => {
      const isDone = r.status !== "pending";
      const isNow = !isDone && r === items[nextIdx];
      const li = el("li", isDone ? "done" : isNow ? "now" : "");
      li.append(el("div", "tl-when", `${r.time_local} · ${isDone ? "Done" : isNow ? inTime(r.due_at) : "Queued"}`),
                el("div", "tl-what", r.message));
      li.title = r.message;
      ol.appendChild(li);
    });
  }
  function inTime(iso) {
    const m = Math.round((new Date(iso).getTime() - Date.now()) / 60000);
    if (m <= 1) return "Now";
    if (m < 60) return `In ${m}m`;
    const h = Math.floor(m / 60);
    return `In ${h}h ${m % 60}m`;
  }
  function timeAgo(iso) {
    const s = (Date.now() - new Date(iso).getTime()) / 1000;
    if (s < 60) return "just now";
    if (s < 3600) return `${Math.floor(s / 60)}m ago`;
    if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
    return `${Math.floor(s / 86400)}d ago`;
  }

  // ------------------------------------------------------------------ system monitor
  const METERS = [["cpu", "CPU", "%"], ["ram", "Memory", "%"], ["disk", "Disk", "%"], ["latency", "Latency", " ms"]];
  const history = Object.fromEntries(METERS.map(([k]) => [k, []]));
  (function buildMeters() {
    const box = $("meters");
    for (const [key, label] of METERS) {
      const row = el("div", "meter");
      const c = el("canvas");
      c.id = `spark-${key}`;
      const v = el("strong", "", "—");
      v.id = `val-${key}`;
      row.append(el("span", "", label), c, v);
      box.appendChild(row);
    }
  })();
  function drawSpark(key, max) {
    const c = $(`spark-${key}`);
    const pts = history[key];
    const w = c.clientWidth, h = c.clientHeight, dpr = Math.min(window.devicePixelRatio || 1, 2);
    if (!w) return;
    c.width = w * dpr; c.height = h * dpr;
    const g = c.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.fillStyle = "rgba(58,166,255,0.08)";
    g.fillRect(0, 0, w, h);
    if (pts.length < 2) return;
    const top = Math.max(max, ...pts) || 1;
    const x = (i) => (i / (pts.length - 1)) * w;
    const y = (v) => h - 3 - (v / top) * (h - 6);
    g.beginPath();
    pts.forEach((v, i) => (i ? g.lineTo(x(i), y(v)) : g.moveTo(0, y(v))));
    g.strokeStyle = "#3aa6ff";
    g.lineWidth = 1.4;
    g.stroke();
    g.lineTo(w, h); g.lineTo(0, h); g.closePath();
    g.fillStyle = "rgba(58,166,255,0.14)";
    g.fill();
  }
  async function pollSystem() {
    try {
      const t0 = performance.now();
      const sys = await api("/api/system");
      const values = { ...sys, latency: Math.round(performance.now() - t0) };
      for (const [key, , unit] of METERS) {
        if (values[key] === undefined) continue;
        history[key].push(Number(values[key]));
        if (history[key].length > 40) history[key].shift();
        $(`val-${key}`).textContent = `${Math.round(values[key])}${unit}`;
        drawSpark(key, key === "latency" ? 300 : 100);
      }
      $("stLatency").textContent = `${values.latency} ms`;
    } catch { /* offline: the pill says so */ }
  }

  // ------------------------------------------------------------------ header + stats
  function renderStats() {
    const c = (dash && dash.counts) || {};
    $("stModel").textContent = status.model || "—";
    $("stMemory").textContent = `${c.facts || 0} facts`;
    $("stSkills").textContent = `${c.tools || 0} ready`;
    $("stLink").textContent = navigator.onLine ? "online" : "offline";
    if (status.started_at) {
      const s = Math.max(0, (Date.now() - new Date(status.started_at).getTime()) / 1000);
      const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
      $("stUptime").textContent = d ? `${d}d ${String(h).padStart(2, "0")}h` : `${h}h ${String(m).padStart(2, "0")}m`;
    }
    const set = (id, n) => { $(id).textContent = n ? String(n) : ""; };
    set("navTurns", c.turns); set("navTodos", c.todos); set("navReminders", c.reminders); set("navFacts", c.facts);
    set("navNotes", c.notes); set("navContacts", c.contacts); set("navCalls", c.calls); set("navTools", c.tools);
  }
  function setSystem(ok) {
    const pill = $("sysPill");
    pill.classList.remove("bad", "warn");
    let text = "All systems nominal";
    if (!ok) { text = "Reconnecting…"; pill.classList.add("warn"); }
    else if (status.ai_ready === false) { text = `No ${status.ai_name || "AI"} API key`; pill.classList.add("bad"); }
    else if (dash && dash.actions && dash.actions.length) { text = `${dash.actions.length} awaiting approval`; pill.classList.add("warn"); }
    $("sysStatus").textContent = text;
  }

  function renderAll() {
    if (!dash) return;
    renderTasks(); renderTimeline(); renderStats(); setSystem(true);
    if (!$("capActions").children.length && dash.actions.length) showApprovals(dash.actions);
  }
  async function refresh() {
    try { dash = await api("/api/dashboard"); renderAll(); } catch { /* shown elsewhere */ }
  }

  // ------------------------------------------------------------------ live events
  let source = null;
  function listenForEvents() {
    if (source) source.close();
    source = new EventSource(`/api/events${token ? `?token=${encodeURIComponent(token)}` : ""}`);
    source.onmessage = (e) => {
      const ev = JSON.parse(e.data);
      ev.at = ev.at || new Date().toISOString();
      events.unshift(ev);
      unread++; $("bellCount").textContent = String(unread);
      addMsg("system", `🔔 ${ev.message}`);
      toast(`🔔 ${ev.message}`);
      if ("Notification" in window && Notification.permission === "granted" && document.hidden) new Notification("Jarvis", { body: ev.message });
      if (!busy) speak(ev.message);
      refresh();
    };
    source.onopen = () => setSystem(true);
    source.onerror = () => setSystem(false);
  }

  // ------------------------------------------------------------------ clock
  function tick() {
    const now = new Date();
    $("date").textContent = now.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" });
    $("time").textContent = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }
  tick();
  setInterval(tick, 1000);

  // ------------------------------------------------------------------ AI core ring
  (function ring() {
    const canvas = $("ring");
    const g = canvas.getContext("2d");
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let w = 0, h = 0, t = 0, energy = 0;
    const BARS = 120;
    const noise = Array.from({ length: BARS }, (_, i) => 0.35 + 0.65 * Math.abs(Math.sin(i * 12.9898) * 0.5 + Math.sin(i * 0.37) * 0.5));
    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const r = canvas.getBoundingClientRect();
      w = r.width; h = r.height;
      canvas.width = w * dpr; canvas.height = h * dpr;
      g.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    new ResizeObserver(resize).observe(canvas);
    resize();
    const circle = (r, color, width, dash) => {
      g.beginPath(); g.setLineDash(dash || []); g.arc(0, 0, r, 0, Math.PI * 2);
      g.strokeStyle = color; g.lineWidth = width; g.stroke(); g.setLineDash([]);
    };
    const arc = (r, a0, a1, color, width) => {
      g.beginPath(); g.arc(0, 0, r, a0, a1); g.strokeStyle = color; g.lineWidth = width; g.lineCap = "round"; g.stroke();
    };
    function frame() {
      const target = { idle: 0.15, listening: 0.7, thinking: 0.45, speaking: 1 }[core.mode] || 0.15;
      energy += (target - energy) * 0.06;
      if (!reduce) t += 0.004 + energy * 0.012;
      g.clearRect(0, 0, w, h);
      const R = Math.min(w, h) * 0.44;
      g.save();
      g.translate(w / 2, h / 2);

      const glow = g.createRadialGradient(0, 0, R * 0.05, 0, 0, R * 0.75);
      glow.addColorStop(0, `rgba(40,130,220,${0.18 + energy * 0.12})`);
      glow.addColorStop(1, "rgba(40,130,220,0)");
      g.fillStyle = glow;
      g.beginPath(); g.arc(0, 0, R * 0.75, 0, Math.PI * 2); g.fill();

      // outer scale
      for (let i = 0; i < 180; i++) {
        const a = (i / 180) * Math.PI * 2;
        const long = i % 15 === 0;
        const r0 = R, r1 = R * (long ? 1.04 : 1.018);
        g.beginPath(); g.moveTo(Math.cos(a) * r0, Math.sin(a) * r0); g.lineTo(Math.cos(a) * r1, Math.sin(a) * r1);
        g.strokeStyle = `rgba(120,170,210,${long ? 0.35 : 0.14})`; g.lineWidth = 1; g.stroke();
      }
      circle(R * 1.09, "rgba(120,170,210,0.12)", 1, [1, 5]);

      // sweeping arcs
      g.save(); g.rotate(t * 0.9);
      arc(R * 0.9, Math.PI * 0.95, Math.PI * 1.55, "rgba(58,166,255,0.95)", 2.2);
      arc(R * 0.9, Math.PI * 1.95, Math.PI * 2.35, "rgba(58,166,255,0.9)", 2.2);
      g.restore();
      g.save(); g.rotate(-t * 0.6);
      arc(R * 0.82, Math.PI * 1.35, Math.PI * 1.75, "rgba(58,166,255,0.55)", 1.4);
      arc(R * 0.82, Math.PI * 0.2, Math.PI * 0.45, "rgba(58,166,255,0.45)", 1.4);
      g.restore();
      circle(R * 0.78, "rgba(58,166,255,0.35)", 1);

      // orbiting dots
      for (let k = 0; k < 4; k++) {
        const a = t * (1.1 + k * 0.25) + k * 1.7, r = R * (0.72 + (k % 2) * 0.2);
        g.beginPath(); g.arc(Math.cos(a) * r, Math.sin(a) * r, 2.6, 0, Math.PI * 2);
        g.fillStyle = "#7cc8ff"; g.shadowColor = "#3aa6ff"; g.shadowBlur = 10; g.fill(); g.shadowBlur = 0;
      }

      // voice ring: radial bars that swell with activity
      for (let i = 0; i < BARS; i++) {
        const a = (i / BARS) * Math.PI * 2 - Math.PI / 2;
        const wave = 0.5 + 0.5 * Math.sin(t * 9 + i * 0.55) * Math.sin(t * 4.3 + i * 0.21);
        const len = R * (0.047 + energy * 0.09 * noise[i] * wave);
        const r0 = R * 0.6;
        g.beginPath();
        g.moveTo(Math.cos(a) * r0, Math.sin(a) * r0);
        g.lineTo(Math.cos(a) * (r0 + len), Math.sin(a) * (r0 + len));
        g.strokeStyle = `rgba(58,166,255,${0.45 + energy * 0.45})`; g.lineWidth = 1.6; g.stroke();
      }
      circle(R * 0.56, "rgba(58,166,255,0.28)", 1);
      circle(R * 0.5, "rgba(58,166,255,0.22)", 1, [2, 6]);
      circle(R * 0.38, "rgba(58,166,255,0.12)", 1);
      g.restore();
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  })();

  // ------------------------------------------------------------------ boot
  let timers = false;
  async function boot() {
    try {
      status = await api("/api/status");
      $("opName").textContent = status.name || "Operator";
      $("opSub").textContent = status.mode === "demo" ? "Demo · in this page" : `${status.ai_name || "AI"} · ${status.mode} mode`;
      $("monitorWhere").textContent = status.mode === "demo" ? "Simulated" : status.computer_control ? "This computer" : "Server";
      if (!chatLog.children.length) {
        const hello = `Good to see you, ${status.name}. How can I help?`;
        addMsg("jarvis", hello);
      }
      await refresh();
      pollSystem();
      listenForEvents();
      if (!timers) {
        timers = true;
        setInterval(refresh, 20000);
        setInterval(pollSystem, 3000);
        setInterval(renderStats, 30000);
        window.addEventListener("online", renderStats);
        window.addEventListener("offline", renderStats);
      }
    } catch (e) {
      if (e.message !== "locked") { setSystem(false); toast(`Can't reach Jarvis: ${e.message}`, true); }
    }
  }
  setMode("idle");
  boot();
})();
