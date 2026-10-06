// Runs before first paint, so a saved theme or text size never flashes in after the page.
// Preferences are per device: localStorage belongs to this origin on this browser.
(function () {
  "use strict";

  var KEY = "lectern:prefs";
  var DEFAULTS = {
    family: "solarized",
    mode: "light",
    size: 19,
    width: "m",
    hideCode: false,
    follow: false,
  };
  // The page background of each theme, for the browser and status bar around the page.
  var BAR_COLORS = {
    "solarized-light": "#fdf6e3",
    "solarized-dark": "#002b36",
    "plain-light": "#ffffff",
    "plain-dark": "#000000",
    eink: "#ffffff",
  };
  var FAMILIES = ["solarized", "plain", "eink"];
  var WIDTHS = ["n", "m", "w", "x", "f"];
  // Reading devices whose browsers say who they are; the rest are caught by the media query.
  var EINK_DEVICE = /\b(BOOX|Onyx|Kindle|Kobo|PocketBook|reMarkable|Bigme|Meebook|Likebook|Boyue)\b/i;
  var SIZE = { min: 14, max: 26 };
  var dark = window.matchMedia("(prefers-color-scheme: dark)");

  // What a device starts with before anything is chosen on it. The same 19px that suits a
  // tablet held in the hands is large on a 13-inch e-ink reader, a phone and a monitor.
  function deviceDefaults() {
    var defaults = {};
    for (var name in DEFAULTS) defaults[name] = DEFAULTS[name];
    // A published site can name the colours it wants to open in.
    var family = document.documentElement.dataset.defaultFamily;
    if (family) defaults.family = family;
    var eink = EINK_DEVICE.test(navigator.userAgent) || window.matchMedia("(monochrome)").matches;
    var phone = Math.min(screen.width, screen.height) < 500;
    var desktop = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
    if (eink) {
      defaults.family = "eink";
      defaults.size = 16;
    } else if (phone) {
      defaults.size = 16;
    } else if (desktop) {
      defaults.size = 17;
      defaults.width = "w";
    }
    return defaults;
  }

  function read() {
    var saved = null;
    try {
      saved = JSON.parse(localStorage.getItem(KEY));
    } catch (e) {}
    if (!saved || typeof saved !== "object") saved = {};
    var defaults = deviceDefaults();
    var prefs = {};
    for (var name in DEFAULTS) {
      prefs[name] = typeof saved[name] === typeof DEFAULTS[name] ? saved[name] : defaults[name];
    }
    if (FAMILIES.indexOf(prefs.family) < 0) prefs.family = DEFAULTS.family;
    if (["light", "dark", "system"].indexOf(prefs.mode) < 0) prefs.mode = DEFAULTS.mode;
    if (WIDTHS.indexOf(prefs.width) < 0) prefs.width = DEFAULTS.width;
    prefs.size = Math.min(SIZE.max, Math.max(SIZE.min, Math.round(prefs.size)));
    return prefs;
  }

  function apply(prefs) {
    var root = document.documentElement;
    var mode = prefs.mode === "system" ? (dark.matches ? "dark" : "light") : prefs.mode;
    // E-ink has one look; light and dark do not apply to it.
    var theme = prefs.family === "eink" ? "eink" : prefs.family + "-" + mode;
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
