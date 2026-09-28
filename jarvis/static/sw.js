// Jarvis service worker: lets Jarvis be installed as an app, shows notifications
// pushed by the server (reminders, briefings, calls) even when Jarvis is closed,
// and shows a friendly page instead of an error when there's no connection.
// Nothing is cached, so a new version of Jarvis always loads straight away.
"use strict";

const OFFLINE_PAGE = `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Jarvis · offline</title>
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#07111b;color:#e3eef8;
font:16px system-ui,-apple-system,sans-serif;text-align:center}div{max-width:340px;padding:24px}
b{display:block;letter-spacing:.3em;color:#3aa6ff;margin-bottom:12px}button{margin-top:18px;padding:10px 18px;
border-radius:10px;border:1px solid #3aa6ff;background:transparent;color:#e3eef8;font:inherit}</style></head>
<body><div><b>JARVIS</b>You're offline, or Jarvis's server is waking up. Check your connection and try again.
<br><button onclick="location.reload()">Try again</button></div></body></html>`;

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("fetch", (event) => {
  // Only page loads get the offline fallback; everything else goes straight to the network.
  if (event.request.mode !== "navigate") return;
  event.respondWith(fetch(event.request).catch(() =>
    new Response(OFFLINE_PAGE, { headers: { "Content-Type": "text/html; charset=utf-8" } })));
});

self.addEventListener("push", (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch { data = { body: event.data && event.data.text() }; }
  event.waitUntil(self.registration.showNotification(data.title || "Jarvis", {
    body: data.body || "",
    tag: data.tag || "jarvis",
    renotify: true,
    icon: "/static/icons/icon-192.png",
    badge: "/static/icons/icon-192.png",
    data: { url: data.url || "/" },
  }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = new URL((event.notification.data && event.notification.data.url) || "/", self.location.origin).href;
  event.waitUntil((async () => {
    const open = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const client of open) {
      if (client.url.startsWith(self.location.origin)) { await client.focus(); return; }
    }
    await self.clients.openWindow(url);
  })());
});
