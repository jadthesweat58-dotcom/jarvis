// JARVIS Command Center: dashboard, conversation, voice in/out, approvals,
// live notifications and the animated AI core.
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
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/>',
  };
  const icon = (name) => `<svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ICONS.grid}</svg>`;
  const iconEl = (name) => { const i = el("i"); i.dataset.icon = name; i.innerHTML = icon(name); return i; };
  const paintIcons = (root = document) => root.querySelectorAll("i[data-icon]").forEach((i) => { i.innerHTML = icon(i.dataset.icon); });
  paintIcons();

  // ------------------------------------------------------------------ waveforms
  function makeWave(node, bars) {
    node.innerHTML = "";
    for (let k = 0; k < bars; k++) {
      const s = el("span");
      s.style.setProperty("--h", `${25 + Math.round(Math.abs(Math.sin(k * 1.7)) * 70)}%`);
      s.style.animationDelay = `${(k % 9) * -0.17}s`;
      node.appendChild(s);
    }
  }
  makeWave($("sideWave"), 44);
  makeWave($("talkWaveL"), 10);
  makeWave($("talkWaveR"), 10);
  const waves = [$("sideWave"), $("talkWaveL"), $("talkWaveR")];

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
  let lastLatency = null;
  async function api(path, body) {
    const t0 = performance.now();
    const res = await fetch(path, {
      method: body === undefined ? "GET" : "POST",
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    lastLatency = performance.now() - t0;
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
  let status = {}, dash = null, weather = null;
  const localFeed = [];   // events received this session (newest first)
  let unread = 0;
  const voiceIn = !!(window.SpeechRecognition || window.webkitSpeechRecognition);
  const voiceOut = "speechSynthesis" in window;

  function setMode(mode, text) {
    core.mode = mode || "idle";
    const active = mode === "listening" || mode === "speaking";
    waves.forEach((w) => w.classList.toggle("active", active || mode === "thinking"));
    $("voiceState").textContent = text || (wakeOn() ? 'Listening for "Jarvis"…' : "Standing by");
    $("talkSub").textContent = mode === "listening" ? "I am listening…" : mode === "thinking" ? "Thinking…" : mode === "speaking" ? "Speaking…" : "Tap to speak";
    $("coreState").textContent = `v1.0 · ${(mode && mode !== "idle" ? mode : "online").toUpperCase()}`;
    $("micOrb").classList.toggle("on", mode === "listening");
    $("talkBtn").classList.toggle("on", mode === "listening");
    $("drawerMic").classList.toggle("on", mode === "listening");
  }

  // ------------------------------------------------------------------ conversation
  const chatLog = $("chatLog");
  function addMsg(kind, text) {
    const m = el("div", `msg ${kind}`, text);
    chatLog.appendChild(m);
    chatLog.scrollTop = chatLog.scrollHeight;
    $("drawer").querySelector(".drawer-body").scrollTop = 1e9;
    return m;
  }
  function approvalButtons(action, container) {
    const row = el("div", "row");
    row.dataset.action = action.id;
    for (const [label, ok, cls] of [["Approve", true, "ok"], ["Deny", false, "no"]]) {
      const b = el("button", `btn-sm ${cls}`, label);
      b.onclick = () => { row.remove(); decide(action.id, ok); };
      row.appendChild(b);
    }
    container.appendChild(row);
    return row;
  }

  async function handleReply(data, userText) {
    addMsg("jarvis", data.reply);
    $("capJarvis").textContent = data.reply;
    if (userText) $("capUser").textContent = `“${userText}”`;
    const caps = $("capActions");
    caps.innerHTML = "";
    for (const a of data.actions || []) {
      approvalButtons(a, addMsg("system", `Approval needed: ${a.summary}`));
      const wrap = el("div");
      wrap.appendChild(el("small", "muted", a.summary));
      approvalButtons(a, wrap);
      caps.appendChild(wrap);
    }
    refresh();
    await speak(data.reply);
  }

  let busy = false;
  async function send(text) {
    text = (text || "").trim();
    if (!text) return;
    addMsg("user", text);
    $("capUser").textContent = `“${text}”`;
    $("capJarvis").textContent = "…";
    busy = true;
    setMode("thinking", "Thinking…");
    try {
      await handleReply(await api("/api/chat", { text }), text);
    } catch (e) {
      if (e.message !== "locked") { addMsg("system", e.message); toast(e.message, true); $("capJarvis").textContent = ""; }
    } finally {
      busy = false;
      if (core.mode === "thinking") setMode("idle");
    }
  }

  async function decide(id, approve) {
    document.querySelectorAll(`[data-action="${id}"]`).forEach((n) => n.remove());
    setMode("thinking", approve ? "Working on it…" : "Cancelling…");
    $("capActions").innerHTML = "";
    try {
      await handleReply(await api(`/api/actions/${id}`, { approve }));
    } catch (e) {
      toast(e.message, true);
    } finally {
      if (core.mode === "thinking") setMode("idle");
    }
  }

  $("askForm").addEventListener("submit", (e) => { e.preventDefault(); const v = $("ask").value; $("ask").value = ""; send(v); });
  $("drawerForm").addEventListener("submit", (e) => { e.preventDefault(); const v = $("drawerInput").value; $("drawerInput").value = ""; send(v); });

  // ------------------------------------------------------------------ drawer (conversation + lists)
  const TITLES = { chat: "CONVERSATION", todos: "TASKS", reminders: "REMINDERS", facts: "MEMORY", notes: "NOTES", contacts: "CONTACTS", calls: "PHONE CALLS", tools: "TOOLS & SKILLS" };
  let view = "dashboard";
  async function openView(name) {
    view = name;
    document.querySelectorAll("#nav button").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
    if (name === "dashboard") return closeDrawer();
    $("drawerTitle").textContent = TITLES[name] || name.toUpperCase();
    const isChat = name === "chat";
    chatLog.hidden = !isChat;
    $("itemList").hidden = isChat;
    $("drawer").classList.add("open");
    $("drawer").setAttribute("aria-hidden", "false");
    $("scrim").hidden = false;
    if (isChat) { setTimeout(() => $("drawerInput").focus(), 200); return; }
    const list = $("itemList");
    list.innerHTML = '<li class="empty">Loading…</li>';
    try {
      const rows = await api(`/api/list/${name}`);
      list.innerHTML = "";
      if (!rows.length) list.innerHTML = '<li class="empty">Nothing here yet — just ask Jarvis.</li>';
      for (const r of rows) {
        const li = el("li", r.done ? "done" : "");
        li.appendChild(el("strong", "", r.title || "(untitled)"));
        if (r.detail) li.appendChild(el("small", "", r.detail));
        list.appendChild(li);
      }
    } catch (e) { list.innerHTML = ""; list.appendChild(el("li", "empty", e.message)); }
  }
  function closeDrawer() {
    $("drawer").classList.remove("open");
    $("drawer").setAttribute("aria-hidden", "true");
    $("scrim").hidden = true;
    view = "dashboard";
    document.querySelectorAll("#nav button").forEach((b) => b.classList.toggle("active", b.dataset.view === "dashboard"));
  }
  $("nav").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) openView(b.dataset.view); });
  document.querySelectorAll("[data-open]").forEach((b) => (b.onclick = () => openView(b.dataset.open)));
  $("drawerClose").onclick = closeDrawer;
  $("scrim").onclick = closeDrawer;
  $("chatBtn").onclick = () => openView("chat");
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") { closeDrawer(); $("menu").hidden = true; } });

  // ------------------------------------------------------------------ settings menu
  $("gearBtn").onclick = (e) => { e.stopPropagation(); $("menu").hidden = !$("menu").hidden; };
  document.addEventListener("click", (e) => { if (!$("menu").contains(e.target)) $("menu").hidden = true; });
  $("newChat").onclick = async () => {
    await api("/api/reset", {});
    chatLog.innerHTML = "";
    $("capUser").textContent = ""; $("capJarvis").textContent = "New conversation started.";
    addMsg("system", "New conversation started.");
    refresh();
  };
  $("lockBtn").onclick = () => { store.del("jarvis-token"); token = ""; location.reload(); };
  $("bellBtn").onclick = () => {
    unread = 0; $("bellCount").textContent = "";
    if ("Notification" in window && Notification.permission === "default") Notification.requestPermission();
    document.querySelector(".feed").scrollIntoView({ behavior: "smooth", block: "center" });
  };

  // ------------------------------------------------------------------ voice out
  let voice = null;
  function pickVoice() {
    const vs = speechSynthesis.getVoices();
    const prefs = ["Daniel", "Google UK English Male", "Microsoft Ryan", "Arthur", "Microsoft George", "George"];
    voice = prefs.map((p) => vs.find((v) => v.name.includes(p))).find(Boolean)
      || vs.find((v) => v.lang === "en-GB") || vs.find((v) => v.lang.startsWith("en")) || null;
  }
  if (voiceOut) { pickVoice(); speechSynthesis.onvoiceschanged = pickVoice; }

  function speak(text) {
    return new Promise((resolve) => {
      if (!speakToggle.checked || !voiceOut || !text) return resolve();
      pauseListening();
      speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text.replace(/[*_#`>]/g, "").replace(/https?:\/\/\S+/g, "the link"));
      if (voice) u.voice = voice;
      u.rate = 1.03;
      setMode("speaking", "Speaking…");
      u.onend = u.onerror = () => { setMode("idle"); resumeListening(); resolve(); };
      speechSynthesis.speak(u);
    });
  }

  // ------------------------------------------------------------------ voice in
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let rec = null, listening = false, awaitingCommand = false, paused = false;
  const wakeOn = () => wakeToggle.checked;

  function startRecognition(continuous) {
    if (!Recognition) { toast("Voice input needs Chrome, Edge or Safari. You can still type.", true); return; }
    stopRecognition();
    rec = new Recognition();
    rec.lang = navigator.language || "en-US";
    rec.continuous = continuous;
    rec.interimResults = false;
    rec.onresult = (e) => {
      const said = e.results[e.results.length - 1][0].transcript.trim();
      if (!continuous) { send(said); return; }
      onWakeResult(said);
    };
    rec.onend = () => {
      listening = false;
      if (wakeOn() && !paused) setTimeout(() => { if (wakeOn() && !paused && !listening) startRecognition(true); }, 300);
      else if (core.mode === "listening") setMode("idle");
    };
    rec.onerror = (e) => {
      if (e.error === "not-allowed" || e.error === "service-not-allowed") {
        setWake(false);
        toast("Microphone access was blocked. Allow it in your browser (Jarvis must be on https or localhost).", true);
      }
    };
    try { rec.start(); } catch { return; }
    listening = true;
    setMode("listening", continuous ? 'Listening for "Jarvis"…' : "Listening…");
  }
  function stopRecognition() {
    if (rec) { rec.onend = null; try { rec.abort(); } catch { /* already stopped */ } }
    rec = null; listening = false;
  }
  function onWakeResult(said) {
    if (awaitingCommand) { awaitingCommand = false; send(said); return; }
    const m = said.match(/\bjarvis\b[,.!?]?\s*(.*)$/i);
    if (!m) return;
    if (m[1]) { send(m[1]); return; }
    awaitingCommand = true;
    speak("Yes?");
  }
  function pauseListening() { paused = true; if (listening) stopRecognition(); }
  function resumeListening() { paused = false; if (wakeOn() && !listening) startRecognition(true); }

  function pushToTalk() {
    if (listening && !wakeOn()) { stopRecognition(); setMode("idle"); return; }
    if (voiceOut) speechSynthesis.cancel();
    startRecognition(false);
  }
  function setWake(on) {
    wakeToggle.checked = on;
    const btn = $("wakeBtn");
    btn.classList.toggle("on", on);
    btn.querySelector("span").textContent = `Wake Word: ${on ? "On" : "Off"}`;
    if (on) startRecognition(true); else { stopRecognition(); setMode("idle"); }
  }
  $("micOrb").onclick = pushToTalk;
  $("talkBtn").onclick = pushToTalk;
  $("drawerMic").onclick = pushToTalk;
  $("wakeBtn").onclick = () => setWake(!wakeOn());
  wakeToggle.onchange = () => setWake(wakeToggle.checked);

  // ------------------------------------------------------------------ quick commands
  const BRIEFING = "Give me my executive briefing: today's weather, my upcoming reminders, open to-dos and anything I should know. Keep it brief.";
  const QUICK = [
    ["mic", "Start Voice Chat", () => pushToTalk()],
    ["play", "Executive Briefing", () => send(BRIEFING)],
    ["sun", "Check the Weather", () => send("What's the weather like today?")],
    ["check", "What's on my To-Do List?", () => send("What's on my to-do list?")],
    ["plus", "New Conversation", () => $("newChat").click()],
  ];
  function renderQuick() {
    const q = $("quick");
    q.innerHTML = "";
    const items = [...QUICK];
    if (status.phone) items.splice(4, 0, ["phone", "Call Me Now", () => send("Call me on my phone now so we can talk.")]);
    for (const [ic, label, fn] of items) {
      const b = el("button");
      b.append(iconEl(ic), label);
      b.onclick = fn;
      q.appendChild(b);
    }
  }
  $("briefBtn").onclick = () => send(BRIEFING);

  // ------------------------------------------------------------------ dashboard rendering
  const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
  function ovItem(ic, color, title, sub) {
    const li = el("li");
    const circle = el("span", "ov-icon");
    circle.style.color = color;
    circle.appendChild(iconEl(ic));
    const text = el("div");
    text.appendChild(el("strong", "", title));
    const s = el("small", "", sub);
    s.style.color = color;
    text.appendChild(s);
    li.append(circle, text);
    return li;
  }

  function renderOverview() {
    const c = dash.counts || {};
    const ul = $("overview");
    ul.innerHTML = "";
    const G = "var(--green)", Y = "var(--yellow)", M = "var(--muted)", C = "var(--glow)", P = "var(--purple)", O = "var(--orange)";
    ul.append(
      ovItem("brain", status.claude ? G : "var(--red)", "AI Core", status.claude ? `Active · ${status.model}` : "No API key"),
      ovItem("database", C, "Memory", `${c.facts || 0} stored · ${c.notes || 0} notes`),
      ovItem("mic", voiceIn ? G : Y, "Voice", voiceIn ? (wakeOn() ? "Wake word on" : "Online") : "Speech off (use Chrome)"),
      ovItem("phone", status.phone ? G : M, "Phone", status.phone ? (status.two_way_calls ? "Two-way ready" : "Connected") : "Not set up"),
      ovItem("tool", P, "Skills", `${c.tools || 0} tools ready`),
      ovItem("shield", O, "System", status.computer_control ? "Local · computer control" : "Cloud · safe mode"),
    );
  }

  function timeAgo(iso) {
    const s = (Date.now() - new Date(iso).getTime()) / 1000;
    if (s < 60) return "just now";
    if (s < 3600) return `${Math.floor(s / 60)}m ago`;
    if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
    return `${Math.floor(s / 86400)}d ago`;
  }
  function inTime(iso) {
    const m = Math.round((new Date(iso).getTime() - Date.now()) / 60000);
    if (m <= 0) return "Now";
    if (m < 60) return `In ${m}m`;
    const h = Math.floor(m / 60);
    return h < 24 ? `In ${h}h ${m % 60}m` : `In ${Math.floor(h / 24)}d`;
  }

  function renderFeed() {
    const ul = $("feed");
    ul.innerHTML = "";
    const items = [];
    for (const a of dash.actions || []) items.push({ cls: "act", tag: "ACTION", ic: "alert", title: a.summary, sub: "Waiting for your approval", action: a });
    const seen = new Set();
    for (const e of [...localFeed, ...(dash.feed || [])]) {
      const key = `${e.kind}|${e.message}|${e.at || ""}`;
      if (seen.has(key)) continue;
      seen.add(key);
      const map = { reminder: ["info", "INFO", "bell"], call: ["tip", "CALL", "phone"], error: ["err", "ALERT", "alert"] }[e.kind] || ["info", "INFO", "zap"];
      items.push({ cls: map[0], tag: map[1], ic: map[2], title: e.message, sub: e.at ? timeAgo(e.at) : "" });
    }
    for (const r of (dash.reminders || []).slice(0, 2)) {
      const mins = (new Date(r.due_at).getTime() - Date.now()) / 60000;
      if (mins < 90) items.push({ cls: "warn", tag: "SOON", ic: "clock", title: r.message, sub: `${inTime(r.due_at)} · ${r.due_local}` });
    }
    if ((dash.todos || []).length) items.push({ cls: "tip", tag: "TIP", ic: "check", title: `${plural(dash.todos.length, "open task")} on your list`, sub: "Ask Jarvis to go through them", open: "todos" });
    if (!items.length) items.push({ cls: "tip", tag: "TIP", ic: "zap", title: 'Try: "Remind me in 10 minutes to stretch"', sub: "Reminders, calls and alerts appear here" });
    for (const it of items.slice(0, 8)) {
      const li = el("li", it.cls);
      li.appendChild(iconEl(it.ic));
      const t = el("div", "feed-text");
      t.append(el("strong", "", it.title), el("small", "", it.sub));
      li.appendChild(t);
      if (it.action) {
        const ok = el("button", "btn-sm ok", "✓"); ok.title = "Approve"; ok.onclick = () => decide(it.action.id, true);
        const no = el("button", "btn-sm no", "✕"); no.title = "Deny"; no.onclick = () => decide(it.action.id, false);
        li.append(ok, no);
      } else if (it.open) {
        const b = el("button", "btn-sm", "View"); b.onclick = () => openView(it.open); li.appendChild(b);
      } else {
        li.appendChild(el("span", `tag ${it.cls}`, it.tag));
      }
      ul.appendChild(li);
    }
  }

  function renderSkills() {
    const c = dash.counts || {};
    const skills = [
      ["globe", "var(--glow)", "Research", "active", "Web search"],
      ["database", "var(--purple)", "Memory", "active", `${c.facts || 0} facts`],
      ["calendar", "var(--glow)", "Reminders", c.reminders ? "active" : "standby", c.reminders ? `${c.reminders} upcoming` : "Standby"],
      ["phone", "var(--orange)", "Phone", status.phone ? "active" : "off", status.phone ? "Ready" : "Not set up"],
      ["monitor", "var(--yellow)", "Computer", status.computer_control ? "active" : "off", status.computer_control ? "Ready" : "Cloud mode"],
      ["sun", "var(--green)", "Weather", status.home_city ? "active" : "standby", status.home_city ? status.home_city : "Ask anywhere"],
    ];
    const grid = $("skills");
    grid.innerHTML = "";
    for (const [ic, color, name, st, sub] of skills) {
      const card = el("button", "skill");
      card.title = `Ask Jarvis about ${name.toLowerCase()}`;
      const box = el("span", "skill-icon");
      box.style.color = color;
      box.appendChild(iconEl(ic));
      const small = el("small", `st-${st}`);
      small.appendChild(el("span", "st-text", `● ${sub}`));
      const w = el("span", `wave${st === "active" ? " active" : ""}`);
      makeWave(w, 40);
      w.querySelectorAll("span").forEach((b) => { b.style.background = color; b.style.boxShadow = `0 0 4px ${color}`; });
      card.append(box, el("strong", "", name), small, w);
      card.onclick = () => openView({ Research: "tools", Memory: "facts", Reminders: "reminders", Phone: "calls", Computer: "tools", Weather: "tools" }[name]);
      grid.appendChild(card);
    }
  }

  function renderTimeline() {
    const ul = $("timeline");
    ul.innerHTML = "";
    const rows = (dash.reminders || []).slice(0, 5);
    if (!rows.length) { ul.appendChild(el("li", "empty", "No upcoming reminders.")); return; }
    for (const r of rows) {
      const soon = new Date(r.due_at).getTime() - Date.now() < 3600e3;
      const li = el("li", soon ? "soon" : "");
      const d = new Date(r.due_at);
      const t = el("time");
      t.append(el("b", "", d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })),
        el("span", "", d.toLocaleDateString([], { weekday: "short" })));
      li.append(t, el("div", "tl-title", r.message), el("div", "tl-in", inTime(r.due_at)));
      ul.appendChild(li);
    }
  }

  function gauge(node, label, value) {
    const v = Math.max(0, Math.min(100, Number(value) || 0));
    const r = 38, circ = 2 * Math.PI * r;
    if (!node.firstChild) {
      node.innerHTML = `<svg viewBox="0 0 92 92"><circle class="track" cx="46" cy="46" r="${r}" fill="none" stroke-width="7"/>` +
        `<circle class="val" cx="46" cy="46" r="${r}" fill="none" stroke-width="7" stroke-linecap="round" stroke-dasharray="${circ}" stroke-dashoffset="${circ}"/></svg>` +
        `<div class="lbl"><small>${label}</small><strong>0%</strong></div>`;
    }
    const val = node.querySelector(".val");
    val.style.stroke = v > 85 ? "var(--red)" : v > 65 ? "var(--yellow)" : "var(--glow)";
    requestAnimationFrame(() => { val.style.strokeDashoffset = circ * (1 - v / 100); });
    node.querySelector("strong").textContent = value === undefined ? "—" : `${Math.round(v)}%`;
  }

  let constellationN = -1;
  function renderMemory() {
    const c = dash.counts || {};
    $("mFacts").textContent = (c.facts || 0).toLocaleString();
    $("mTurns").textContent = (c.turns || 0).toLocaleString();
    $("mTools").textContent = (c.tool_calls || 0).toLocaleString();
    const n = Math.max(7, Math.min(22, 7 + (c.facts || 0)));
    if (n === constellationN) return;
    constellationN = n;
    let seed = 7;
    const rnd = () => ((seed = (seed * 9301 + 49297) % 233280) / 233280);
    const pts = Array.from({ length: n }, (_, k) => [12 + (k / (n - 1)) * 196 + (rnd() - 0.5) * 18, 18 + rnd() * 84]);
    let svg = "";
    pts.forEach((p, k) => {
      if (k) svg += `<line x1="${pts[k - 1][0]}" y1="${pts[k - 1][1]}" x2="${p[0]}" y2="${p[1]}"/>`;
      if (k > 2 && rnd() > 0.6) svg += `<line x1="${pts[k - 3][0]}" y1="${pts[k - 3][1]}" x2="${p[0]}" y2="${p[1]}"/>`;
    });
    pts.forEach((p) => { svg += `<circle cx="${p[0]}" cy="${p[1]}" r="${1.4 + rnd() * 1.6}"/>`; });
    $("constellation").innerHTML = svg;
  }

  function renderConnections() {
    const G = "var(--green)", M = "var(--muted)", Y = "var(--yellow)";
    const perm = "Notification" in window ? Notification.permission : "unsupported";
    const items = [
      ["brain", "Claude", status.claude, status.claude ? "Connected" : "Add API key"],
      ["globe", "Web Search", status.claude, status.claude ? "Connected" : "Needs Claude"],
      ["cloud", "Weather", !!(weather && weather.available), weather && weather.available ? "Open-Meteo" : status.home_city ? "Unreachable" : "Set HOME_CITY"],
      ["phone", "Twilio Phone", status.phone, status.phone ? "Connected" : "Not linked"],
      ["message", "Two-way Calls", status.two_way_calls, status.two_way_calls ? "Ready" : "Needs public URL"],
      ["monitor", "Computer", status.computer_control, status.computer_control ? "Enabled" : "Cloud mode"],
      ["mic", "Voice Input", voiceIn, voiceIn ? "Browser ready" : "Use Chrome/Edge"],
      ["speaker", "Voice Output", voiceOut, voiceOut ? (voice ? voice.name.split(" ")[0] : "Ready") : "Unsupported"],
      ["bell", "Notifications", perm === "granted", perm === "granted" ? "Allowed" : perm === "denied" ? "Blocked" : "Tap bell to allow"],
    ];
    const grid = $("connections");
    grid.innerHTML = "";
    let ok = 0;
    for (const [ic, name, on, sub] of items) {
      if (on) ok++;
      const color = on ? G : sub.startsWith("Tap") ? Y : M;
      const d = el("div", "conn");
      const circle = el("span", "ov-icon");
      circle.style.color = on ? "var(--glow)" : M;
      circle.appendChild(iconEl(ic));
      const t = el("div");
      const s = el("small", "", sub);
      s.style.color = color;
      t.append(el("strong", "", name), s);
      d.append(circle, t);
      grid.appendChild(d);
    }
    $("connCount").textContent = `${ok} Connected`;
  }

  function renderBottom() {
    $("bLocation").textContent = (weather && weather.place) || status.home_city || status.timezone || "—";
    $("bWeather").textContent = weather && weather.available
      ? `${Math.round(weather.temperature)}${weather.unit} ${weather.summary}`
      : status.home_city ? "Unavailable" : "Set HOME_CITY";
    const online = navigator.onLine;
    const q = lastLatency == null ? "" : lastLatency < 250 ? "Excellent" : lastLatency < 800 ? "Good" : "Slow";
    $("bNetwork").textContent = online ? q || "Online" : "Offline";
  }

  function renderNav() {
    const c = dash.counts || {};
    const set = (id, n) => { $(id).textContent = n ? String(n) : ""; };
    set("navTurns", c.turns); set("navTodos", c.todos); set("navReminders", c.reminders); set("navFacts", c.facts);
    set("navNotes", c.notes); set("navContacts", c.contacts); set("navCalls", c.calls); set("navTools", c.tools);
  }

  function renderAll() {
    if (!dash) return;
    renderOverview(); renderFeed(); renderSkills(); renderTimeline(); renderMemory(); renderConnections(); renderBottom(); renderNav();
    const sys = dash.system || {};
    gauge($("gCpu"), "CPU", sys.cpu); gauge($("gRam"), "RAM", sys.ram); gauge($("gDisk"), "Disk", sys.disk);
    $("monitorHost").textContent = status.computer_control ? "this computer" : "server";
  }

  async function refresh() {
    try { dash = await api("/api/dashboard"); renderAll(); } catch { /* shown elsewhere */ }
  }
  async function refreshWeather() {
    try { weather = await api("/api/weather"); renderConnections(); renderBottom(); } catch { /* ignore */ }
  }

  // ------------------------------------------------------------------ live events
  let events = null;
  function listenForEvents() {
    if (events) events.close();
    events = new EventSource(`/api/events${token ? `?token=${encodeURIComponent(token)}` : ""}`);
    events.onmessage = (e) => {
      const ev = { ...JSON.parse(e.data), at: new Date().toISOString() };
      localFeed.unshift(ev);
      unread++; $("bellCount").textContent = String(unread);
      addMsg("system", `🔔 ${ev.message}`);
      toast(`🔔 ${ev.message}`);
      if ("Notification" in window && Notification.permission === "granted" && document.hidden) new Notification("Jarvis", { body: ev.message });
      if (!busy) speak(ev.message);
      refresh();
    };
    events.onopen = () => setSystem(true);
    events.onerror = () => setSystem(false);
  }
  function setSystem(ok) {
    const s = $("sysStatus");
    s.classList.toggle("bad", !ok);
    s.innerHTML = `<i class="dot"></i>${ok ? (status.claude ? "OPTIMAL" : "NO API KEY") : "RECONNECTING"}`;
    if (ok && !status.claude) s.classList.add("bad");
  }

  // ------------------------------------------------------------------ clock
  function tick() {
    const now = new Date();
    $("date").textContent = now.toLocaleDateString([], { weekday: "long", day: "numeric", month: "long", year: "numeric" });
    $("time").textContent = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }
  tick();
  setInterval(tick, 1000);

  // ------------------------------------------------------------------ AI core globe
  const core = { mode: "idle" };
  (function globe() {
    const canvas = $("globe");
    const ctx = canvas.getContext("2d");
    const N = 700, pts = [];
    const golden = Math.PI * (3 - Math.sqrt(5));
    for (let k = 0; k < N; k++) {
      const y = 1 - (k / (N - 1)) * 2, r = Math.sqrt(1 - y * y), th = golden * k;
      pts.push([Math.cos(th) * r, y, Math.sin(th) * r]);
    }
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let w = 0, h = 0, dpr = 1, rot = 0, pulse = 0;
    function resize() {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      const rect = canvas.getBoundingClientRect();
      w = rect.width; h = rect.height;
      canvas.width = w * dpr; canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    new ResizeObserver(resize).observe(canvas);
    resize();
    function ellipse(cx, cy, rx, ry, rotA, alpha, width) {
      ctx.beginPath();
      ctx.ellipse(cx, cy, rx, ry, rotA, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(25,211,255,${alpha})`;
      ctx.lineWidth = width;
      ctx.stroke();
    }
    function frame(t) {
      const speed = { idle: 0.0022, listening: 0.004, thinking: 0.012, speaking: 0.005 }[core.mode] || 0.0022;
      if (!reduce) rot += speed;
      pulse = core.mode === "speaking" ? 1 + Math.sin(t / 90) * 0.035 : core.mode === "listening" ? 1 + Math.sin(t / 260) * 0.02 : 1;
      ctx.clearRect(0, 0, w, h);
      const cx = w / 2, cy = h / 2 - 8, R = Math.min(w * 0.42, h * 0.4) * pulse;
      // glow
      const g = ctx.createRadialGradient(cx, cy, R * 0.1, cx, cy, R * 1.5);
      g.addColorStop(0, core.mode === "thinking" ? "rgba(120,220,255,0.28)" : "rgba(25,180,255,0.22)");
      g.addColorStop(0.55, "rgba(25,140,255,0.08)");
      g.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, w, h);
      // orbits
      ellipse(cx, cy, R * 1.55, R * 0.34, -0.12, 0.28, 1);
      ellipse(cx, cy, R * 1.35, R * 0.52, 0.35, 0.16, 1);
      ellipse(cx, cy, R * 1.05, R * 1.05, 0, 0.12, 1);
      for (let k = 0; k < 3; k++) {
        const a = rot * (3 + k) + k * 2.1, rx = R * [1.55, 1.35, 1.05][k], ry = R * [0.34, 0.52, 1.05][k], ra = [-0.12, 0.35, 0][k];
        const x = Math.cos(a) * rx, y = Math.sin(a) * ry;
        const px = cx + x * Math.cos(ra) - y * Math.sin(ra), py = cy + x * Math.sin(ra) + y * Math.cos(ra);
        ctx.beginPath(); ctx.arc(px, py, 2.6, 0, Math.PI * 2);
        ctx.fillStyle = "#bff6ff"; ctx.shadowColor = "#19d3ff"; ctx.shadowBlur = 12; ctx.fill(); ctx.shadowBlur = 0;
      }
      // sphere points
      const cosR = Math.cos(rot), sinR = Math.sin(rot), tilt = 0.35, cosT = Math.cos(tilt), sinT = Math.sin(tilt);
      for (const [x0, y0, z0] of pts) {
        const x = x0 * cosR + z0 * sinR, z = -x0 * sinR + z0 * cosR;
        const y = y0 * cosT - z * sinT, z2 = y0 * sinT + z * cosT;
        const depth = (z2 + 1) / 2;
        ctx.globalAlpha = 0.12 + depth * 0.85;
        ctx.fillStyle = depth > 0.8 ? "#d9fbff" : "#19d3ff";
        const s = 0.6 + depth * 1.3;
        ctx.fillRect(cx + x * R - s / 2, cy + y * R - s / 2, s, s);
      }
      ctx.globalAlpha = 1;
      // latitude rings
      for (let k = -2; k <= 2; k++) {
        const yy = k * 0.33, rr = Math.sqrt(1 - yy * yy);
        ellipse(cx, cy + yy * R * cosT, rr * R, rr * R * sinT, 0, 0.1, 1);
      }
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  })();

  // ------------------------------------------------------------------ boot
  let timers = false;
  async function boot() {
    try {
      status = await api("/api/status");
      $("opName").textContent = status.name;
      if (!chatLog.children.length) {
        const hello = `Good to see you, ${status.name}. How can I help?`;
        addMsg("jarvis", hello);
        $("capJarvis").textContent = hello;
      }
      setSystem(true);
      renderQuick();
      await refresh();
      refreshWeather();
      listenForEvents();
      if (!timers) {
        timers = true;
        setInterval(refresh, 20000);
        setInterval(refreshWeather, 600000);
        window.addEventListener("online", renderBottom);
        window.addEventListener("offline", renderBottom);
      }
    } catch (e) {
      if (e.message !== "locked") { setSystem(false); toast(`Can't reach Jarvis: ${e.message}`, true); }
    }
  }
  setMode("idle");
  boot();
})();
