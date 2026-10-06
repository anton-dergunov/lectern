// Shows lectern's own "not running" page where the browser would show its error page.
//
// Served as /_sw.js with the two placeholders filled in. Browsers only run service workers
// on HTTPS or localhost, so this is at work behind Tailscale and not on a plain .local
// address, where the long-cached start page does the same job for the Home Screen icon.
//
// It never answers for the server while the server answers: everything goes to the
// network first, and nothing but the "not running" page and what it needs is kept.

const CACHE = "lectern-__VERSION__";
const OFFLINE = "/_offline";
const NEEDED = __ASSETS__;

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll([OFFLINE, ...NEEDED]))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) => names.filter((name) => name.startsWith("lectern-") && name !== CACHE))
      .then((old) => Promise.all(old.map((name) => caches.delete(name))))
      .then(() => self.clients.claim())
  );
});

function notRunning(otherwise) {
  return caches.match(OFFLINE).then((page) => page || otherwise);
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).then(
        // An error page from something in front of lectern (a proxy with nothing behind
        // it) is the same news as no answer. Lectern's own error pages carry its header.
        (response) =>
          response.status >= 500 && !response.headers.has("X-Lectern")
            ? notRunning(response)
            : response,
        () => notRunning(Response.error())
      )
    );
  } else if (url.pathname.startsWith("/_static/")) {
    event.respondWith(fetch(request).catch(() => caches.match(request)));
  }
});
