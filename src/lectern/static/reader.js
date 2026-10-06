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

  // The "not running" screen: shown over the page, checked again every two seconds, and
  // gone by itself, on to `target`, once the server answers.
  function waitForServer(target) {
    var screen = document.getElementById("offline");
    if (!screen) {
      screen = document.createElement("div");
      screen.id = "offline";
      screen.className = "offline";
      screen.innerHTML =
        "<h1>Lectern</h1>" +
        '<div class="offline-msg"><p><strong>Lectern is not running.</strong></p>' +
        "<p>On your Mac, run <code>lectern serve</code> in the folder you want to read. " +
        "This page will carry on by itself.</p></div>";
      document.body.appendChild(screen);
    }
    screen.hidden = false;
    screen.querySelector(".offline-msg").hidden = false;
    (function retry() {
      ping().then(
        function () {
          location.replace(target);
        },
        function () {
          setTimeout(retry, RETRY_EVERY);
        }
      );
    })();
  }

  // The start page. It is cached for a long time so that it still opens when the server
  // is down, and its only job is to find out which case this is.
  var shell = document.getElementById("offline");
  if (shell) {
    var home = shell.dataset.home;
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

  function showBar(show) {
    root.classList.toggle("bar-away", !show);
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

  function showSettings() {
    settings.querySelectorAll("[data-pref]").forEach(function (button) {
      var on = String(prefs[button.dataset.pref]) === button.dataset.value;
      button.setAttribute("aria-pressed", on);
    });
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
      } else if (button.dataset.sizeStep) {
        keepingPlace(function () {
          window.lectern.set("size", prefs.size + Number(button.dataset.sizeStep));
        });
      }
      showSettings();
    });
    showSettings();
  }

  // ---- Code cells ----

  var OPEN_UP_TO = 30;

  function applyHideCode() {
    document.querySelectorAll("details.src").forEach(function (cell) {
      cell.open = !prefs.hideCode && Number(cell.dataset.lines) <= OPEN_UP_TO;
    });
  }

  if (prefs.hideCode) applyHideCode();

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
