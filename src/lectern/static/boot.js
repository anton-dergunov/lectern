// Runs before first paint, so a saved theme or text size never flashes in after the page.
// Preferences are per device: localStorage belongs to this origin on this browser.
(function () {
  "use strict";

  var KEY = "lectern:prefs";
  var DEFAULTS = { family: "solarized", mode: "light", size: 19, width: "m", hideCode: false };
  // The page background of each theme, for the browser and status bar around the page.
  var BAR_COLORS = {
    "solarized-light": "#fdf6e3",
    "solarized-dark": "#002b36",
    "plain-light": "#ffffff",
    "plain-dark": "#000000",
  };
  var SIZE = { min: 14, max: 26 };
  var dark = window.matchMedia("(prefers-color-scheme: dark)");

  function read() {
    var saved = {};
    try {
      saved = JSON.parse(localStorage.getItem(KEY)) || {};
    } catch (e) {}
    var prefs = {};
    for (var name in DEFAULTS) {
      prefs[name] = typeof saved[name] === typeof DEFAULTS[name] ? saved[name] : DEFAULTS[name];
    }
    if (!BAR_COLORS[prefs.family + "-light"]) prefs.family = DEFAULTS.family;
    if (["light", "dark", "system"].indexOf(prefs.mode) < 0) prefs.mode = DEFAULTS.mode;
    if (["n", "m", "w"].indexOf(prefs.width) < 0) prefs.width = DEFAULTS.width;
    prefs.size = Math.min(SIZE.max, Math.max(SIZE.min, Math.round(prefs.size)));
    return prefs;
  }

  function apply(prefs) {
    var root = document.documentElement;
    var mode = prefs.mode === "system" ? (dark.matches ? "dark" : "light") : prefs.mode;
    var theme = prefs.family + "-" + mode;
    root.dataset.theme = theme;
    root.dataset.width = prefs.width;
    root.style.setProperty("--size", prefs.size + "px");
    root.toggleAttribute("data-hide-code", prefs.hideCode);
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = BAR_COLORS[theme];
  }

  var prefs = read();
  apply(prefs);

  window.lectern = {
    prefs: prefs,
    size: SIZE,
    set: function (name, value) {
      prefs[name] = value;
      try {
        localStorage.setItem(KEY, JSON.stringify(prefs));
      } catch (e) {}
      apply(prefs);
    },
  };

  dark.addEventListener("change", function () {
    apply(prefs);
  });
})();
