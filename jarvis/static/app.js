// Jarvis browser app: chat, voice in (speech recognition), voice out (speech
// synthesis), approvals, and live notifications from the server.
(() => {
  const $ = (id) => document.getElementById(id);
  const log = $("log"), form = $("form"), input = $("text"), reactor = $("reactor");
  const stateEl = $("state"), statusEl = $("status"), micBtn = $("mic");
  const wakeBox = $("wake"), speakBox = $("speak");

  const store = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch { /* storage blocked */ } },
  };
  let token = store.get("jarvis-token") || "";
  speakBox.checked = store.get("jarvis-speak") !== "0";
  speakBox.onchange = () => store.set("jarvis-speak", speakBox.checked ? "1" : "0");

  // ---------- server calls ----------
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

  function askToken() {
    const dlg = $("login");
    if (!dlg.open) dlg.showModal();
  }
  $("loginForm").addEventListener("submit", () => {
    token = $("token").value.trim();
    store.set("jarvis-token", token);
    boot();
  });

  // ---------- chat log ----------
  function addMsg(kind, text) {
    const div = document.createElement("div");
    div.className = `msg ${kind}`;
    div.textContent = text;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
    return div;
  }

  function addApproval(action) {
    const div = addMsg("system", `Approve? ${action.summary}`);
    const row = document.createElement("div");
    row.className = "approve";
    for (const [label, approve, cls] of [["Approve", true, "ok"], ["Deny", false, "no"]]) {
      const b = document.createElement("button");
      b.textContent = label;
      b.className = cls;
      b.onclick = () => { row.remove(); decide(action.id, approve); };
      row.appendChild(b);
    }
    div.appendChild(row);
  }

  function setState(mode, text) {
    reactor.className = `reactor ${mode || ""}`;
    stateEl.textContent = text || "";
  }

  async function handleReply(data) {
    addMsg("jarvis", data.reply);
    (data.actions || []).forEach(addApproval);
    refreshPanel();
    await speak(data.reply);
  }

  async function send(text) {
    text = text.trim();
    if (!text) return;
    addMsg("user", text);
    setState("thinking", "Thinking…");
    try {
      await handleReply(await api("/api/chat", { text }));
    } catch (e) {
      if (e.message !== "locked") addMsg("system", e.message);
    } finally {
      setState("", wakeBox.checked ? 'Listening for "Jarvis"…' : "Tap the reactor or type below");
    }
  }

  async function decide(id, approve) {
    setState("thinking", approve ? "Working on it…" : "Cancelling…");
    try {
      await handleReply(await api(`/api/actions/${id}`, { approve }));
    } catch (e) {
      addMsg("system", e.message);
    } finally {
      setState("", "");
    }
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value;
    input.value = "";
    send(text);
  });

  $("reset").onclick = async () => {
    await api("/api/reset", {});
    log.innerHTML = "";
    addMsg("system", "New conversation started.");
  };

  // ---------- side panel ----------
  function fill(listId, items, render, empty) {
    const ul = $(listId);
    ul.innerHTML = "";
    if (!items.length) { ul.innerHTML = `<li class="muted">${empty}</li>`; return; }
    for (const item of items) { const li = document.createElement("li"); render(li, item); ul.appendChild(li); }
  }

  async function refreshPanel() {
    try {
      const d = await api("/api/dashboard");
      fill("actions", d.actions, (li, a) => {
        li.textContent = a.summary + " ";
        const ok = document.createElement("button"); ok.textContent = "✓"; ok.className = "ok";
        ok.onclick = () => decide(a.id, true);
        const no = document.createElement("button"); no.textContent = "✕"; no.className = "no";
        no.onclick = () => decide(a.id, false);
        li.append(ok, " ", no);
      }, "Nothing pending");
      fill("reminders", d.reminders, (li, r) => {
        const when = document.createElement("span"); when.className = "when"; when.textContent = r.due_local;
        li.append(when, r.message);
      }, "None");
      fill("todos", d.todos, (li, t) => { li.textContent = "☐ " + t.task; }, "All clear");
      $("facts").textContent = `${d.facts} things remembered about you`;
    } catch { /* ignore */ }
  }

  // ---------- voice out ----------
  let voice = null;
  function pickVoice() {
    const voices = speechSynthesis.getVoices();
    const prefs = ["Daniel", "Google UK English Male", "Microsoft Ryan", "Arthur", "George", "Microsoft George"];
    voice = prefs.map((p) => voices.find((v) => v.name.includes(p))).find(Boolean)
      || voices.find((v) => v.lang === "en-GB") || voices.find((v) => v.lang.startsWith("en")) || null;
  }
  if ("speechSynthesis" in window) { pickVoice(); speechSynthesis.onvoiceschanged = pickVoice; }

  function speak(text) {
    return new Promise((resolve) => {
      if (!speakBox.checked || !("speechSynthesis" in window) || !text) return resolve();
      pauseListening();
      speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text.replace(/[*_#`>]/g, "").replace(/https?:\/\/\S+/g, "the link"));
      if (voice) u.voice = voice;
      u.rate = 1.03;
      setState("speaking", "Speaking…");
      u.onend = u.onerror = () => { setState("", ""); resumeListening(); resolve(); };
      speechSynthesis.speak(u);
    });
  }

  // ---------- voice in ----------
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let rec = null, listening = false, awaitingCommand = false, paused = false;

  if (!Recognition) {
    micBtn.disabled = true; wakeBox.disabled = true;
    micBtn.title = "Voice input needs Chrome, Edge or Safari";
  }

  function startRecognition(continuous) {
    if (!Recognition) return;
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
      micBtn.classList.remove("on");
      if (wakeBox.checked && !paused) setTimeout(() => startRecognition(true), 250);
      else if (reactor.classList.contains("listening")) setState("", "");
    };
    rec.onerror = (e) => {
      if (e.error === "not-allowed") {
        wakeBox.checked = false;
        addMsg("system", "Microphone access was blocked. Allow it in your browser (and use https or localhost).");
      }
    };
    rec.start();
    listening = true;
    micBtn.classList.add("on");
    setState("listening", continuous ? 'Listening for "Jarvis"…' : "Listening…");
  }

  function stopRecognition() {
    if (rec) { rec.onend = null; try { rec.abort(); } catch { /* already stopped */ } }
    rec = null; listening = false; micBtn.classList.remove("on");
  }

  function onWakeResult(said) {
    const m = said.match(/\bjarvis\b[,.!?]?\s*(.*)$/i);
    if (awaitingCommand) { awaitingCommand = false; send(said); return; }
    if (!m) return;
    if (m[1]) { send(m[1]); return; }
    awaitingCommand = true;
    setState("listening", "Yes?");
    speak("Yes?");
  }

  function pauseListening() { paused = true; if (listening) stopRecognition(); }
  function resumeListening() { paused = false; if (wakeBox.checked && !listening) startRecognition(true); }

  function pushToTalk() {
    if (listening && !wakeBox.checked) { stopRecognition(); setState("", ""); return; }
    speechSynthesis && speechSynthesis.cancel();
    startRecognition(false);
  }
  micBtn.onclick = pushToTalk;
  reactor.onclick = pushToTalk;
  wakeBox.onchange = () => {
    if (wakeBox.checked) startRecognition(true);
    else { stopRecognition(); setState("", "Tap the reactor or type below"); }
  };

  // ---------- live notifications (reminders, call results) ----------
  let events = null;
  function listenForEvents() {
    if (events) events.close();
    events = new EventSource(`/api/events${token ? `?token=${encodeURIComponent(token)}` : ""}`);
    events.onmessage = (e) => {
      const ev = JSON.parse(e.data);
      addMsg("system", `🔔 ${ev.message}`);
      if ("Notification" in window && Notification.permission === "granted" && document.hidden) {
        new Notification("Jarvis", { body: ev.message });
      }
      speak(ev.message);
      refreshPanel();
    };
    events.onopen = () => { statusEl.textContent = statusEl.dataset.base || "online"; };
    events.onerror = () => { statusEl.textContent = "reconnecting…"; };
  }

  // ---------- start ----------
  let panelTimer = null;
  async function boot() {
    try {
      const s = await api("/api/status");
      statusEl.textContent = statusEl.dataset.base =
        `online · ${s.mode} mode${s.phone ? " · phone ready" : ""}${s.computer_control ? " · computer control" : ""}`;
      if (!log.children.length) addMsg("jarvis", `Good to see you, ${s.name}. How can I help?`);
      listenForEvents();
      refreshPanel();
      if (!panelTimer) panelTimer = setInterval(refreshPanel, 30000);
      if ("Notification" in window && Notification.permission === "default") Notification.requestPermission();
    } catch (e) {
      if (e.message !== "locked") statusEl.textContent = "offline";
    }
  }
  boot();
})();
