// Jarvis demo backend: runs the real dashboard with no server.
//
// Loaded before app.js. It answers the dashboard's /api/* requests in the page
// (data kept in this browser) and lets Jarvis think with Claude through the
// claude.ai artifact "sample" capability, so no API key is needed. Phone calls
// are simulated; web search, weather and computer control need the full server.
(() => {
  "use strict";

  // ---------------------------------------------------------------- storage
  const KEY = "jarvis-demo-state-v2";
  const now = () => new Date();
  const iso = (d) => d.toISOString();
  const inMinutes = (m) => iso(new Date(Date.now() + m * 60000));

  function seed() {
    return {
      nextId: 100,
      facts: [
        { id: 1, fact: "Prefers short, direct answers", category: "preferences" },
        { id: 2, fact: "Is building a personal AI assistant called Jarvis", category: "work" },
      ],
      notes: [{ id: 3, title: "Jarvis ideas", body: "Morning briefing, call reminders, smart home later." }],
      todos: [
        { id: 4, task: "Add my Gemini API key", due: "", priority: "high", done: 0 },
        { id: 5, task: "Deploy Jarvis to Render", due: "today", priority: "high", done: 0 },
        { id: 8, task: "Set up UptimeRobot monitor", due: "", priority: "med", done: 0 },
        { id: 9, task: "Create Supabase project", due: "", priority: "med", done: 1 },
      ],
      reminders: [
        { id: 10, message: "Morning briefing", due_at: inMinutes(-90), status: "fired" },
        { id: 6, message: "Try asking Jarvis for a briefing", due_at: inMinutes(45), status: "pending" },
        { id: 11, message: "Evening walk", due_at: inMinutes(180), status: "pending" },
      ],
      contacts: [{ id: 7, name: "Mom", phone: "+15551234567", relationship: "mother" }],
      calls: [],
      actions: [],
      history: [],
      toolCalls: 0,
      feed: [],
    };
  }

  let state;
  try { state = JSON.parse(localStorage.getItem(KEY)) || seed(); } catch { state = seed(); }
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch { /* storage blocked */ } };
  const newId = () => ++state.nextId;

  // ---------------------------------------------------------------- Claude
  const samplePromise = window.claude && typeof window.claude.use === "function"
    ? window.claude.use("sample").catch(() => null)
    : Promise.resolve(null);
  let sampleState = window.claude ? "pending" : "absent";  // pending | ready | absent | declined
  samplePromise.then((s) => { if (sampleState === "pending") sampleState = s ? "ready" : "absent"; });

  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  const localTime = (d) => d.toLocaleString([], { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

  const PERSONA = `You are JARVIS, a personal AI assistant, running in DEMO MODE inside a web page.

Personality: calm, capable, quietly witty, with the polished manner of a British butler
(think Tony Stark's JARVIS). Be warm but never gushing. Address the user as "Commander".

Use your tools whenever they help; don't describe what you would do, just do it. Never claim
you did something unless a tool confirmed it.

Style: your replies are often read aloud, so keep them short and conversational (usually
1-3 sentences) unless asked for detail. No markdown, tables, emoji or URLs.

Memory: when the user tells you something lasting about themselves, their people,
preferences or plans, save it with remember_fact without being asked.

Demo limits: in this demo you cannot browse the web, check live weather or control the
computer, and phone calls/texts are simulated. If asked for those, say briefly that the
full Jarvis (deployed with an API key) does it, and help however you can.

Approvals: calling or texting someone needs the user's approval. Just call the tool; the
app shows Approve / Deny buttons. Don't ask for confirmation in text as well.`;

  // ---------------------------------------------------------------- tools
  const byId = (list, id) => list.find((x) => x.id === Number(id));
  const PRI = { high: 0, med: 1, low: 2 };
  const STARTED = iso(new Date(Date.now() - 3 * 3600 * 1000));
  const startOfDay = () => { const d = new Date(); d.setHours(0, 0, 0, 0); return d; };
  const findContact = (who) => {
    const w = String(who || "").trim().toLowerCase();
    if (/^\+\d{7,15}$/.test(w.replace(/[\s()-]/g, ""))) return { name: who, phone: w.replace(/[\s()-]/g, "") };
    return state.contacts.find((c) => c.name.toLowerCase() === w)
      || state.contacts.find((c) => c.name.toLowerCase().includes(w));
  };

  function makeTools(pending) {
    const t = (name, description, properties, required, execute) => ({
      name, description,
      inputSchema: { type: "object", properties, required: required || [] },
      execute: (input) => { state.toolCalls++; const out = execute(input || {}); save(); return out; },
    });
    const str = { type: "string" };
    return [
      t("remember_fact", "Save a lasting fact about the user. Returns a confirmation.", { fact: str, category: str }, ["fact"], (a) => {
        const f = { id: newId(), fact: String(a.fact), category: String(a.category || "general") };
        state.facts.push(f);
        return `Saved fact #${f.id}.`;
      }),
      t("recall_facts", "Search saved facts about the user (empty query lists all).", { query: str }, [], (a) => {
        const q = String(a.query || "").toLowerCase();
        const rows = state.facts.filter((f) => !q || f.fact.toLowerCase().includes(q) || f.category.includes(q));
        return rows.length ? rows.map((f) => `#${f.id} ${f.fact}`).join("\n") : "No matching facts.";
      }),
      t("forget_fact", "Delete a saved fact by id.", { id: { type: "integer" } }, ["id"], (a) => {
        const before = state.facts.length;
        state.facts = state.facts.filter((f) => f.id !== Number(a.id));
        if (before === state.facts.length) throw new Error(`No fact #${a.id}.`);
        return `Forgot fact #${a.id}.`;
      }),
      t("add_note", "Save a note.", { title: str, body: str }, ["title"], (a) => {
        const n = { id: newId(), title: String(a.title), body: String(a.body || "") };
        state.notes.unshift(n);
        return `Saved note #${n.id}.`;
      }),
      t("search_notes", "Find notes by keyword (empty lists recent notes).", { query: str }, [], (a) => {
        const q = String(a.query || "").toLowerCase();
        const rows = state.notes.filter((n) => !q || (n.title + " " + n.body).toLowerCase().includes(q)).slice(0, 10);
        return rows.length ? rows.map((n) => `#${n.id} ${n.title}: ${n.body}`).join("\n") : "No notes found.";
      }),
      t("add_todo", "Add a task to the to-do list.", { task: str, due: str, priority: { type: "string", enum: ["high", "med", "low"] } }, ["task"], (a) => {
        const td = { id: newId(), task: String(a.task), due: String(a.due || ""), priority: ["high", "med", "low"].includes(a.priority) ? a.priority : "med", done: 0 };
        state.todos.push(td);
        return `Added to-do #${td.id}.`;
      }),
      t("list_todos", "Show the open to-do list.", {}, [], () => {
        const rows = state.todos.filter((x) => !x.done);
        return rows.length ? rows.map((x) => `#${x.id} ${x.task}${x.due ? ` (due ${x.due})` : ""}`).join("\n") : "The to-do list is empty.";
      }),
      t("complete_todo", "Mark a to-do as done by id.", { id: { type: "integer" } }, ["id"], (a) => {
        const td = byId(state.todos, a.id);
        if (!td) throw new Error(`No to-do #${a.id}.`);
        td.done = 1;
        return `Marked #${td.id} done.`;
      }),
      t("set_reminder", `Set a reminder or timer; the app alerts the user on screen and out loud. Use in_minutes for relative times, or 'at' as a local ISO date-time (user timezone ${tz}).`,
        { message: str, in_minutes: { type: "number" }, at: str }, ["message"], (a) => {
          let due;
          if (a.in_minutes !== undefined && a.in_minutes !== null) due = new Date(Date.now() + Number(a.in_minutes) * 60000);
          else if (a.at) due = new Date(String(a.at));
          if (!due || isNaN(due)) throw new Error("Give in_minutes or a valid 'at' time.");
          if (due <= now()) throw new Error("That time is in the past.");
          const r = { id: newId(), message: String(a.message), due_at: iso(due), status: "pending" };
          state.reminders.push(r);
          return `Reminder #${r.id} set for ${localTime(due)}.`;
        }),
      t("list_reminders", "List upcoming reminders.", {}, [], () => {
        const rows = state.reminders.filter((r) => r.status === "pending");
        return rows.length ? rows.map((r) => `#${r.id} ${localTime(new Date(r.due_at))}: ${r.message}`).join("\n") : "No upcoming reminders.";
      }),
      t("cancel_reminder", "Cancel a reminder by id.", { id: { type: "integer" } }, ["id"], (a) => {
        const r = byId(state.reminders, a.id);
        if (!r || r.status !== "pending") throw new Error(`No upcoming reminder #${a.id}.`);
        r.status = "cancelled";
        return `Cancelled reminder #${r.id}.`;
      }),
      t("add_contact", "Save a contact (phone in +international format).", { name: str, phone: str, relationship: str }, ["name", "phone"], (a) => {
        const phone = String(a.phone).replace(/[\s()-]/g, "");
        if (!/^\+\d{7,15}$/.test(phone)) throw new Error("The number needs a + and country code, e.g. +15551234567.");
        state.contacts = state.contacts.filter((c) => c.name.toLowerCase() !== String(a.name).toLowerCase());
        state.contacts.push({ id: newId(), name: String(a.name), phone, relationship: String(a.relationship || "") });
        return `Saved ${a.name}.`;
      }),
      t("list_contacts", "List saved contacts.", {}, [], () =>
        state.contacts.map((c) => `${c.name}: ${c.phone}${c.relationship ? ` (${c.relationship})` : ""}`).join("\n") || "No contacts."),
      t("call_contact", "Phone someone (saved contact name or +number) on the user's behalf and deliver a message. Simulated in the demo. The user approves it in the app.",
        { who: str, message: str }, ["who", "message"], (a) => queue("call", a, pending)),
      t("text_contact", "Text someone (saved contact name or +number). Simulated in the demo. The user approves it in the app.",
        { who: str, message: str }, ["who", "message"], (a) => queue("text", a, pending)),
    ];
  }

  function queue(kind, a, pending) {
    const c = findContact(a.who);
    if (!c) throw new Error(`No contact called '${a.who}'. Ask for their number and save it with add_contact.`);
    const action = {
      id: newId(), kind, name: c.name, phone: c.phone, message: String(a.message),
      summary: `${kind === "call" ? "Call" : "Text"} ${c.name} (${c.phone}): "${a.message}"`, status: "pending",
    };
    state.actions.push(action);
    pending.push({ id: action.id, summary: action.summary });
    return `Waiting for the user's approval (action #${action.id}). Tell them briefly what you're about to do.`;
  }

  // ---------------------------------------------------------------- chat
  const OFFLINE_REPLY = "I'm running in demo mode without access to Claude here, Commander. Open this page on claude.ai and allow it to use Claude, or deploy the full Jarvis with your API key, and I'll be fully at your service.";

  async function askClaude(userText, pending, useTools = true) {
    const sample = await samplePromise;
    if (!sample || sampleState === "declined") return OFFLINE_REPLY;
    const facts = state.facts.map((f) => `- ${f.fact}`).join("\n") || "(nothing yet)";
    const rules = `${PERSONA}\n\nThings you remember about the user:\n${facts}`;
    const history = state.history.slice(-16);
    while (history.length && history[0].role !== "user") history.shift();
    const stamped = `[${localTime(now())}, ${tz}] ${userText}`;
    const turns = [{ role: "user", content: rules }, ...history, { role: "user", content: stamped }];
    try {
      const opts = { cache: false, modelTier: "quick" };
      if (useTools) opts.tools = makeTools(pending);
      const { text } = await sample(turns, opts);
      state.history.push({ role: "user", content: stamped }, { role: "assistant", content: text });
      save();
      return text;
    } catch (e) {
      const code = e && e.code;
      if (code === "not_granted" || code === "sampling_disabled" || code === "capability_disabled" || code === "not_declared") {
        sampleState = "declined";
        return OFFLINE_REPLY;
      }
      if (code === "tools_unavailable") {
        const { text } = await sample(turns, { cache: false, modelTier: "quick" });
        state.history.push({ role: "user", content: stamped }, { role: "assistant", content: text });
        save();
        return text;
      }
      if (code === "rate_limited") throw new Error("Claude is busy right now. Give it a moment and try again.");
      throw new Error((e && e.text) || "Claude couldn't answer that just now. Try again.");
    }
  }

  // ---------------------------------------------------------------- events
  const listeners = new Set();
  function publish(kind, message) {
    const ev = { kind, message, at: iso(now()) };
    state.feed.unshift(ev);
    state.feed = state.feed.slice(0, 30);
    save();
    for (const l of listeners) setTimeout(() => l.onmessage && l.onmessage({ data: JSON.stringify(ev) }), 0);
  }

  class DemoEventSource {
    constructor() {
      this.readyState = 1;
      listeners.add(this);
      setTimeout(() => this.onopen && this.onopen({}), 0);
    }
    close() { this.readyState = 2; listeners.delete(this); }
  }
  window.EventSource = DemoEventSource;

  setInterval(() => {
    for (const r of state.reminders) {
      if (r.status === "pending" && new Date(r.due_at) <= now()) {
        r.status = "fired";
        publish("reminder", `Reminder: ${r.message}`);
      }
    }
  }, 2000);

  if (!state.feed.length) {
    state.feed.unshift({ kind: "info", message: "Demo mode: Jarvis runs in this page and thinks with Claude. Calls are simulated.", at: iso(now()) });
    save();
  }

  // ---------------------------------------------------------------- API
  const counts = () => ({
    facts: state.facts.length,
    notes: state.notes.length,
    todos: state.todos.filter((x) => !x.done).length,
    reminders: state.reminders.filter((r) => r.status === "pending").length,
    contacts: state.contacts.length,
    calls: state.calls.length,
    turns: state.history.filter((m) => m.role === "user").length,
    tool_calls: state.toolCalls,
    tools: makeTools([]).length,
  });

  let cpu = 14;
  const system = () => {
    cpu = Math.max(4, Math.min(38, cpu + (Math.random() - 0.5) * 8));
    const mem = performance && performance.memory;
    const ram = mem ? (mem.usedJSHeapSize / mem.jsHeapSizeLimit) * 100 : 32;
    return { cpu: Math.round(cpu), ram: Math.max(3, Math.round(ram)), disk: 21 };
  };

  const routes = {
    "GET /api/status": () => ({
      name: "Commander", mode: "demo", model: "Claude (claude.ai)", phone: false, computer_control: false,
      two_way_calls: false, started_at: STARTED, ai_name: "Claude (demo)", ai_ready: sampleState !== "absent" && sampleState !== "declined", web_search: false,
      home_city: "", timezone: tz,
    }),
    "GET /api/dashboard": () => ({
      reminders: state.reminders.filter((r) => r.status === "pending")
        .sort((a, b) => a.due_at.localeCompare(b.due_at)).slice(0, 10)
        .map((r) => ({ id: r.id, message: r.message, due_at: r.due_at, due_local: new Date(r.due_at).toLocaleString([], { weekday: "short", hour: "2-digit", minute: "2-digit" }) })),
      todos: state.todos.filter((x) => !x.done).map(({ id, task, due }) => ({ id, task, due })),
      tasks: [...state.todos].sort((a, b) => a.done - b.done || PRI[a.priority] - PRI[b.priority] || b.id - a.id)
        .map(({ id, task, due, priority, done }) => ({ id, task, due, priority: priority || "med", done })),
      timeline: state.reminders.filter((r) => r.status !== "cancelled" && new Date(r.due_at) >= startOfDay())
        .sort((a, b) => a.due_at.localeCompare(b.due_at))
        .map((r) => ({ id: r.id, message: r.message, due_at: r.due_at, status: r.status,
                       time_local: new Date(r.due_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false }) })),
      actions: state.actions.filter((a) => a.status === "pending").map(({ id, summary }) => ({ id, summary })),
      facts: state.facts.length,
      counts: counts(),
      system: system(),
      feed: state.feed,
    }),
    "GET /api/system": () => system(),
    "POST /api/todos": (body) => {
      const task = String((body && body.task) || "").trim();
      if (!task) return [400, { detail: "The task is empty." }];
      state.todos.push({ id: newId(), task, due: "", priority: ["high", "med", "low"].includes(body.priority) ? body.priority : "med", done: 0 });
      save();
      return { ok: true };
    },
    "GET /api/weather": () => ({ available: false, label: "Full version", reason: "Weather needs the full Jarvis server." }),
    "POST /api/reset": () => { state.history = []; save(); return { ok: true }; },
    "POST /api/chat": async (body) => {
      const text = String((body && body.text) || "").trim();
      if (!text) return [400, { detail: "Say something first." }];
      const pending = [];
      const reply = await askClaude(text, pending);
      return { reply, actions: pending };
    },
  };

  const lists = {
    facts: () => [...state.facts].reverse().map((f) => ({ id: f.id, title: f.fact, detail: f.category })),
    notes: () => state.notes.map((n) => ({ id: n.id, title: n.title, detail: n.body })),
    todos: () => [...state.todos].sort((a, b) => a.done - b.done).map((x) => ({ id: x.id, title: x.task, detail: x.due, done: x.done })),
    reminders: () => [...state.reminders].reverse().map((r) => ({ id: r.id, title: r.message, detail: `${localTime(new Date(r.due_at))} · ${r.status}` })),
    contacts: () => state.contacts.map((c) => ({ id: c.id, title: c.name, detail: `${c.phone} ${c.relationship}` })),
    calls: () => [...state.calls].reverse().map((c) => ({ id: c.id, title: c.name, detail: `${c.kind} · simulated · ${localTime(new Date(c.at))}` })),
    tools: () => makeTools([]).map((t, i) => ({ id: i, title: t.name, detail: t.description })),
  };

  async function resolveAction(id, approve) {
    const a = byId(state.actions, id);
    if (!a || a.status !== "pending") return [409, { detail: `Action #${id} was already handled.` }];
    a.status = approve ? "approved" : "denied";
    let result = "Denied by the user.";
    if (approve) {
      state.calls.push({ id: newId(), kind: a.kind, name: a.name, phone: a.phone, message: a.message, at: iso(now()) });
      result = a.kind === "call"
        ? `Simulated call to ${a.name} (${a.phone}) delivering: "${a.message}". Real calls need Twilio in the full version.`
        : `Simulated text to ${a.name} (${a.phone}): "${a.message}". Real texts need Twilio in the full version.`;
      publish("call", approve ? result : `Cancelled: ${a.summary}`);
    }
    save();
    const note = `(I ${approve ? "approved" : "denied"} action #${id}: ${a.summary}. Result: ${result})`;
    let reply;
    // No tools here: Claude only confirms and can't place the call a second time.
    try { reply = await askClaude(note, [], false); } catch { reply = approve ? `Done. ${result}` : "Understood, I've cancelled that."; }
    if (reply === OFFLINE_REPLY) reply = approve ? `Done. ${result}` : "Understood, I've cancelled that.";
    return { reply, actions: [], result };
  }

  const json = (status, data) => new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
  const realFetch = window.fetch.bind(window);

  window.fetch = async (input, init = {}) => {
    const url = new URL(typeof input === "string" ? input : input.url, location.href);
    if (!url.pathname.startsWith("/api/")) return realFetch(input, init);
    const method = (init.method || "GET").toUpperCase();
    const body = init.body ? JSON.parse(init.body) : undefined;
    try {
      let out;
      const list = url.pathname.match(/^\/api\/list\/(\w+)$/);
      const action = url.pathname.match(/^\/api\/actions\/(\d+)$/);
      const todo = url.pathname.match(/^\/api\/todos\/(\d+)$/);
      if (list && method === "GET") out = lists[list[1]] ? lists[list[1]]() : [404, { detail: "Unknown list." }];
      else if (action && method === "POST") out = await resolveAction(Number(action[1]), !!(body && body.approve));
      else if (todo && method === "POST") {
        const td = byId(state.todos, todo[1]);
        if (td) { td.done = body && body.done ? 1 : 0; save(); out = { ok: true }; } else out = [404, { detail: "No such task." }];
      }
      else if (routes[`${method} ${url.pathname}`]) out = await routes[`${method} ${url.pathname}`](body);
      else out = [404, { detail: "Not found." }];
      return Array.isArray(out) && typeof out[0] === "number" ? json(out[0], out[1]) : json(200, out);
    } catch (e) {
      return json(500, { detail: (e && e.message) || "Something went wrong." });
    }
  };

  // Microphones are blocked inside the claude.ai page frame; say so plainly.
  window.JARVIS_NO_SCREEN = true;  // screen capture is blocked inside the claude.ai page frame
  window.JARVIS_NO_VOICE_MSG = "Voice input isn't available in this preview. Type instead; the full Jarvis listens in Chrome, Edge or Safari.";
  delete window.SpeechRecognition;
  delete window.webkitSpeechRecognition;
  window.SpeechRecognition = undefined;
  window.webkitSpeechRecognition = undefined;
})();
