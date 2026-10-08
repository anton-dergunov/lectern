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
  // Marking text: on a document lectern is serving, in a browser that can paint the marks.
  var canMark = Boolean(
    served && doc && doc.dataset.path && window.Highlight && window.CSS && CSS.highlights
  );

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

  // ---- Back and forward between documents ----
  // The pages opened in this tab, kept here and not taken from the browser's history: a
  // jump inside a page is a history entry too, and going back would step through those
  // instead of leaving the document. A Home Screen app has no buttons for it anyway.

  var TRAIL = "lectern:trail";
  var TRAIL_MOVE = "lectern:trail-move";
  var TRAIL_KEEPS = 50;
  var address = location.pathname + location.search;
  var upLink = bar && bar.querySelector("a.back");
  var up = upLink && { href: upLink.getAttribute("href"), label: upLink.getAttribute("aria-label") };

  function syncTrail(arrival) {
    var trail = null;
    var move = null;
    try {
      trail = JSON.parse(sessionStorage.getItem(TRAIL));
      move = sessionStorage.getItem(TRAIL_MOVE);
      sessionStorage.removeItem(TRAIL_MOVE);
    } catch (e) {}
    if (!trail || !Array.isArray(trail.list) || !trail.list[trail.at]) trail = { list: [], at: -1 };
    function isHere(index) {
      return Boolean(trail.list[index]) && trail.list[index].url === address;
    }
    if (move !== null && isHere(Number(move))) {
      // One of the two buttons below brought us here.
      trail.at = Number(move);
    } else if (isHere(trail.at)) {
      // A reload.
    } else if (arrival === "back_forward" && isHere(trail.at - 1)) {
      trail.at -= 1;
    } else if (arrival === "back_forward" && isHere(trail.at + 1)) {
      trail.at += 1;
    } else {
      trail.list = trail.list.slice(Math.max(0, trail.at + 2 - TRAIL_KEEPS), trail.at + 1);
      trail.list.push({ url: address });
      trail.at = trail.list.length - 1;
    }
    trail.list[trail.at].title = document.title;
    try {
      sessionStorage.setItem(TRAIL, JSON.stringify(trail));
    } catch (e) {
      // Nowhere to keep it: the chevron stays the way up to the folder.
      return;
    }

    var previous = trail.list[trail.at - 1];
    var next = trail.list[trail.at + 1];
    // On a document the chevron goes back to where the reader came from, and up to the
    // folder only when they came from nowhere. A listing's chevron always goes up.
    if (upLink) {
      var back = doc && previous;
      upLink.setAttribute("href", back ? previous.url : up.href);
      upLink.setAttribute("aria-label", back ? "Back to " + previous.title : up.label);
      if (back) upLink.dataset.trail = trail.at - 1;
      else delete upLink.dataset.trail;
    }
    var forward = bar.querySelector("a.forward");
    if (next && !forward) {
      forward = document.createElement("a");
      forward.className = "bar-button forward";
      forward.innerHTML =
        '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M9 5l7 7-7 7" ' +
        'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
      if (upLink) upLink.after(forward);
      else bar.prepend(forward);
    }
    if (next) {
      forward.setAttribute("href", next.url);
      forward.setAttribute("aria-label", "Forward to " + next.title);
      forward.dataset.trail = trail.at + 1;
    } else if (forward) {
      forward.remove();
    }
  }

  if (bar) {
    var arrived = performance.getEntriesByType && performance.getEntriesByType("navigation")[0];
    syncTrail(arrived ? arrived.type : "");
    // A page brought back whole by the browser's own back or forward does not load again.
    window.addEventListener("pageshow", function (event) {
      if (event.persisted) syncTrail("back_forward");
    });
    // Says which way the trail is being walked. It is believed on arrival only if the page
    // at that step is the one that loaded, so a link that led nowhere leaves nothing behind.
    bar.addEventListener("click", function (event) {
      var link = event.target.closest("a[data-trail]");
      if (!link) return;
      try {
        sessionStorage.setItem(TRAIL_MOVE, link.dataset.trail);
      } catch (e) {}
    });
  }

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
      // One inside a folded section has no place on the page.
      if (heading && heading.getClientRects().length && heading.getBoundingClientRect().top < line) {
        current = link;
      }
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
  // How much of the page before stays at the top of the next one, in lines of text.
  var CARRY_LINES = 2;
  var SHORTEST_TURN = 120;

  function lineHeight() {
    return 1.6 * parseFloat(getComputedStyle(root).fontSize);
  }

  function pageStep() {
    var covered = bar.offsetHeight + (pager ? pager.offsetHeight : 0);
    return Math.max(SHORTEST_TURN, window.innerHeight - covered - CARRY_LINES * lineHeight());
  }

  function lastScroll() {
    return Math.max(0, root.scrollHeight - window.innerHeight);
  }

  // A turn starts and ends on a whole line. The page is moved so that a line begins right
  // under the bar; line heights differ, so the bottom cannot be made to land as well, and
  // a strip in the page's colour covers the line the footer would cut through. That line
  // is the first one not yet read, so the next turn carries on from it.

  var trim = null;
  var trimmed = 0;
  var turnedTo = -1;
  // The turns made so far, each as where it left and where it arrived. Forward and back
  // are worked out differently (one from the bottom of the page, one from the top), so a
  // turn back is not the reverse of the turn that came before it; it retraces that turn
  // instead, and Previous then Next ends on the page it started from.
  var turns = [];

  function leaveTurns() {
    setTrim(0);
    turns = [];
  }

  function setTrim(height) {
    trimmed = height;
    if (!trim && height) {
      trim = document.createElement("div");
      trim.className = "page-trim";
      pager.before(trim);
    }
    if (trim) {
      trim.style.bottom = pager.offsetHeight + "px";
      trim.style.height = height + "px";
    }
  }

  function caretAt(x, y) {
    if (document.caretPositionFromPoint) {
      var position = document.caretPositionFromPoint(x, y);
      return position && { node: position.offsetNode, offset: position.offset };
    }
    if (document.caretRangeFromPoint) {
      var range = document.caretRangeFromPoint(x, y);
      return range && { node: range.startContainer, offset: range.startOffset };
    }
    return null;
  }

  // The line of text, table row, cell's Show/Hide or small picture drawn at this height of the screen, as
  // its top and bottom, or nothing when that height falls between lines. Anything much
  // taller than a line (a figure, a table) is not something to stop at the edge of.
  function lineAt(y) {
    var column = doc.getBoundingClientRect();
    var tallest = 3 * lineHeight();
    var found = null;
    function take(box) {
      if (box.top <= y && y < box.bottom && box.height > 0 && box.height <= tallest) found = box;
      return Boolean(found);
    }
    [column.left + column.width / 2, column.left + 40, column.right - 40].some(function (x) {
      var caret = caretAt(x, y);
      if (caret && caret.node.nodeType === Node.TEXT_NODE) {
        // The caret sits between two characters; either may be the one on this line.
        var hit = [caret.offset, caret.offset - 1].some(function (start) {
          if (start < 0 || start >= caret.node.length) return false;
          var range = document.createRange();
          range.setStart(caret.node, start);
          range.setEnd(caret.node, start + 1);
          return Array.prototype.some.call(range.getClientRects(), take);
        });
        if (hit) return true;
      }
      var element = document.elementFromPoint(x, y);
      var whole = element && doc.contains(element) && element.closest("tr, summary, img, svg, .katex-display");
      return Boolean(whole) && take(whole.getBoundingClientRect());
    });
    return found;
  }

  function turn(direction) {
    var whole = doc && pager && typeof direction === "number";
    var top = bar.offsetHeight;
    var bottom = window.innerHeight - (pager ? pager.offsetHeight : 0);
    var from = window.scrollY;
    var to = from + direction * pageStep();
    if (direction === "start") to = 0;
    if (direction === "end") to = lastScroll();
    var made = turns[turns.length - 1];
    var retraced = whole && made && made.direction === -direction && Math.abs(made.to - from) <= 1;
    if (!whole) turns = [];
    if (retraced) {
      to = turns.pop().from;
    } else if (whole && direction > 0) {
      // From the first line that is not fully in view, less the lines carried over.
      // Under the strip is the line it was put there to cover.
      var unread = bottom - trimmed;
      var cut = trimmed ? null : lineAt(bottom - 1);
      if (cut) unread = cut.top;
      var forward = unread - CARRY_LINES * lineHeight() - top;
      if (forward >= SHORTEST_TURN) to = window.scrollY + forward;
    }
    setTrim(0);
    window.scrollTo({ top: to, behavior: "instant" });
    if (whole) {
      var first = !retraced && lineAt(top + 1);
      if (first && first.top < top) {
        window.scrollTo({ top: window.scrollY + first.top - top - 2, behavior: "instant" });
      }
      if (!retraced && Math.abs(window.scrollY - from) > 1) {
        turns.push({ from: from, to: window.scrollY, direction: direction });
        if (turns.length > 200) turns.shift();
      }
      var last = window.scrollY < lastScroll() - 1 && lineAt(bottom - 1);
      if (last && last.bottom > bottom) setTrim(Math.ceil(bottom - last.top) + 1);
    }
    turnedTo = window.scrollY;
  }

  function updatePager() {
    if (!pager || !eink()) return;
    // The strip belongs to the page a turn arrived at; any other move does away with it.
    if (Math.abs(window.scrollY - turnedTo) > 1) leaveTurns();
    var step = pageStep();
    var last = lastScroll();
    var y = Math.min(last, Math.max(0, window.scrollY));
    var total = Math.ceil(last / step) + 1;
    // To the nearest: a turn that stops on a whole line is a little short of a full step.
    var page = y >= last - 1 ? total : Math.min(total, Math.round(y / step) + 1);
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
    window.addEventListener("resize", function () {
      // Nothing is where it was.
      leaveTurns();
      updatePager();
    });
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

  // ---- Sections that fold ----
  // A heading's section is everything after it up to the next heading of its level or
  // above, wherever the cells happen to be divided: a heading is often in the middle of a
  // markdown cell. So the page is taken as one run of blocks (each piece of a markdown
  // cell, each code cell whole) and the folded headings hide the blocks that follow them.

  var blocks = [];
  var folded = {};
  var FOLDS = doc && doc.dataset.path ? "lectern:fold:" + doc.dataset.path : null;

  if (doc) {
    cells().forEach(function (cell) {
      if (!cell.classList.contains("md")) {
        blocks.push({ el: cell, level: 0 });
        return;
      }
      Array.prototype.forEach.call(cell.children, function (el) {
        var heading = /^H[1-4]$/.test(el.tagName) && el.id;
        blocks.push({ el: el, level: heading ? Number(el.tagName.charAt(1)) : 0 });
      });
    });
    // A heading with nothing under it has nothing to fold.
    blocks.forEach(function (block, index) {
      var next = blocks[index + 1];
      if (block.level && (!next || (next.level && next.level <= block.level))) block.level = 0;
    });
  }

  function headingBlocks() {
    return blocks.filter(function (block) {
      return block.level;
    });
  }

  // The folded heading that hides this element, if one does.
  function hiderOf(element) {
    var hider = null;
    var found = null;
    blocks.some(function (block) {
      if (hider && block.level && block.level <= hider.level) hider = null;
      if (block.el.contains(element) || element.contains(block.el)) {
        found = hider;
        return true;
      }
      if (!hider && block.level && folded[block.el.id]) hider = block;
      return false;
    });
    return found;
  }

  function applyFolds() {
    var hiding = 0;
    blocks.forEach(function (block) {
      if (hiding && block.level && block.level <= hiding) hiding = 0;
      block.el.classList.toggle("folded-away", hiding > 0);
      if (!hiding && block.level && folded[block.el.id]) hiding = block.level;
      if (block.level) {
        block.el.querySelector(".fold").setAttribute("aria-expanded", !folded[block.el.id]);
      }
    });
    // A markdown cell with nothing left showing gives up its place too.
    doc.querySelectorAll(":scope > .cell.md").forEach(function (cell) {
      var empty = cell.children.length > 0 && !cell.querySelector(":scope > :not(.folded-away)");
      cell.classList.toggle("folded-away", empty);
    });
    if (toc) {
      toc.querySelectorAll("a[href^='#']").forEach(function (link) {
        link.toggleAttribute("data-folded", folded[decodeURIComponent(link.hash.slice(1))] === true);
      });
    }
    if (!FOLDS) return;
    try {
      var ids = Object.keys(folded);
      if (ids.length) localStorage.setItem(FOLDS, JSON.stringify(ids));
      else localStorage.removeItem(FOLDS);
    } catch (e) {}
  }

  // Folding changes what is on the page above and below; hold on to what was being read.
  // If that is now folded away, its heading is the nearest thing to it.
  function foldKeepingPlace(change) {
    var line = readingLine();
    var held = null;
    blocks.some(function (block) {
      if (block.el.getBoundingClientRect().bottom <= line) return false;
      held = block.el;
      return true;
    });
    var before = held && held.getBoundingClientRect().top;
    change();
    applyFolds();
    if (held) {
      var hider = hiderOf(held);
      holdBar = Date.now() + 600;
      if (hider) hider.el.scrollIntoView({ block: "start", behavior: "instant" });
      else window.scrollBy({ top: held.getBoundingClientRect().top - before, behavior: "instant" });
      lastY = window.scrollY;
    }
    leaveTurns();
    updatePager();
  }

  // Opens whatever keeps a link's target out of sight, and the target's own section.
  function unfoldFor(target) {
    if (!blocks.length || !doc.contains(target)) return false;
    var changed = false;
    for (var hider = hiderOf(target); hider; hider = hiderOf(target)) {
      delete folded[hider.el.id];
      changed = true;
    }
    if (folded[target.id]) {
      delete folded[target.id];
      changed = true;
    }
    if (changed) {
      applyFolds();
      leaveTurns();
    }
    return changed;
  }

  function hashTarget(hash) {
    try {
      return hash.length > 1 ? document.getElementById(decodeURIComponent(hash.slice(1))) : null;
    } catch (e) {
      return null;
    }
  }

  if (headingBlocks().length) {
    headingBlocks().forEach(function (block) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "fold";
      button.setAttribute("aria-label", "Fold or unfold this section");
      block.el.prepend(button);
    });
    try {
      ((FOLDS && JSON.parse(localStorage.getItem(FOLDS))) || []).forEach(function (id) {
        var heading = document.getElementById(id);
        if (heading && heading.querySelector(":scope > .fold")) folded[id] = true;
      });
    } catch (e) {}
    applyFolds();

    doc.addEventListener("click", function (event) {
      var button = event.target.closest("button.fold");
      if (!button) return;
      var id = button.parentNode.id;
      foldKeepingPlace(function () {
        if (folded[id]) delete folded[id];
        else folded[id] = true;
      });
    });

    // Before the browser jumps to it: a target that is folded away has nowhere to be.
    document.addEventListener("click", function (event) {
      var link = event.target.closest && event.target.closest("a[href]");
      if (!link || link.pathname !== location.pathname || link.search !== location.search) return;
      var target = hashTarget(link.hash);
      if (target) unfoldFor(target);
    });
    var showHashTarget = function () {
      var target = hashTarget(location.hash);
      if (target && unfoldFor(target)) target.scrollIntoView({ block: "start", behavior: "instant" });
    };
    window.addEventListener("hashchange", showHashTarget);
    showHashTarget();

    var foldAll = toc && toc.querySelector("[data-folds]");
    if (foldAll) {
      foldAll.hidden = false;
      foldAll.addEventListener("click", function (event) {
        var button = event.target.closest("[data-fold-all]");
        if (!button) return;
        var headings = headingBlocks();
        // A lone h1 is the title: folding it would leave nothing but the title.
        var titles = headings.filter(function (block) {
          return block.level === 1;
        });
        foldKeepingPlace(function () {
          folded = {};
          if (button.dataset.foldAll !== "true") return;
          headings.forEach(function (block) {
            if (block.level > 1 || titles.length > 1) folded[block.el.id] = true;
          });
        });
        markCurrentHeading(toc);
      });
    }
  }

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

  // ---- Notes and highlights ----
  // A mark is a stretch of the page's text, kept as the words themselves, a little of what
  // stands either side of them and the cell they are in, so that it is found again after
  // the notebook has changed around it. One whose words are gone is kept and not shown.
  // Marks are painted over the text (the CSS highlight API) and the page's elements are
  // left as they are, so folding, the reading position and the page turns do not notice.
  //
  // A mark is made with the pen in the top bar: while that is switched on, whatever is
  // selected is marked. A page cannot add to the menu a device shows for a selection, nor
  // tell which side of the selection it will be on, so nothing is offered there. A tap on
  // a mark shows its note and what can be done with it.

  var CONTEXT = 32;
  var LONGEST_MARK = 2000;
  // Text that is not the document's: put there by this script or by the renderer (the
  // pilcrow that links to a heading), or said twice for a reader.
  var NOT_MARKED = "button, summary, .cell-n, .stream-tools, .anchor-link, .katex-mathml";

  // The document's text as one string, and where each piece of it is on the page.
  function textModel() {
    var model = { text: "", nodes: [], starts: [], index: new Map(), spans: {} };
    var pieces = [];
    var length = 0;
    Array.prototype.forEach.call(cells(), function (cell) {
      var span = { start: length, end: length };
      var walker = document.createTreeWalker(cell, NodeFilter.SHOW_TEXT);
      for (var node = walker.nextNode(); node; node = walker.nextNode()) {
        if (node.parentElement.closest(NOT_MARKED)) continue;
        model.index.set(node, model.nodes.length);
        model.nodes.push(node);
        model.starts.push(length);
        pieces.push(node.data);
        length += node.data.length;
      }
      span.end = length;
      if (!(cell.id in model.spans)) model.spans[cell.id] = span;
    });
    model.text = pieces.join("");
    return model;
  }

  function offsetOf(model, container, offset) {
    var known = model.index.get(container);
    if (known !== undefined) return model.starts[known] + Math.min(offset, container.length);
    // Not inside a piece of the text: the first piece that begins at or after this point.
    var point = document.createRange();
    point.setStart(container, offset);
    point.collapse(true);
    var low = 0;
    var high = model.nodes.length;
    while (low < high) {
      var middle = (low + high) >> 1;
      if (point.comparePoint(model.nodes[middle], 0) >= 0) high = middle;
      else low = middle + 1;
    }
    return low < model.nodes.length ? model.starts[low] : model.text.length;
  }

  // The last piece that begins at or before this offset; for the end of a stretch, before it.
  function pieceAt(model, offset, forEnd) {
    var low = 0;
    var high = model.nodes.length - 1;
    while (low < high) {
      var middle = (low + high + 1) >> 1;
      if (forEnd ? model.starts[middle] < offset : model.starts[middle] <= offset) low = middle;
      else high = middle - 1;
    }
    return low;
  }

  function rangeFor(model, start, end) {
    var first = pieceAt(model, start, false);
    var last = pieceAt(model, end, true);
    var range = document.createRange();
    range.setStart(model.nodes[first], start - model.starts[first]);
    range.setEnd(model.nodes[last], end - model.starts[last]);
    return range;
  }

  // What to keep of a selection, or nothing if it holds none of the document's text.
  function describe(range) {
    var model = textModel();
    var start = offsetOf(model, range.startContainer, range.startOffset);
    var end = offsetOf(model, range.endContainer, range.endOffset);
    while (start < end && /\s/.test(model.text.charAt(start))) start += 1;
    while (end > start && /\s/.test(model.text.charAt(end - 1))) end -= 1;
    if (end <= start) return null;
    var cell = model.nodes[pieceAt(model, start, false)].parentElement.closest("main.doc > .cell");
    return {
      cell: cell.id,
      start: start - model.spans[cell.id].start,
      quote: model.text.slice(start, end),
      prefix: model.text.slice(Math.max(0, start - CONTEXT), start),
      suffix: model.text.slice(end, end + CONTEXT),
    };
  }

  // Where a mark's words are now, or -1. In its own cell first, where the words alone are
  // enough; anywhere else only if what stood beside them is there too.
  function locate(model, mark) {
    var quote = mark.quote;
    function agreement(at) {
      var before = mark.prefix && model.text.slice(Math.max(0, at - mark.prefix.length), at);
      var after = mark.suffix && model.text.substr(at + quote.length, mark.suffix.length);
      return (before === mark.prefix ? 1 : 0) + (after === mark.suffix ? 1 : 0);
    }
    function best(from, to, wanted, least) {
      var found = -1;
      var agreed = least - 1;
      for (var at = model.text.indexOf(quote, from); at >= 0 && at < to; at = model.text.indexOf(quote, at + 1)) {
        var agrees = agreement(at);
        var nearer = Math.abs(at - wanted) < Math.abs(found - wanted);
        if (agrees > agreed || (agrees === agreed && found >= 0 && nearer)) {
          found = at;
          agreed = agrees;
        }
      }
      return found;
    }
    var span = model.spans[mark.cell];
    var at = span ? best(span.start, span.end, span.start + mark.start, 0) : -1;
    return at >= 0 ? at : best(0, model.text.length, 0, mark.prefix || mark.suffix ? 1 : 0);
  }

  if (canMark) {
    // Where this document's marks are kept: the server writes them to a file beside it.
    var NOTES = "/_notes" + location.pathname;
    var marks = [];
    var rev = "";
    // The marks that are on the page, each with where it is, in reading order.
    var painted = [];

    var paint = function () {
      var plain = new Highlight();
      var noted = new Highlight();
      painted = [];
      if (marks.length) {
        var model = textModel();
        marks.forEach(function (mark) {
          var at = locate(model, mark);
          if (at < 0) return;
          var range = rangeFor(model, at, at + mark.quote.length);
          (mark.note ? noted : plain).add(range);
          painted.push({ mark: mark, range: range, at: at });
        });
        painted.sort(function (a, b) {
          return a.at - b.at;
        });
      }
      CSS.highlights.set("lectern-mark", plain);
      CSS.highlights.set("lectern-note", noted);
      listButton.hidden = !marks.length;
    };

    // ---- Keeping them ----
    // The whole list is sent each time, with the version it was changed from. If another
    // device has saved since, the server sends back what it has instead, and what was
    // changed here is made again on top of that: `changes` holds every mark added or
    // edited (and `null` for one removed) that the server has not yet taken.

    var changes = {};
    var sending = false;
    var retry = 0;

    var withChanges = function (list, made) {
      var out = list.filter(function (mark) {
        return !(mark.id in made);
      });
      Object.keys(made).forEach(function (id) {
        if (made[id]) out.push(made[id]);
      });
      return out;
    };

    var send = function () {
      clearTimeout(retry);
      if (sending || !Object.keys(changes).length) return;
      sending = true;
      var sent = changes;
      changes = {};
      var failed = function (again) {
        // Still wanted, unless changed again since.
        Object.keys(sent).forEach(function (id) {
          if (!(id in changes)) changes[id] = sent[id];
        });
        sending = false;
        pen.toggleAttribute("data-unsaved", true);
        if (again) retry = setTimeout(send, again);
      };
      fetch(NOTES, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rev: rev, notes: marks }),
      }).then(
        function (response) {
          if (response.status !== 200 && response.status !== 409) {
            // Refused, not unreachable: asking again would get the same answer.
            failed(response.status >= 500 ? 5000 : 0);
            return null;
          }
          return response.json().then(function (kept) {
            rev = kept.rev;
            if (response.status === 409) {
              marks = withChanges(withChanges(kept.notes, sent), changes);
              paint();
              failed(1);
              return;
            }
            sending = false;
            pen.removeAttribute("data-unsaved");
            send();
          });
        },
        function () {
          failed(5000);
        }
      );
    };

    var marksChanged = function (mark, removed) {
      var change = {};
      change[mark.id] = removed ? null : mark;
      // By id: the list may have been replaced since whoever is asking was handed the mark.
      marks = withChanges(marks, change);
      changes[mark.id] = change[mark.id];
      paint();
      send();
    };

    var fetchMarks = function () {
      return fetch(NOTES, { cache: "no-store" }).then(function (response) {
        return response.ok ? response.json() : Promise.reject(new Error(response.status));
      });
    };

    var addMark = function (found, note) {
      var now = new Date().toISOString();
      found.id = Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
      found.note = note || "";
      found.created = now;
      found.updated = now;
      marksChanged(found);
    };

    var removeMark = function (mark) {
      marksChanged(mark, true);
    };

    var lastBox = function (range) {
      var boxes = range.getClientRects();
      return boxes.length ? boxes[boxes.length - 1] : range.getBoundingClientRect();
    };

    // The last mark drawn at this point of the screen, with the line of it that was hit.
    var markAt = function (x, y) {
      for (var i = painted.length - 1; i >= 0; i -= 1) {
        var boxes = painted[i].range.getClientRects();
        for (var j = 0; j < boxes.length; j += 1) {
          var box = boxes[j];
          if (box.left <= x && x <= box.right && box.top <= y && y <= box.bottom) {
            return { mark: painted[i].mark, box: box };
          }
        }
      }
      return null;
    };

    // ---- The card beside a mark that was tapped ----
    // It is part of the page, not of the screen, so it scrolls away with what it belongs to.

    var pop = document.createElement("div");
    pop.className = "mark-pop";
    pop.hidden = true;
    document.body.appendChild(pop);
    var coarse = window.matchMedia("(pointer: coarse)").matches;

    var hidePop = function () {
      pop.hidden = true;
    };

    var showPop = function (box, text, actions) {
      pop.textContent = "";
      if (text) {
        var words = document.createElement("p");
        words.textContent = text;
        pop.appendChild(words);
      }
      if (actions.length) {
        var row = document.createElement("div");
        row.className = "mark-actions";
        actions.forEach(function (action) {
          var button = toolButton(action.label);
          button.addEventListener("click", action.act);
          row.appendChild(button);
        });
        pop.appendChild(row);
      }
      pop.style.left = "0px";
      pop.hidden = false;
      var gap = coarse ? 14 : 8;
      var floor = window.innerHeight - (pager ? pager.offsetHeight : 0);
      var top = box.bottom + gap;
      if (top + pop.offsetHeight > floor) {
        top = Math.max(bar.offsetHeight + 4, box.top - gap - pop.offsetHeight);
      }
      var left = box.left + box.width / 2 - pop.offsetWidth / 2;
      left = Math.max(8, Math.min(left, root.clientWidth - pop.offsetWidth - 8));
      pop.style.top = window.scrollY + top + "px";
      pop.style.left = window.scrollX + left + "px";
    };

    pop.addEventListener("click", function (event) {
      event.preventDefault();
    });

    // ---- Writing a note ----

    var editing = null;
    var editor = document.createElement("dialog");
    editor.className = "note-editor";
    editor.setAttribute("aria-label", "Note");
    editor.innerHTML =
      '<form method="dialog"><blockquote></blockquote>' +
      '<textarea aria-label="Your note" placeholder="Note"></textarea>' +
      '<div class="note-actions"><button value="cancel">Cancel</button>' +
      '<button value="save">Save</button></div></form>';
    document.body.appendChild(editor);
    editor.addEventListener("close", function () {
      var mark = editing;
      editing = null;
      if (!mark || editor.returnValue !== "save") return;
      mark.note = editor.querySelector("textarea").value.trim();
      mark.updated = new Date().toISOString();
      marksChanged(mark);
    });

    var editNote = function (mark) {
      editing = mark;
      editor.returnValue = "";
      var quote = mark.quote.length > 200 ? mark.quote.slice(0, 200) + "…" : mark.quote;
      editor.querySelector("blockquote").textContent = quote;
      editor.querySelector("textarea").value = mark.note || "";
      editor.showModal();
    };

    // ---- Marking: with the pen in the top bar switched on, what is selected is marked ----

    var settling = 0;
    var pointerDown = false;

    var selectionSettled = function () {
      if (!root.hasAttribute("data-marking") || document.querySelector("dialog[open]")) return;
      var selection = window.getSelection();
      var range = selection.rangeCount && !selection.isCollapsed ? selection.getRangeAt(0) : null;
      var found = range && range.intersectsNode(doc) ? describe(range) : null;
      if (!found) return;
      // Not while it is still being dragged out.
      if (pointerDown) {
        settling = setTimeout(selectionSettled, 300);
        return;
      }
      if (found.quote.length > LONGEST_MARK) showPop(lastBox(range), "Too much to mark at once.", []);
      else addMark(found);
      selection.removeAllRanges();
    };

    document.addEventListener("selectionchange", function () {
      clearTimeout(settling);
      settling = setTimeout(selectionSettled, 800);
    });
    document.addEventListener("pointerdown", function () {
      pointerDown = true;
    });
    ["pointerup", "pointercancel", "touchend"].forEach(function (name) {
      document.addEventListener(name, function () {
        pointerDown = false;
      });
    });

    var pen = document.createElement("button");
    pen.type = "button";
    pen.className = "bar-button mark-pen";
    pen.hidden = true;
    pen.setAttribute("aria-label", "Mark what is selected");
    pen.setAttribute("aria-pressed", "false");
    pen.innerHTML =
      '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M4 20l1-4L16 5l3 3L8 19zM14 7l3 3" ' +
      'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    bar.querySelector("[data-open='settings']").before(pen);
    pen.addEventListener("click", function () {
      pen.setAttribute("aria-pressed", root.toggleAttribute("data-marking"));
      // Not saved, and the server may be back: a tap here is also a way of trying again.
      send();
    });

    // ---- A tap on a mark ----

    var showMark = function (hit) {
      var mark = hit.mark;
      showPop(hit.box, mark.note, [
        {
          label: mark.note ? "Edit note" : "Add note",
          act: function () {
            hidePop();
            editNote(mark);
          },
        },
        {
          label: "Remove",
          act: function () {
            hidePop();
            removeMark(mark);
          },
        },
      ]);
    };

    var dismissed = null;
    document.addEventListener(
      "click",
      function (event) {
        if (!pop.hidden && !pop.contains(event.target)) {
          hidePop();
          dismissed = event;
        }
      },
      true
    );
    doc.addEventListener("click", function (event) {
      if (event.defaultPrevented) return;
      // Anything that does something of its own keeps its tap, marked or not.
      if (event.target.closest("a, button, summary, input")) return;
      var hit = String(window.getSelection()) ? null : markAt(event.clientX, event.clientY);
      if (hit) showMark(hit);
      // Nor does the tap that puts the card away do anything more, such as turn the page.
      if (hit || dismissed === event) event.preventDefault();
    });

    // ---- The list of what is marked ----
    // In reading order, each a way to its place; then the marks whose words are no longer
    // in the document, which have no place to go to and can only be read or removed.

    var listButton = document.createElement("button");
    listButton.type = "button";
    listButton.className = "bar-button mark-list";
    listButton.hidden = true;
    listButton.setAttribute("aria-label", "Notes");
    listButton.innerHTML =
      '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M6 4h9l3 3v13H6zM9 10h6M9 14h6" ' +
      'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    pen.before(listButton);

    var list = document.createElement("dialog");
    list.className = "sheet";
    list.id = "notes";
    list.setAttribute("aria-label", "Notes");
    list.innerHTML =
      '<div class="sheet-panel" tabindex="-1" autofocus><header class="sheet-head"><h2>Notes</h2>' +
      '<button type="button" data-close>Done</button></header><div class="notes"></div></div>';
    document.body.appendChild(list);

    var goToMark = function (range) {
      var place = range.startContainer.parentElement;
      unfoldFor(place);
      // Code that is folded away, and output cut to its first lines.
      for (var shut = place.closest("details:not([open])"); shut; shut = place.closest("details:not([open])")) {
        shut.open = true;
      }
      var clamped = place.closest("pre.clamped");
      if (clamped) clamped.classList.remove("clamped");
      holdBar = Date.now() + 600;
      var top = window.scrollY + range.getBoundingClientRect().top - readingLine() - 2 * lineHeight();
      window.scrollTo({ top: top, behavior: "instant" });
      lastY = window.scrollY;
      leaveTurns();
      updatePager();
    };

    var listEntry = function (mark, range) {
      var entry = document.createElement(range ? "a" : "div");
      entry.className = "noted";
      var quote = document.createElement("q");
      quote.textContent = mark.quote.length > 160 ? mark.quote.slice(0, 160) + "…" : mark.quote;
      entry.appendChild(quote);
      if (mark.note) {
        var note = document.createElement("span");
        note.textContent = mark.note;
        entry.appendChild(note);
      }
      if (range) {
        entry.href = "#";
        entry.addEventListener("click", function (event) {
          event.preventDefault();
          list.close();
          goToMark(range);
        });
      } else {
        var remove = toolButton("Remove");
        remove.addEventListener("click", function () {
          removeMark(mark);
          showList();
        });
        entry.appendChild(remove);
      }
      return entry;
    };

    var showList = function () {
      var body = list.querySelector(".notes");
      body.textContent = "";
      painted.forEach(function (found) {
        body.appendChild(listEntry(found.mark, found.range));
      });
      var lost = marks.filter(function (mark) {
        return !painted.some(function (found) {
          return found.mark === mark;
        });
      });
      if (lost.length) {
        var heading = document.createElement("h3");
        heading.textContent = "No longer in the text";
        body.appendChild(heading);
        lost.forEach(function (mark) {
          body.appendChild(listEntry(mark, null));
        });
      }
      if (!marks.length) list.close();
    };

    listButton.addEventListener("click", function () {
      hidePop();
      showList();
      openSheet(list);
    });
    list.addEventListener("click", function (event) {
      if (event.target === list || event.target.closest("[data-close]")) list.close();
    });

    // ---- Starting ----
    // The marks are asked for after the page is up, and the pen appears when they arrive.
    // A server that keeps no notes says so here, and then there is nothing to mark with.

    // What the trial of this kept in the browser, taken along once.
    var TRIAL = "lectern:notes:" + doc.dataset.path;

    fetchMarks()
      .then(function (kept) {
        rev = kept.rev;
        marks = kept.notes;
        pen.hidden = false;
        try {
          (JSON.parse(localStorage.getItem(TRIAL)) || []).forEach(function (mark) {
            var known = marks.some(function (other) {
              return other.id === mark.id;
            });
            if (known || !mark.id || !mark.quote) return;
            marks.push(mark);
            changes[mark.id] = mark;
          });
          localStorage.removeItem(TRIAL);
        } catch (e) {}
        paint();
        send();
      })
      .catch(function () {});

    // Coming back to the page: what another device has marked since, unless something
    // here is still waiting to be saved.
    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState !== "visible" || pen.hidden) return;
      if (sending || Object.keys(changes).length) {
        send();
        return;
      }
      fetchMarks()
        .then(function (kept) {
          if (kept.rev === rev || sending || Object.keys(changes).length) return;
          rev = kept.rev;
          marks = kept.notes;
          hidePop();
          paint();
        })
        .catch(function () {});
    });
  }

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
    // A markdown file is one cell, and that cell has no id.
    var cell = place.cell ? document.getElementById(place.cell) : doc && cells()[0];
    if (!cell) return;
    holdBar = Date.now() + 600;
    // A place inside a folded section: its heading is as near as the page gets.
    var hider = cell.classList.contains("folded-away") && hiderOf(cell);
    if (hider) {
      hider.el.scrollIntoView({ block: "start", behavior: "instant" });
      lastY = window.scrollY;
      return;
    }
    var box = cell.getBoundingClientRect();
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
