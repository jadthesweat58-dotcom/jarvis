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
    eye: '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/>',
    library: '<path d="M4 4h4v16H4zM10 4h4v16h-4z"/><path d="m16.5 5.2 3.8-1 3.2 15.6-3.9.9z"/>',
    repeat: '<path d="M17 2l4 4-4 4"/><path d="M3 11V9a3 3 0 0 1 3-3h15M7 22l-4-4 4-4"/><path d="M21 13v2a3 3 0 0 1-3 3H3"/>',
    trend: '<path d="m3 17 6-6 4 4 8-8"/><path d="M14 7h7v7"/>',
    clip: '<path d="m21 11-8.6 8.6a5.5 5.5 0 0 1-7.8-7.8l8.6-8.6a3.7 3.7 0 0 1 5.2 5.2l-8.6 8.6a1.8 1.8 0 0 1-2.6-2.6l7.9-7.9"/>',
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

  // Pictures Jarvis made: fetched with the access token, shown in both chat logs.
  async function showImages(ids) {
    for (const id of ids || []) {
      try {
        const res = await fetch(`/api/images/${id}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
        if (!res.ok) throw new Error(`Error ${res.status}`);
        const url = URL.createObjectURL(await res.blob());
        for (const log of [boxLog, chatLog]) {
          const m = el("div", "msg jarvis");
          const img = el("img");
          img.src = url; img.alt = `Picture #${id} made by Jarvis`;
          img.onclick = () => window.open(url, "_blank", "noopener");
          m.appendChild(img);
          log.appendChild(m);
        }
        boxLog.scrollTop = boxLog.scrollHeight;
      } catch (e) { toast(`Couldn't show picture #${id}: ${e.message}`, true); }
    }
  }

  async function handleReply(data, userText) {
    addMsg("jarvis", data.reply);
    showImages(data.images);
    live("");
    showApprovals(data.actions);
    refresh();
    setTimeout(pollUsage, 4000);  // after the voice has been fetched too
    await speak(data.reply);
  }

  let busy = false;
  // ------------------------------------------------------------------ screen sharing
  // While sharing, every message carries a snapshot of the screen so Jarvis can see it.
  let screenStream = null;
  const canShareScreen = !!(navigator.mediaDevices && navigator.mediaDevices.getDisplayMedia) && !window.JARVIS_NO_SCREEN;
  if (!canShareScreen) $("screenBtn").hidden = true;
  async function toggleScreen() {
    if (screenStream) return stopScreen();
    try {
      screenStream = await navigator.mediaDevices.getDisplayMedia({ video: { frameRate: 2 }, audio: false });
    } catch (e) {
      if (e.name !== "NotAllowedError") toast(`Couldn't share the screen: ${e.message}`, true);
      return;
    }
    const video = $("screenVideo");
    video.srcObject = screenStream;
    video.play().catch(() => {});
    screenStream.getVideoTracks()[0].addEventListener("ended", stopScreen);  // browser's own Stop button
    $("screenBtn").classList.add("on");
    $("screenBtn").setAttribute("aria-pressed", "true");
    $("screenChip").hidden = false;
    toast("Jarvis will see your screen each time you send a message. Click the eye again to stop.");
  }
  function stopScreen() {
    if (screenStream) screenStream.getTracks().forEach((t) => t.stop());
    screenStream = null;
    $("screenVideo").srcObject = null;
    $("screenBtn").classList.remove("on");
    $("screenBtn").setAttribute("aria-pressed", "false");
    $("screenChip").hidden = true;
  }
  function screenSnapshot() {
    const video = $("screenVideo");
    if (!screenStream || !video.videoWidth) return null;
    const scale = Math.min(1, 1600 / Math.max(video.videoWidth, video.videoHeight));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(video.videoWidth * scale);
    canvas.height = Math.round(video.videoHeight * scale);
    canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/jpeg", 0.8);
  }
  $("screenBtn").onclick = toggleScreen;

  // ------------------------------------------------------------------ attach a file
  // PDFs, Word documents, pictures and text files: Jarvis reads them with your next message.
  const MAX_FILE = 10 * 1024 * 1024;
  let pendingFile = null;
  function clearFile() {
    pendingFile = null; $("fileChip").hidden = true; $("fileInput").value = "";
    $("boxInput").placeholder = "Message Jarvis…";
  }
  function attachFile(f) {
    if (!f) return;
    if (f.size > MAX_FILE) { toast("That file is too large (10 MB max).", true); return; }
    const reader = new FileReader();
    reader.onload = () => {
      pendingFile = { name: f.name || "pasted-image.png", data: String(reader.result) };
      $("fileName").textContent = pendingFile.name;
      $("fileChip").hidden = false;
      live("");
      $("boxInput").placeholder = "Ask about the file, or just press Send…";
      $("boxInput").focus();
    };
    reader.onerror = () => toast("Couldn't read that file.", true);
    reader.readAsDataURL(f);
  }
  $("attachBtn").onclick = () => $("fileInput").click();
  $("fileInput").onchange = () => attachFile($("fileInput").files[0]);
  $("fileClear").onclick = clearFile;
  const chatbox = document.querySelector(".chatbox");
  chatbox.addEventListener("dragover", (e) => { if ([...e.dataTransfer.types].includes("Files")) { e.preventDefault(); chatbox.classList.add("dragging"); } });
  chatbox.addEventListener("dragleave", (e) => { if (!chatbox.contains(e.relatedTarget)) chatbox.classList.remove("dragging"); });
  chatbox.addEventListener("drop", (e) => {
    chatbox.classList.remove("dragging");
    if (!e.dataTransfer.files.length) return;
    e.preventDefault();
    attachFile(e.dataTransfer.files[0]);
  });
  $("boxInput").addEventListener("paste", (e) => {
    const f = [...(e.clipboardData ? e.clipboardData.files : [])][0];
    if (f) { e.preventDefault(); attachFile(f); }
  });

  // ------------------------------------------------------------------ daily briefing
  async function playBriefing() {
    const btn = $("briefBtn");
    btn.disabled = true;
    setMode("thinking", "Putting your briefing together…");
    try {
      const { text } = await api("/api/briefing", {});
      addMsg("jarvis", text);
      live("");
      await speak(text);
    } catch (e) {
      if (e.message !== "locked") toast(e.message, true);
    } finally {
      btn.disabled = false;
      if (core.mode === "thinking") setMode("idle");
    }
  }
  $("briefBtn").onclick = playBriefing;

  async function send(text) {
    text = (text || "").trim();
    const file = pendingFile;
    if (!text && !file) return;
    const image = screenSnapshot();
    const body = { text };
    if (image) body.image = image;
    if (file) { body.file = { name: file.name, data: file.data }; clearFile(); }
    addMsg("user", `${text || "Summarize this for me."}${file ? `  📎 ${file.name}` : ""}${image ? "  🖥" : ""}`);
    busy = true;
    setMode("thinking", file ? `Jarvis is reading ${file.name}…` : image ? "Jarvis is looking at your screen…" : "Jarvis is thinking…");
    try {
      await handleReply(await api("/api/chat", body), text);
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
                   library: "LIBRARY", automations: "AUTOMATIONS",
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
    if (name === "automations") return renderAutomations();
    const list = $("itemList");
    list.innerHTML = '<li class="empty">Loading…</li>';
    try {
      const rows = await api(`/api/list/${name}`);
      list.innerHTML = "";
      if (!rows.length) list.appendChild(el("li", "empty", "Nothing here yet. Just ask Jarvis."));
      if (name === "library" && !rows.length) {
        list.innerHTML = "";
        list.appendChild(el("li", "empty", "Files you attach in the chat are saved here, so you can ask about them later."));
      }
      for (const r of rows) {
        const li = el("li", r.done ? "done" : "");
        li.appendChild(el("strong", "", r.title || "(untitled)"));
        if (r.detail) li.appendChild(el("small", "", r.detail));
        if (name === "library") {
          li.appendChild(el("span", "meta", `${Number(r.chars || 0).toLocaleString()} characters · saved ${String(r.created_at || "").slice(0, 10)}`));
          const row = el("div", "row");
          const del = el("button", "btn-sm no", "Remove");
          del.onclick = async () => {
            if (!confirm(`Remove "${r.title}" from the library?`)) return;
            try { await api(`/api/library/${r.id}/delete`, {}); li.remove(); refresh(); } catch (e) { toast(e.message, true); }
          };
          row.appendChild(del);
          li.appendChild(row);
        }
        list.appendChild(li);
      }
    } catch (e) { list.innerHTML = ""; list.appendChild(el("li", "empty", e.message)); }
  }
  async function renderAutomations() {
    const list = $("itemList");
    list.innerHTML = '<li class="empty">Loading…</li>';
    let data;
    try { data = await api("/api/automations"); } catch (e) { list.innerHTML = ""; list.appendChild(el("li", "empty", e.message)); return; }
    list.innerHTML = "";
    const act = async (kind, id, action) => {
      if (action === "delete" && !confirm(`Delete this ${kind}?`)) return;
      try {
        await api(`/api/automations/${kind}/${id}`, { action });
        if (action === "run") toast(kind === "routine" ? "Running it now; the result arrives in a minute or two." : "Checking it now.");
        renderAutomations(); refresh();
      } catch (e) { toast(e.message, true); }
    };
    const buttons = (kind, id, paused) => {
      const row = el("div", "row");
      for (const [label, action, cls] of [[kind === "routine" ? "Run now" : "Check now", "run", "ok"],
                                          [paused ? "Resume" : "Pause", paused ? "resume" : "pause", ""],
                                          ["Delete", "delete", "no"]]) {
        const b = el("button", `btn-sm ${cls}`.trim(), label);
        b.onclick = () => act(kind, id, action);
        row.appendChild(b);
      }
      return row;
    };
    list.appendChild(el("h4", "", "ROUTINES"));
    if (!data.routines.length) list.appendChild(el("li", "empty", 'Try: "Every Friday at 6pm, find fun things to do in Dubai this weekend."'));
    for (const r of data.routines) {
      const li = el("li", r.enabled ? "" : "paused");
      li.append(el("strong", "", `${r.title}${r.enabled ? "" : " (paused)"}`), el("small", "", r.prompt),
                el("span", "meta", `${r.schedule} · next ${r.next_local}${r.last_local ? ` · last ${r.last_local}` : ""}`));
      if (r.last_result) li.appendChild(el("small", "", `Last result: ${r.last_result.slice(0, 400)}`));
      li.appendChild(buttons("routine", r.id, !r.enabled));
      list.appendChild(li);
    }
    list.appendChild(el("h4", "", "WATCHERS"));
    if (!data.watchers.length) list.appendChild(el("li", "empty", 'Try: "Watch this page and tell me when the price is under 500 AED: <link>"'));
    for (const w of data.watchers) {
      const paused = w.status !== "active";
      const li = el("li", paused ? "paused" : "");
      li.append(el("strong", "", w.condition || "Any meaningful change"), el("small", "", w.url),
                el("span", "meta", `${w.status === "done" ? "Done ✓" : paused ? "Paused" : `every ${w.every_hours}h`}${w.last_local ? ` · checked ${w.last_local}` : ""}`));
      if (w.last_note) li.appendChild(el("small", "", w.last_note));
      li.appendChild(buttons("watcher", w.id, paused));
      list.appendChild(li);
    }
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
  if (window.JARVIS_NO_EXPORT) $("exportBtn").hidden = true;
  $("exportBtn").onclick = async () => {
    try {
      const res = await fetch("/api/export", { headers: token ? { Authorization: `Bearer ${token}` } : {} });
      if (!res.ok) throw new Error(`Error ${res.status}`);
      const name = (res.headers.get("content-disposition") || "").match(/filename="([^"]+)"/);
      const a = el("a");
      a.href = URL.createObjectURL(await res.blob());
      a.download = name ? name[1] : "jarvis-memory.json";
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 5000);
    } catch (e) { toast(`Couldn't download your data: ${e.message}`, true); }
  };
  $("telegramBtn").onclick = async () => {
    const box = $("telegramBox");
    try {
      const { code, link } = await api("/api/telegram/link", {});
      box.innerHTML = "";
      const a = el("a", "", "Open Telegram and press Start");
      a.href = link; a.target = "_blank"; a.rel = "noopener";
      box.append(a, el("br"), document.createTextNode("or send the bot: "), el("code", "", `/start ${code}`),
                 el("br"), document.createTextNode("The link works once, for 15 minutes."));
      box.hidden = false;
    } catch (e) { toast(e.message, true); }
  };

  // ------------------------------------------------------------------ install + phone notifications
  // Installing Jarvis (Add to Home Screen) makes it an app; Web Push then delivers
  // reminders and briefings even when Jarvis is closed.
  let swReg = null, pushOn = false, installPrompt = null;
  const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const standalone = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  const pushSupported = () => !!(swReg && "PushManager" in window && "Notification" in window);
  window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); installPrompt = e; $("installBtn").hidden = false; });
  $("installBtn").onclick = async () => {
    if (!installPrompt) return;
    installPrompt.prompt();
    await installPrompt.userChoice.catch(() => {});
    installPrompt = null; $("installBtn").hidden = true;
  };
  const b64ToBytes = (b64) => {
    const raw = atob((b64 + "=".repeat((4 - (b64.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/"));
    return Uint8Array.from(raw, (c) => c.charCodeAt(0));
  };
  function setPushUI(on, note) {
    pushOn = on;
    $("pushToggle").checked = on;
    $("pushTest").hidden = !on;
    $("pushNote").textContent = note || "";
    $("pushNote").hidden = !note;
  }
  async function setupPush() {
    if (window.JARVIS_NO_PUSH || !("serviceWorker" in navigator)) { $("pushRow").hidden = true; return; }
    try { swReg = await navigator.serviceWorker.register("/sw.js"); } catch { $("pushRow").hidden = true; return; }
    if (!pushSupported()) {
      $("pushToggle").disabled = true;
      setPushUI(false, isIOS && !standalone
        ? "On iPhone: tap Share, then Add to Home Screen, and open Jarvis from there to turn notifications on."
        : "This browser can't receive notifications.");
      return;
    }
    const sub = await swReg.pushManager.getSubscription().catch(() => null);
    const on = !!sub && Notification.permission === "granted";
    setPushUI(on);
    if (on) api("/api/push/subscribe", sub.toJSON()).catch(() => {});  // make sure the server still has it
  }
  $("pushToggle").onchange = async () => {
    const want = $("pushToggle").checked;
    try {
      if (want) {
        const perm = await Notification.requestPermission();
        if (perm !== "granted") { setPushUI(false, "Notifications are blocked. Allow them for this site in your browser settings."); return; }
        const { key } = await api("/api/push/key");
        let sub = await swReg.pushManager.getSubscription();
        if (!sub) sub = await swReg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64ToBytes(key) });
        await api("/api/push/subscribe", sub.toJSON());
        setPushUI(true);
        toast("Notifications on: reminders and briefings will reach this device even when Jarvis is closed.");
      } else {
        const sub = await swReg.pushManager.getSubscription();
        if (sub) { await api("/api/push/unsubscribe", { endpoint: sub.endpoint }).catch(() => {}); await sub.unsubscribe(); }
        setPushUI(false);
      }
    } catch (e) {
      setPushUI(false, `Couldn't turn notifications on: ${e.message}`);
    }
  };
  $("pushTest").onclick = async () => {
    try { await api("/api/push/test", {}); toast("Test sent. It should pop up in a moment."); } catch (e) { toast(e.message, true); }
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
    // Show up to five: the last finished one, then what's next. Calendar events
    // (diamonds) sit alongside reminders; all-day events never count as "next".
    const nextIdx = items.findIndex((r) => r.status === "pending" && !r.all_day);
    const start = Math.max(0, Math.min((nextIdx < 0 ? items.length : nextIdx) - 1, items.length - 5));
    items.slice(start, start + 5).forEach((r) => {
      const isEvent = r.kind === "event";
      const isDone = r.status !== "pending";
      const isNow = !isDone && r === items[nextIdx];
      const li = el("li", `${isEvent ? "event " : ""}${isDone ? "done" : isNow ? "now" : ""}`.trim());
      const state = isDone ? (isEvent ? "Ended" : "Done") : isNow ? inTime(r.due_at) : isEvent ? "Event" : "Queued";
      li.append(el("div", "tl-when", `${r.time_local} · ${state}`), el("div", "tl-what", r.message));
      li.title = r.location ? `${r.message} (${r.location})` : r.message;
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

  // ------------------------------------------------------------------ live ticker (HUD)
  const LEAGUE_NAMES = { "eng.1": "Premier League", "esp.1": "LaLiga", "ita.1": "Serie A", "ger.1": "Bundesliga",
                         "fra.1": "Ligue 1", "uefa.champions": "Champions League", "ksa.1": "Saudi Pro League" };
  let hudPrefs = null;
  const money = (n) => (n >= 1000 ? n.toLocaleString([], { maximumFractionDigits: 0 }) : n.toLocaleString([], { maximumFractionDigits: n < 10 ? 4 : 2 }));
  function hudItem(parts) {
    const span = el("span");
    for (const p of parts) span.append(typeof p === "string" ? document.createTextNode(p) : p);
    return span;
  }
  async function pollHud() {
    let d;
    try { d = await api("/api/hud"); } catch { return; }
    hudPrefs = d.settings;
    const items = [];
    for (const q of d.markets || []) {
      const dir = q.change > 0 ? "up" : q.change < 0 ? "down" : "";
      items.push(hudItem([el("span", "tag", q.label.toUpperCase()), el("b", "", `$${money(q.price)}`),
                          el("span", dir, `${q.change > 0 ? "▲" : q.change < 0 ? "▼" : "•"} ${Math.abs(q.change).toFixed(2)}%`)]));
    }
    for (const m of d.football || []) {
      const score = m.state === "pre" ? "v" : `${m.home_score ?? 0}–${m.away_score ?? 0}`;
      const when = m.state === "pre" ? new Date(m.kickoff).toLocaleTimeString([], { weekday: "short", hour: "2-digit", minute: "2-digit" }) : m.detail;
      items.push(hudItem([el("span", "tag", "⚽"), `${m.home} `, el("b", "", score), ` ${m.away} `,
                          el("span", m.state === "in" ? "live" : "", m.state === "in" ? `● ${m.detail}` : when)]));
    }
    for (const n of d.news || []) {
      const a = el("a", "", n.title);
      a.href = n.link; a.target = "_blank"; a.rel = "noopener";
      items.push(hudItem([el("span", "tag", "NEWS"), a, n.source ? ` · ${n.source}` : ""]));
    }
    const box = $("hudItems");
    box.innerHTML = "";
    if (!items.length) { $("hud").hidden = !status.home_city; return; }
    // Two copies side by side make the scroll loop seamlessly.
    for (let copy = 0; copy < 2; copy++) for (const it of items) box.appendChild(copy ? it.cloneNode(true) : it);
    box.querySelectorAll("a").forEach((a, i) => { if (i >= (d.news || []).length) a.tabIndex = -1; });
    box.style.setProperty("--hud-speed", `${Math.max(30, items.length * 7)}s`);
    $("hud").hidden = false;
  }
  async function pollWeather() {
    if (!status.home_city) return;
    try {
      const w = await api("/api/weather");
      if (!w.available) return;
      const chip = $("hudWeather");
      chip.innerHTML = "";
      chip.append(iconEl(/rain|shower|drizzle|thunder/.test(w.summary) ? "cloud" : "sun"),
                  el("span", "", `${w.place.split(",")[0]} ${Math.round(w.temperature)}${w.unit.replace("°C", "°")} · ${w.summary}`));
      chip.hidden = false;
      $("hud").hidden = false;
    } catch { /* optional */ }
  }
  $("hudBtn").onclick = () => {
    const form = $("hudForm");
    form.hidden = !form.hidden;
    if (form.hidden || !hudPrefs) return;
    $("hudTickers").value = hudPrefs.tickers.join(", ");
    $("hudNews").checked = hudPrefs.news;
    const box = $("hudLeagues");
    box.innerHTML = "";
    for (const [code, label] of Object.entries(LEAGUE_NAMES)) {
      const l = el("label");
      const c = el("input"); c.type = "checkbox"; c.value = code; c.checked = hudPrefs.leagues.includes(code);
      l.append(c, document.createTextNode(label));
      box.appendChild(l);
    }
  };
  $("hudForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const tickers = $("hudTickers").value.split(/[,\s]+/).map((t) => t.trim()).filter(Boolean);
    const leagues = [...$("hudLeagues").querySelectorAll("input:checked")].map((c) => c.value);
    try {
      await api("/api/hud", { tickers, leagues, news: $("hudNews").checked });
      $("hudForm").hidden = true;
      toast("Ticker updated.");
      pollHud();
    } catch (err) { toast(err.message, true); }
  });

  const fmtK = (n) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1000 ? `${(n / 1000).toFixed(n >= 1e4 ? 0 : 1)}k` : String(n || 0));
  async function pollUsage() {
    try {
      const u = await api("/api/usage");
      const t = u.today || {}, m = u.month || {};
      const calls = t.ai_calls || 0;
      const pics = t.images || 0;
      $("usageAi").textContent = `${calls} call${calls === 1 ? "" : "s"} · ${fmtK((t.ai_tokens_in || 0) + (t.ai_tokens_out || 0))} tokens`
        + (pics ? ` · ${pics} picture${pics === 1 ? "" : "s"}` : "");
      const voiceRow = status.tts === "elevenlabs";
      $("usageVoiceRow").hidden = !voiceRow;
      $("usageBarWrap").hidden = !(voiceRow && u.tts_quota);
      if (voiceRow) {
        const used = m.tts_chars || 0;
        $("usageVoice").textContent = u.tts_quota ? `${fmtK(used)} / ${fmtK(u.tts_quota)} chars` : `${fmtK(used)} chars`;
        if (u.tts_quota) {
          const pct = Math.min(100, (used / u.tts_quota) * 100);
          $("usageBar").style.width = `${pct}%`;
          $("usageBarWrap").classList.toggle("warn", pct >= 80 && pct < 95);
          $("usageBarWrap").classList.toggle("bad", pct >= 95);
        }
      }
      $("usage").hidden = false;
    } catch { /* not important */ }
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
    set("navLibrary", c.library); set("navAuto", c.automations);
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
      if (ev.kind === "briefing") {  // the morning briefing: show it as Jarvis speaking
        addMsg("jarvis", ev.message);
        toast("🌅 Your morning briefing is here.");
      } else if (ev.kind === "routine" || ev.kind === "watch") {
        addMsg("jarvis", ev.message);
        toast(ev.kind === "routine" ? "🔁 A routine finished." : "🔎 A watcher has news.");
      } else {
        addMsg("system", `🔔 ${ev.message}`);
        toast(`🔔 ${ev.message}`);
      }
      if (!pushOn && "Notification" in window && Notification.permission === "granted" && document.hidden) new Notification("Jarvis", { body: ev.message });
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
      const tg = status.telegram || {};
      $("telegramBtn").hidden = !tg.enabled;
      $("telegramBtn").textContent = tg.linked ? "Telegram linked ✓ (link again)" : "Link Telegram";
      if (!chatLog.children.length) {
        const hello = `Good to see you, ${status.name}. How can I help?`;
        addMsg("jarvis", hello);
      }
      await refresh();
      pollSystem();
      pollUsage();
      pollHud();
      pollWeather();
      listenForEvents();
      if (!timers) {
        timers = true;
        setInterval(pollHud, 60000);
        setInterval(pollWeather, 15 * 60000);
        setupPush();
        setInterval(pollUsage, 60000);
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
