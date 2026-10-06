// Everything the pages do after loading. All of it is optional: with this file missing, a
// page still reads top to bottom with every output shown.
(function () {
  "use strict";

  var root = document.documentElement;
  var prefs = window.lectern.prefs;
  var bar = document.querySelector(".bar");
  var doc = document.querySelector("main.doc");

  // ---- Is the server there? ----

  var PING_TIMEOUT = 2500;
  var RETRY_EVERY = 2000;

  function ping() {
    var abort = new AbortController();
    var timer = setTimeout(function () {
      abort.abort();
    }, PING_TIMEOUT);
    return fetch("/_ping", { cache: "no-store", signal: abort.signal })
      .then(function (response) {
        return response.ok ? response.json() : Promise.reject(new Error(response.status));
      })
      .finally(function () {
        clearTimeout(timer);
      });
  }

  // Where this script was loaded from is where the icon is.
  var assets = document.currentScript ? document.currentScript.src.replace(/reader\.js.*$/, "") : "";
  var served = !("static" in root.dataset);

  // Behind HTTPS (or on localhost) a service worker can stand in for the browser's own
  // error page. Elsewhere browsers do not offer one, and this does nothing.
  if (served && "serviceWorker" in navigator) {
    navigator.serviceWorker.register("/_sw.js", { scope: "/" }).catch(function () {});
  }

  // The "not running" screen: shown over the page, checked again every two seconds, and
  // gone by itself, on to `target`, once the server answers.
  var waitingFor = null;

  function waitForServer(target, pause) {
    var screen = document.getElementById("offline");
    if (!screen) {
      screen = document.createElement("div");
      screen.id = "offline";
      screen.className = "offline";
      screen.innerHTML =
        '<img class="offline-icon" src="' + assets + 'icons/icon.svg" alt="" width="72" height="72">' +
        "<h1>Lectern</h1>" +
        '<div class="offline-msg"><p><strong>Lectern is not running.</strong></p>' +
        "<p>On your Mac, run <code>lectern serve</code> in the folder you want to read. " +
        "This page will carry on by itself.</p>" +
        '<p><button type="button" data-retry>Try again</button></p></div>';
      document.body.appendChild(screen);
    }
    screen.hidden = false;
    screen.querySelector(".offline-msg").hidden = false;
    var already = waitingFor !== null;
    waitingFor = target;
    if (already) return;

    var timer = 0;
    var button = screen.querySelector("[data-retry]");
    function retry() {
      clearTimeout(timer);
      button.disabled = true;
      ping().then(
        function () {
          location.replace(waitingFor);
        },
        function () {
          button.disabled = false;
          timer = setTimeout(retry, RETRY_EVERY);
        }
      );
    }
    button.addEventListener("click", retry);
    // Timers are slowed or stopped while an app is in the background; ask at once on
    // coming back instead of leaving the screen up until the next tick.
    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState === "visible") retry();
    });
    window.addEventListener("pageshow", retry);
    timer = setTimeout(retry, pause || 0);
  }

  // The start page. It is cached for a long time so that it still opens when the server
  // is down, and its only job is to find out which case this is.
  var shell = document.getElementById("offline");
  if (shell) {
    var home = shell.dataset.home;
    if (!home) {
      // Put here by the service worker instead of a page that did not load. The pause
      // keeps a server that answers pings but not this page from being asked in a loop.
      waitForServer(location.href, 1500);
      return;
    }
    ping().then(
      function (info) {
        // A newer lectern than the one that cached this page: refresh the cached copy.
        var refresh =
          info.assets === shell.dataset.assets ? Promise.resolve() : fetch("/", { cache: "reload" });
        refresh.catch(function () {}).then(function () {
          location.replace(home);
        });
      },
      function () {
        waitForServer(home);
      }
    );
    return;
  }

  // Following a link to a server that has stopped leaves a Home Screen app reloading a
  // page that cannot load, with no way back. So ask first, and stay here if it is gone.
  document.addEventListener("click", function (event) {
    if (event.defaultPrevented || event.button || event.metaKey || event.ctrlKey || event.shiftKey) {
      return;
    }
    var link = event.target.closest && event.target.closest("a[href]");
    if (!link || link.target || link.origin !== location.origin) return;
    if (link.pathname === location.pathname && link.hash) return;
    // A published site has no lectern server behind it to ask.
    if (!served) return;
    event.preventDefault();
    ping().then(
      function () {
        location.assign(link.href);
      },
      function () {
        waitForServer(link.href);
      }
    );
  });

  // ---- Top bar: out of the way while reading down, back on the way up ----

  var lastY = window.scrollY;
  var holdBar = 0;

  function eink() {
    return root.dataset.theme.indexOf("eink") === 0;
  }

  function showBar(show) {
    // On e-ink the bar stays put: sliding it in and out is a repaint each time.
    root.classList.toggle("bar-away", !show && !eink());
  }

  window.addEventListener(
    "scroll",
    function () {
      var y = Math.max(0, window.scrollY);
      var moved = y - lastY;
      if (Math.abs(moved) < 6) return;
      lastY = y;
      if (Date.now() < holdBar) return;
      showBar(moved < 0 || y < bar.offsetHeight);
    },
    { passive: true }
  );

  // ---- Sheets: contents and settings ----

  function openSheet(sheet) {
    showBar(true);
    sheet.showModal();
  }

  document.querySelectorAll("dialog.sheet").forEach(function (sheet) {
    sheet.addEventListener("click", function (event) {
      // A click on the dialog element itself is a click on the backdrop around its panel.
      if (event.target === sheet || event.target.closest("[data-close]")) sheet.close();
    });
  });

  document.querySelectorAll("[data-open]").forEach(function (button) {
    button.addEventListener("click", function () {
      var sheet = document.getElementById(button.dataset.open);
      if (sheet.id === "toc") markCurrentHeading(sheet);
      openSheet(sheet);
    });
  });

  function readingLine() {
    return bar.offsetHeight + 12;
  }

  function markCurrentHeading(sheet) {
    var current = null;
    var line = readingLine() + window.innerHeight * 0.25;
    sheet.querySelectorAll("a[href^='#']").forEach(function (link) {
      link.removeAttribute("aria-current");
      var heading = document.getElementById(decodeURIComponent(link.hash.slice(1)));
      if (heading && heading.getBoundingClientRect().top < line) current = link;
    });
    if (current) {
      current.setAttribute("aria-current", "true");
      requestAnimationFrame(function () {
        current.scrollIntoView({ block: "center" });
      });
    }
  }

  var toc = document.getElementById("toc");
  if (toc) {
    toc.addEventListener("click", function (event) {
      if (!event.target.closest("a")) return;
      toc.close();
      // The jump scrolls the page; that should not count as reading on and hide the bar.
      holdBar = Date.now() + 600;
    });
  }

  // ---- Settings ----

  var settings = document.getElementById("settings");
  // Column widths in px, as in themes.css.
  var WIDTHS = { n: 600, m: 700, w: 820, x: 1040, f: Infinity };

  function showSettings() {
    settings.querySelectorAll("[data-pref]").forEach(function (button) {
      var on = String(prefs[button.dataset.pref]) === button.dataset.value;
      button.setAttribute("aria-pressed", on);
    });
    settings.querySelector("[data-modes]").hidden = prefs.family === "eink";
    settings.querySelector("[data-inks]").hidden = prefs.family !== "eink";
    // Only where there is a file that can change under the page, and not on e-ink, where
    // a page redrawing by itself is a full flash and keeps the radio awake.
    settings.querySelector("[data-follow-setting]").hidden =
      !doc || "static" in root.dataset || prefs.family === "eink";
    // A width is offered only if it is visibly wider than the one before it on this
    // screen. The chosen one may not be on offer here (chosen on a larger screen, or the
    // window has shrunk); then the widest that is offered is what the page looks like.
    var room = (window.innerWidth - 32) * 0.92;
    var previous = 0;
    var offered = [];
    var widths = settings.querySelectorAll("[data-pref='width']");
    widths.forEach(function (button) {
      button.hidden = previous >= room;
      if (!button.hidden) offered.push(button.dataset.value);
      previous = WIDTHS[button.dataset.value];
    });
    var effective = offered.indexOf(prefs.width) < 0 ? offered[offered.length - 1] : prefs.width;
    widths.forEach(function (button) {
      button.setAttribute("aria-pressed", button.dataset.value === effective);
    });
    // With one width to choose from, as on a phone, there is nothing to choose.
    settings.querySelector("[data-width-setting]").hidden = offered.length < 2;
    settings.querySelector("[data-size-value]").textContent = prefs.size + " px";
    settings.querySelector("[data-size-step='-1']").disabled = prefs.size <= window.lectern.size.min;
    settings.querySelector("[data-size-step='1']").disabled = prefs.size >= window.lectern.size.max;
  }

  // Changing the text size or column width reflows the page; keep the same place in view.
  function keepingPlace(change) {
    var place = doc && currentPlace();
    change();
    if (place) goToPlace(place);
  }

  if (settings) {
    settings.addEventListener("click", function (event) {
      var button = event.target.closest("button");
      if (!button) return;
      if (button.dataset.pref) {
        var value = button.dataset.value;
        if (value === "true" || value === "false") value = value === "true";
        keepingPlace(function () {
          window.lectern.set(button.dataset.pref, value);
          if (button.dataset.pref === "hideCode") applyHideCode();
        });
        showBar(true);
        updatePager();
      } else if (button.dataset.sizeStep) {
        keepingPlace(function () {
          window.lectern.set("size", prefs.size + Number(button.dataset.sizeStep));
        });
        updatePager();
      }
      showSettings();
    });
    showSettings();
  }

  // ---- Turning pages (e-ink) ----
  // Scrolling smears on e-ink, so the page moves a screenful at a time, at once: by the
  // buttons at the bottom, a tap on the left or right edge, or the page keys.

  var pager = document.querySelector(".pager");

  function pageStep() {
    var twoLines = 2 * 1.6 * parseFloat(getComputedStyle(root).fontSize);
    var covered = bar.offsetHeight + (pager ? pager.offsetHeight : 0);
    return Math.max(120, window.innerHeight - covered - twoLines);
  }

  function lastScroll() {
    return Math.max(0, root.scrollHeight - window.innerHeight);
  }

  function turn(direction) {
    var to = window.scrollY + direction * pageStep();
    if (direction === "start") to = 0;
    if (direction === "end") to = lastScroll();
    window.scrollTo({ top: to, behavior: "instant" });
  }

  function updatePager() {
    if (!pager || !eink()) return;
    var step = pageStep();
    var last = lastScroll();
    var y = Math.min(last, Math.max(0, window.scrollY));
    var total = Math.ceil(last / step) + 1;
    var page = y >= last - 1 ? total : Math.min(total, Math.floor(y / step + 0.01) + 1);
    var label = page + " / " + total;
    var output = pager.querySelector("[data-page]");
    if (output.textContent !== label) output.textContent = label;
    pager.querySelector("[data-turn='start']").disabled = y <= 0;
    pager.querySelector("[data-turn='-1']").disabled = y <= 0;
    pager.querySelector("[data-turn='1']").disabled = y >= last - 1;
    pager.querySelector("[data-turn='end']").disabled = y >= last - 1;
  }

  if (pager) {
    pager.addEventListener("click", function (event) {
      var button = event.target.closest("[data-turn]");
      if (button) {
        var to = button.dataset.turn;
        turn(to === "start" || to === "end" ? to : Number(to));
      } else if (event.target.closest("[data-page]")) {
        // The page number puts the top bar away and brings it back, for a screen that is
        // all text. Remembered on this device; the same tap is the only way back.
        keepingPlace(function () {
          window.lectern.set("noBar", !prefs.noBar);
        });
        updatePager();
      }
    });
    window.addEventListener("scroll", updatePager, { passive: true });
    window.addEventListener("resize", updatePager);
    window.addEventListener("load", updatePager);

    var EDGE = 0.3;
    document.addEventListener("click", function (event) {
      if (!eink() || event.defaultPrevented) return;
      // Anything that does something of its own keeps its tap.
      if (event.target.closest("a, button, summary, input, dialog, .bar, .pager, .table-wrap")) return;
      if (String(window.getSelection())) return;
      var x = event.clientX / window.innerWidth;
      if (x < EDGE) turn(-1);
      else if (x > 1 - EDGE) turn(1);
    });

    var KEYS = {
      PageDown: 1,
      ArrowRight: 1,
      " ": 1,
      PageUp: -1,
      ArrowLeft: -1,
      Home: "start",
      End: "end",
    };
    document.addEventListener("keydown", function (event) {
      if (!eink() || !KEYS[event.key] || event.metaKey || event.ctrlKey || event.altKey) return;
      if (document.querySelector("dialog[open]")) return;
      event.preventDefault();
      turn(KEYS[event.key]);
    });
  }

  // ---- Math ----
  // Before anything measures the page: typeset math is not the size of its source. Each
  // formula is in its own element, put there by the renderer; KaTeX is only on pages that
  // have some. One that fails to typeset is left as the TeX it was written in.

  if (window.katex) {
    // A `text/latex` output comes wrapped in the delimiters that markdown math has lost.
    var DELIMITED = [/^\$\$([\s\S]+)\$\$$/, /^\\\[([\s\S]+)\\\]$/, /^\$([\s\S]+)\$$/, /^\\\(([\s\S]+)\\\)$/];
    document.querySelectorAll(".math").forEach(function (element) {
      var tex = element.textContent.trim();
      DELIMITED.some(function (pattern) {
        var inside = pattern.exec(tex);
        if (inside) tex = inside[1];
        return inside;
      });
      try {
        window.katex.render(tex, element, {
          displayMode: element.classList.contains("display"),
          throwOnError: true,
        });
        element.classList.add("typeset");
      } catch (e) {}
    });
  }

  // ---- Code cells ----

  var OPEN_UP_TO = 30;

  function applyHideCode() {
    document.querySelectorAll("details.src").forEach(function (cell) {
      cell.open = !prefs.hideCode && Number(cell.dataset.lines) <= OPEN_UP_TO;
    });
  }

  if (prefs.hideCode) applyHideCode();
  updatePager();

  // ---- Printed output: long blocks start short, wide ones can stop wrapping ----

  var CLAMP_ABOVE = 60;
  var LONG_LINE = 100;

  function toolButton(label) {
    var button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    return button;
  }

  document.querySelectorAll("pre.stream").forEach(function (pre) {
    var lines = pre.children.length;
    var tall = lines > CLAMP_ABOVE;
    var wide = Array.prototype.some.call(pre.children, function (line) {
      return line.textContent.length > LONG_LINE;
    });
    if (!tall && !wide) return;
    var tools = document.createElement("div");
    tools.className = "stream-tools";
    if (tall) {
      pre.classList.add("clamped");
      var more = toolButton("Show all " + lines + " lines");
      more.addEventListener("click", function () {
        var clamped = pre.classList.toggle("clamped");
        more.textContent = clamped ? "Show all " + lines + " lines" : "Show fewer lines";
        if (clamped && pre.getBoundingClientRect().top < readingLine()) {
          pre.scrollIntoView({ block: "start" });
        }
      });
      tools.appendChild(more);
    }
    if (wide) {
      var wrap = toolButton("No wrap");
      wrap.addEventListener("click", function () {
        wrap.textContent = pre.classList.toggle("wrap") ? "No wrap" : "Wrap";
      });
      tools.appendChild(wrap);
    }
    pre.after(tools);
  });

  // ---- Reading position ----
  // Kept as a cell id and how far through that cell the reading line was, so it survives a
  // different text size, a rotated screen, and edits elsewhere in the notebook.

  function cells() {
    return doc.querySelectorAll(":scope > .cell");
  }

  function currentPlace() {
    var line = readingLine();
    var found = null;
    Array.prototype.some.call(cells(), function (cell) {
      var box = cell.getBoundingClientRect();
      if (box.bottom <= line) return false;
      // Negative in the gap above a cell; kept as it is, so the place is exact.
      found = { cell: cell.id, frac: (line - box.top) / (box.height || 1) };
      return true;
    });
    return found;
  }

  function goToPlace(place) {
    var cell = place.cell && document.getElementById(place.cell);
    if (!cell) return;
    var box = cell.getBoundingClientRect();
    holdBar = Date.now() + 600;
    window.scrollTo(0, window.scrollY + box.top + place.frac * box.height - readingLine());
    lastY = window.scrollY;
  }

  if (doc && doc.dataset.path) {
    var POSITION = "lectern:pos:" + doc.dataset.path;

    var savePlace = function () {
      // Being at the top is not a place worth coming back to.
      var place = window.scrollY > 40 ? currentPlace() : null;
      try {
        if (place) {
          place.mtime = doc.dataset.mtime;
          localStorage.setItem(POSITION, JSON.stringify(place));
        } else {
          localStorage.removeItem(POSITION);
        }
      } catch (e) {}
    };

    var saving = 0;
    window.addEventListener(
      "scroll",
      function () {
        clearTimeout(saving);
        saving = setTimeout(savePlace, 300);
      },
      { passive: true }
    );
    window.addEventListener("pagehide", savePlace);
    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState === "hidden") savePlace();
    });

    // ---- Following a notebook that is being worked on ----
    // Asks every two seconds whether the file has changed, while the page is in view, and
    // loads the new version in the same place. A failed ask (the server stopped, the file
    // half-saved) changes nothing.
    if (!("static" in root.dataset)) {
      var seen = null;
      setInterval(function () {
        if (!prefs.follow || eink() || document.visibilityState !== "visible") return;
        fetch(location.pathname, { method: "HEAD", cache: "no-store" })
          .then(function (response) {
            var now = response.ok && response.headers.get("ETag");
            if (!now) return;
            if (seen && now !== seen) {
              savePlace();
              location.reload();
            }
            seen = now;
          })
          .catch(function () {});
      }, 2000);
    }

    if (!location.hash) {
      history.scrollRestoration = "manual";
      var saved = null;
      try {
        saved = JSON.parse(localStorage.getItem(POSITION));
      } catch (e) {}
      if (saved) {
        goToPlace(saved);
        // Fonts arriving can move everything; settle once more when they have.
        if (document.fonts && document.fonts.ready) {
          document.fonts.ready.then(function () {
            goToPlace(saved);
          });
        }
      }
    }
  }
})();
