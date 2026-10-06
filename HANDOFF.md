# Lectern: handoff for a tablet notebook reader

## State on 2026-10-06

**All seven milestones are built.** What is below this section is the original design, kept as the record of what was planned; where the build differs is listed first. Work from here on comes from `docs/tasks/plan.md` and from Anton's use.

Anton has read with lectern on the iPad (11 inch), the desktop (a 49-inch ultrawide), an Android phone and the e-ink tablet, an **Onyx Boox Tab X C** (13 inch, colour e-ink). His spoken feedback is in `/Users/anton/tmp-spoken-plans/jupylab/feedback.txt`, `feedback2.txt` and `feedback3.txt`; all of it is folded in. The repository is public at `anton-dergunov/lectern`, tagged `v0.1.0` (milestones 1 to 4) and `v0.2.0` (through milestone 6).

**Published:** `https://anton-dergunov.github.io/ml-explorations/` is built by lectern `v0.2.0` from that repository's Pages workflow.

**Milestone 7, the cleanup, is done in the working trees and uncommitted, for Anton to commit:**

- **agent-memory-eval:** `jupyter-lab-qr.sh`, `jupyter-qr.sh`, `voila-qr.sh` and `custom.css` are deleted (each matched the last commit, so git has them), and the README has a "Reading on a tablet" section. Its notebooks are still gitignored, so it has no Pages build. Its two modified `.gitignore` files are Anton's and were left alone.
- **ml-explorations:** `tools/build_site.py` is deleted, the README's preview command names `v0.2.0`, and `lectern.toml` no longer excludes the `tools` directory that is gone.
- **Saved folders on this Mac** (`~/.config/lectern/config.toml`): agent-memory-eval, ml-explorations, long-tail-multi-label-classification and blog-code, so `lectern serve --all` serves the four. Checked on `127.0.0.1`. **The login agent is not installed**; that is Anton's to switch on.

**Not tried by anyone:** the Tailscale route in the README; the agent listening on the network (it was run on `127.0.0.1` only); milestones 5 and 6 on the tablets. Pages for long-tail-multi-label-classification and blog-code would each need the workflow from ml-explorations and a short `lectern.toml`.

Where the build differs from the design below (the design text is left as written):

Rendering and server:

- **Template:** `classic/base.html.j2` wraps cells, inputs and outputs in classic-notebook `div`s, so the reader template reaches past it with `super.super()` for `codecell`, `output_group`, `output` and `error`, and writes every leaf block itself. Classic's `conf.json` also enables `CSSHTMLHeaderPreprocessor`; the reader's `conf.json` disables it.
- **Output priority:** the widget and javascript MIME types are removed from `display_data_priority`, so such an output falls back to its HTML, image or text form instead of rendering as nothing.
- **IPython is a dependency**, only for the `ipython3` Pygments lexer; without it nbconvert warns and highlights magics as errors.
- **Host check:** any IP literal is accepted (a rebinding attack needs a hostname), plus `localhost` and `<LocalHostName>.local`. No list of LAN IPs to keep current.
- **Tables:** every table is wrapped and classified in one pass after rendering (`render/document.py`), so markdown pipe tables get the same treatment as pandas ones. Numeric cells get `class="num"`. The sticky header row is not done: it cannot stick inside a horizontally scrolling wrapper.
- **`Rendered` has no `summary`;** the listing takes it from `library.describe()`.
- **Display math is a `<span class="math display">`**, not a `div`: the markdown parser puts it inside a `<p>`.
- **Listing:** the "Recently changed" strip appears only above ten documents. Every markdown row names its file, and a folder's README comes first.
- **`/` is a start page, not the listing.** It is served cacheable for a year and decides in the browser: if `/_ping` answers it goes on to `/_home` (the listing, or the list of roots), otherwise it says "Lectern is not running" and retries every two seconds. `/_ping` reports the asset hash so a stale cached start page refreshes itself.

Reading (milestone 2 and the feedback):

- **Five themes, not two:** Solarized light and dark, black-and-white light and dark, plus "Follow system", and E-ink. Stored as `family` (`solarized`, `plain`, `eink`) and `mode`; `data-theme` is `solarized-light`, `solarized-dark`, `plain-light`, `plain-dark` or `eink`. This replaces decision 9's pair.
- **E-ink (milestone 3):** pure black on white with borders instead of tints, syntax told apart by weight, slant and underline, body weight 500, no transitions or animations, the top bar fixed in place, and code wrapped instead of scrolled sideways. A footer turns pages (Previous, "3 / 29", Next); so do taps on the left and right 30% of the screen and PageUp, PageDown, the arrow keys and space. A page turn is the screen height less the bar, the footer and two lines, applied instantly. First visit picks the theme from the user agent (BOOX, Onyx, Kindle, Kobo, PocketBook and others) or `(monochrome)`. Follow-changes does not exist yet, so there is nothing to hide for it.
- **Text size is a pixel stepper** (14 to 26, default 19), not S/M/L/XL; everything else is in rem and follows.
- **One column width for everything, in pixels.** Prose, code, outputs and tables share the column; the design's wider code (to fit 88 columns unscrolled) looked unbalanced to Anton, as it does not in VS Code. The width is a setting with five steps: narrow 600px, medium 700px, wide 820px, wider 1040px, full. It was in rem at first, which made the text-size setting change the column too; Anton read that as a bug, so the column is now independent of the text size. At medium, 14px code fits about 80 characters and longer lines scroll inside their block. A step is offered only if the one before it is under 92% of the screen, so steps that change nothing or next to nothing are left out, and on a phone the whole setting is hidden.
- **First-visit defaults depend on the device** (`boot.js`): e-ink 16px, a phone 16px, a desktop (hover and a fine pointer) 17px and wide, anything else (a tablet) 19px and medium. These are Anton's preferences on his four devices. A device keeps what it has once any setting is changed on it.
- **Cell numbers:** each code cell shows `[n]`, its execution count, or `#n` when it was never run, where n counts code cells only (the first code cell is 1 whatever precedes it, as a run from the top would number it). Markdown cells are not numbered. In the left margin where the screen has one, otherwise beside Show/Hide.
- **Top bar** hides while scrolling down and returns on scrolling up.
- **Link guard:** every in-app link first asks `/_ping`; with the server gone the page stays and shows the "not running" screen instead of navigating into a failed load, which is what sent the Home Screen app into a reload loop.
- **Stream clamp and wrap toggle are added by `reader.js`**, not rendered by the server: above 60 lines the first 30 show; "No wrap" appears when a line is over 100 characters. Without script all lines show.
- **Contents** is a side sheet listing h1 to h3, with the current section marked when it opens.
- **Not done from the design's milestone 2 list:** nothing. Extra: `scripts/check_reader.py` covers more than position restore.
- **Fonts are bundled** for systems without the Apple ones: Charis SIL (drawn from Charter) for text, JetBrains Mono for code, Inter for the interface, Latin subsets as woff2 in `static/fonts`, about 200 KB. The stacks name Charter, SF Mono and the Apple system font first, so an iPad or Mac never fetches them. This came from Anton finding the type on Android less good than on the iPad, and it also answers milestone 3's open question about fonts on the Boox, pending his look at it.

Math and richer outputs (milestone 5):

- **KaTeX 0.19 is vendored** in `static/vendor/katex` (script, stylesheet, woff2 fonts only) and added to a page only when its render has math; `reader.js` typesets each `.math` element before anything measures the page and leaves the TeX source where typesetting fails. A `text/latex` output keeps its `$` delimiters in the HTML and loses them in the script. A static build copies KaTeX only if some page has math.
- **Interactive outputs** (plotly, widgets, bokeh, vega-lite) keep only their saved picture when the output has one; otherwise a short note takes the output's place. The same note replaces an HTML output that was nothing but a script, and any output with no form the reader shows. A widget's text `repr` is no longer shown. The note has no link to JupyterLab: `lectern lab` does not exist yet and a published site has no Lab to link to.
- **Tracebacks** are built by the `error_html` filter: the line naming the error is bold and in the error colour, and above 25 lines the traceback is folded under that line.
- `render/document.py`, `templates/shell.html.j2`, `scripts/_local.py` and `scripts/check_reader.py` are new; `config.py`, `lab.py`, `agent.py` do not exist yet.

Static build (milestone 4):

- **Markdown is built only when a notebook links to it** (followed through other markdown), not every `.md` in the tree: the first build of ml-explorations published `README.md` and an untracked `CLAUDE.md`. `markdown = "all"` or `"none"` in `lectern.toml`, or `--markdown`, changes that.
- **Links to files that are in the source but not on the site** (scripts, data) go to the repository's `blob/<branch>/` URL when a repository is known; otherwise they are left as written.
- **The index has no dates and no "Recently changed"**: in a CI checkout every file has the same date. Directory headings are not links, since only the one index is written.
- **Assets are at `_static/` with `?v=<hash>`** on each URL, not in a hashed directory.
- **`--clean` only empties a directory that holds an earlier build** (it looks for `_static/reader.css`); anything else is refused. The output may be inside the source and is never built into itself.
- **Two documents that would become the same page** (`x.ipynb` and `x.md`, or a root `index.md` against the index): the notebook or the index wins and the other is reported as skipped.
- **`include` and `exclude` are `fnmatch` patterns** on the path from the source root; `*` crosses directories, so `tools/*` covers everything under `tools`.
- **`--theme`** is `solarized`, `plain` or `eink`: the colours a first-time visitor gets. The reader's settings work on the built site as they do when served.
- The link guard and the start page are server-only; a built page carries `data-static` and skips them. The CSP is a `<meta>` there, and built pages were checked to load their own scripts and styles from `file://` under it.
- Ruff is told to skip `*.md` and `tests/fixtures`: its formatter rewrites Python snippets in this file and the code cells of fixture notebooks.

Launch polish (milestone 6):

- **`lectern add` / `remove` / `list`** edit `~/.config/lectern/config.toml` (`LECTERN_CONFIG_DIR` moves it, for tests). `list` is an addition to the design.
- **`serve --all` follows the file**: `ReaderServer.roots` is a property that looks at the file's mtime at most once a second. A file that does not parse leaves the served folders as they were. `extra_hosts` is followed the same way. A server started with paths does not follow it.
- **Zero folders is a valid state** (`serve --all` or the agent before anything is added); the front page says to run `lectern add`.
- **Reuse:** `lectern serve` asks `127.0.0.1:<port>/_ping` first. For a caller on the loopback address `/_ping` also returns each root's path and whether the server follows the settings file; other devices get names only. If lectern answers, the command prints the deep address for a folder inside a served root, or how to get it served, and exits 0.
- **Agent:** label `com.anton.lectern`, `serve --all`, `RunAtLoad`, `KeepAlive` on unsuccessful exit only (it exits 0 when it finds lectern already running), log in `~/Library/Logs/lectern.log`. `--host` is an addition, so it can be kept to the Mac. No firewall prompt appeared when it was run on `127.0.0.1`; on `0.0.0.0` that is untested.
- **Lab:** as section 11, with `--port` and `--host` added. Three `local_hostnames` are passed (the `.local` name as given and lowercased, and `localhost`). Checked live: `/login` 200, `/lab` redirects to the login, `/api/contents` 403, a foreign Host 403. JupyterLab logs that `ServerApp.password_required` in the user's own config is a deprecated spelling; that is his file, not ours. **The JupyterLab from the old script is still running on port 8888** (PID 40924 when checked), started with a token; `lectern lab` on the default port will fail until it is stopped.
- **`--qr`** prints the code before the addresses, so the addresses are what stays on screen.
- **Follow changes** is a reload, not a swap of `<main>`: every two seconds, while the page is visible, a `HEAD` compares the ETag, and a change saves the reading position and reloads. Simpler than re-running every enhancement on swapped content, and the place is kept either way. Off by default; the setting is absent in the e-ink theme and on built sites.

Found by Anton reading the fixtures on the iPad and the Boox (version 0.2.1):

- **Raw HTML in markdown was being broken by nbconvert.** With `embed_images` on, its renderer parses each raw-HTML block and inline tag by itself and writes it back, which closes whatever was open: `<details>` lost its content and `<b>` its text. `ReaderMarkdownRenderer._html_embed_images` now only rewrites the `src` of `<img>` tags and leaves the rest of the HTML untouched.
- **The fixture image was a truncated 2×2 PNG** written by hand; viewers decoded it differently and it showed as a dot at its own size. `make_fixtures.py` now generates a valid 320×200 PNG.
- **The bar names the file** after the folders, and it is the part that shortens when the bar is narrow.
- **Typeset display math hides its scrollbar.** Anton saw a grey strip under the last formula on the Boox, most likely the bar Android draws when a formula is a pixel wider than the column. Not confirmed on the device.
- An output with both a script and HTML form (the `javascript` fixture) shows its HTML where VS Code runs the script; that difference is intended.

After Anton set up Tailscale and read on the Boox (version 0.2.2):

- **Anton uses the Tailscale route** (`tailscale serve --bg --https=443 http://127.0.0.1:8642`), on the Boox at least. With lectern stopped, Tailscale's proxy answers 502 and Chrome showed its own "This page isn't working".
- **A service worker now covers that.** `/_sw.js` is `static/sw.js` with the asset hash and the list of files the "not running" page needs filled in. Browsers run it only on HTTPS or localhost. Navigations go to the network first; no answer, or a 5xx without the `X-Lectern` header that every lectern response now carries, gets the cached `/_offline` page, which is the start page's template with no `home`: it waits for `/_ping` and then loads the address it was shown for. Nothing else is cached or intercepted except `/_static/` as a fallback. On plain `http://….local` there is no service worker and the long-cached start page keeps doing the cold-start job.
- **The "not running" screen** has the icon, a "Try again" button, and retries at once when the page becomes visible again (background timers are throttled, which is the likely reason it sometimes did not recover by itself).
- **E-ink pager:** a "Top" button; a button that has nowhere to go is blank instead of struck through, which read as an error. Scrollbars of streams, tables and code are hidden in the e-ink theme (they showed as a grey strip that stays on the screen). Anton confirmed the strip under math is gone.
- **Kept as it is, after Anton asked:** the top bar stays fixed in the e-ink theme. He does sometimes scroll by finger there, but hiding and showing the bar is a repaint each time and would change the height a page turn has to cover; it costs 44px on a 13-inch screen. And the e-ink theme stays black on white for text, ANSI colours included, although the Boox has colour: pictures and SVG keep their colours, which is where colour carries information.
- **Fixtures have distinct pictures now:** `png` is a five-colour bar chart, `plotly-with-picture` carries real plotly data and a matching three-bar picture, `attachment` keeps the blue panel. Anton had taken three identical placeholder panels for a rendering bug.

Things to know when continuing:

- **Cold start with the server stopped works** in Chromium and, by Anton's test, in the Home Screen app on the iPad: the cached start page says lectern is not running. WebKit under Playwright does not use its cache for that page, so `check_reader.py` reports it as a note there instead of a failure.
- **The e-ink tablet is an Onyx Boox Tab X C.** Anton found the e-ink theme clearly the best on it even though the screen has colour. Not yet reported from it: whether the theme was picked by itself on first visit, whether Add to Home Screen gives full screen over plain http or the Tailscale HTTPS route is needed (decision 12), whether fonts should be bundled, and how the page turning feels. He noted the cell numbers look slightly less good on Android than on iOS and macOS; they now have a 10.5px floor, which may or may not be what he saw.
- A dropped connection used to print a traceback over the launch summary; `ReaderServer.handle_error` now ignores connection errors unless `--verbose`.
- agent-memory-eval has a `private/` directory with a markdown file in it. `lectern serve` in that repo lists and serves it to the network like any other document. Nothing in the design excludes it; an ignore list is a possible addition.
- Many of the notebooks' relative links point at `docs/…` and `papers/…` files that are not in the repo, so they lead to the 404 page.
- A Pygments token class is `.n`; do not reuse short class names inside `.highlight`.
- Headless Chrome gives a blank screenshot for a URL with a `#fragment`; use `scripts/shots.py` instead.

The original spoken brief is at `/Users/anton/tmp-spoken-plans/jupylab/tablet-use.txt`.

---

## 1. The need

Anton reads Jupyter notebooks on tablets rather than at the laptop: an iPad held in portrait (Chrome is the default browser, Safari available) and an Android e-ink tablet with no camera. Notebooks live on his Mac laptops (several, one in use at a time) and are served over trusted home Wi-Fi. For him a notebook is a readable document: explanation, code, saved outputs. He always commits outputs and treats jupytext `.py` files as generated. He mostly reads; running a cell is an occasional nice-to-have.

Wanted: full screen with no browser chrome, no token typing, no dependence on a QR code, Solarized Light, typography worth investing in, no wasted prompt gutter, reusable across repos, later extensible to markdown and PDF. He also wants uncommitted notebooks readable (the existing GitHub Pages route only covers committed ones).

Problems with today's setup that he named: launch script output scrolls the QR off screen; QR opens Chrome not Safari; the installed web app opened a wrong directory; e-ink tablet cannot scan; JupyterLab nested menus close on tap; touch scrolling selects cells and shows the blue selection bar; the Solarized Light theme extension does not work; VS Code tunnel and Sidecar cannot scroll notebooks by touch.

## 2. Decisions (settled; do not re-open without a reason)

| # | Decision | Why |
|---|---|---|
| 1 | Primary deliverable is a **read-only HTML reader**: a small local server that lists a directory tree and renders `.ipynb` from saved outputs, executing nothing. | No maintained tool does this; plain HTML has no touch bugs; reusable for commit-time publishing. |
| 2 | The reader runs with **no token**. | It cannot execute code. Exposure is limited to reading notebooks and markdown under the served roots. |
| 3 | **JupyterLab is a thin backup** for the rare "run a cell" case, and keeps its **password** (typed once per device), never tokenless. | A tokenless Jupyter server lets any device that reaches the port run code as Anton. `~/.jupyter` is already password-only. |
| 4 | **VS Code on the tablet is dropped.** | vscode#126212 (notebook touch scroll) closed as not planned. |
| 5 | Name **lectern**, at `/Users/anton/projects/tools/lectern`, **public** GitHub repo `anton-dergunov/lectern`. | Chosen by Anton. Public lets other repos' workflows install it by git URL. |
| 6 | Rendering uses **nbconvert's `HTMLExporter` with our own template**, producing a body fragment; our own page shell and CSS. | Keeps MIME priority, ANSI, images, attachments, math-safe markdown for free; drops 300 KB of JupyterLab CSS. |
| 7 | Server is **stdlib `ThreadingHTTPServer`**, GET/HEAD only. | Six routes, two devices; live reload can be ETag polling. |
| 8 | Stable origin: **fixed port 8642** and the Mac's Bonjour name. | A home-screen icon is pinned to scheme + host + port. |
| 9 | Two themes: **Solarized Light** (default) and a **high-contrast e-ink** theme, chosen per device. | Solarized body text is about 4–5:1 contrast, too low for e-ink. |
| 10 | The same core provides a **static `build` command** replacing `ml-explorations/tools/build_site.py`. | One mechanism for committed and uncommitted notebooks. |
| 11 | Launch **on demand** first (`lectern serve`); always-on LaunchAgent in a later milestone. | Try on-demand for a while before adding a daemon. |
| 12 | E-ink full-screen route (Tailscale HTTPS versus plain shortcut) is **decided at the e-ink milestone** on the device. | Chosen by Anton. |

Easy to revisit after seeing it: serif versus sans body, base01 versus base00 body colour, port 8642, Lab port 8888.

## 3. Findings: agent-memory-eval (`/Users/anton/projects/writing/agent-memory-eval`)

- One commit (`3127920`), no remote. Tracked: `.gitignore`, `README.md`, `custom.css`, `docs/*.md`, three `*-qr.sh` scripts, `notebooks/.gitignore`.
- Uncommitted: a `notebooks/` line moved from `notebooks/.gitignore` to the root `.gitignore`, which now ignores the whole directory (all four `.ipynb`, their `.py` twins, `notebooks/README.md`, `notebooks/pyproject.toml`). `notebooks/README.md` claims the `.py` is "the version in git"; that is not true today. Leave this alone unless asked.
- **Launch scripts** (root, executable):
  - `jupyter-lab-qr.sh`: hard-codes `$HOME/Library/Python/3.14/bin/jupyter-lab`; LAN IP from `ipconfig getifaddr en0` then `en1`; fresh `secrets.token_urlsafe(32)` per launch; `qrencode -t ANSIUTF8`; `--ip=0.0.0.0 --port=8888 --no-browser --notebook-dir="$(pwd)" --ServerApp.token="$TOKEN"`.
  - `jupyter-qr.sh`: same preamble, classic `jupyter notebook`.
  - `voila-qr.sh [notebook] [port=8866]`: same preamble, Voilà (which re-executes the notebook).
- `custom.css` (134 lines): Solarized Light for classic Notebook v6 selectors (`#notebook-container`, `.rendered_html`, `.CodeMirror`). Palette comment lines 6–13; CodeMirror token colours lines 41–60; prompt gutter narrowed lines 71–79; tablet block `@media (max-width: 1024px)` lines 117–134 (code 15px/1.5, prose 16px/1.6). Reuse the palette and syntax mapping; the selectors are obsolete.
- `~/.jupyter/custom/custom.css` (4195 B): a separate JupyterLab 4 rewrite using `--jp-*` variables. Source of the rule colour `#d9d2c5`.
- `~/.jupyter/jupyter_server_config.py` lines 1880–1888: `ServerApp.ip = "0.0.0.0"`, port 8888, `open_browser = False`, `token = ""`, `password_required = True`. `~/.jupyter/jupyter_server_config.json` holds `IdentityProvider.hashed_password`. So Lab is already password-only; only the script's `--ServerApp.token` flag overrides it.
- Lab theme setting: `~/.jupyter/lab/user-settings/@jupyterlab/apputils-extension/themes.jupyterlab-settings` = "JupyterLab Solarized Light" (from `jupyterlab_theme_solarized_light` 3.0.1, which Anton says does not work).
- **JupyterLab is running now** on port 8888 (PID 40924 at the time of writing, started from `jupyter-lab-qr.sh`). Do not kill it without asking.
- **Notebooks** in `notebooks/` (nbformat 4.5, kernelspec `aci-notebooks`, Python 3.12.9):

  | Notebook | Size | md / code cells | Outputs |
  |---|---|---|---|
  | `mem0-intuition.ipynb` | 49.7 KB | 16 / 14 | 13 stdout, 4 HTML tables |
  | `zep-graphiti-intuition.ipynb` | 79.6 KB | 23 / 19 | 17 stdout, 7 HTML tables |
  | `letta-intuition.ipynb` | 84.3 KB | 24 / 20 | 22 stdout, 1 HTML table |
  | `neuromancer-intuition.ipynb` | 92.6 KB | 31 / 19 | 17 stdout, 8 HTML tables |

  - Stdout has no ANSI; longest lines 277 / 470 / 390 / 190 characters, prose-like.
  - Every `text/html` output is a pandas DataFrame: `<table border="1" class="dataframe">` preceded by `<style scoped>`; several have long prose cells. Each has a `text/plain` fallback.
  - Markdown has pipe tables (1–2 per notebook); fenced code only in neuromancer.
  - Absent: images, math, widgets, plotly, scripts, stderr, errors.
  - The notebooks contain **27 relative links to `.md` files and 6 to their paired `.py` files**, so markdown rendering and link rewriting are needed from milestone 1.
  - `letta-intuition.ipynb` has outputs but no `execution_count` values (harmless; do not rely on counts).
- jupytext: per-file `formats: py:percent,ipynb`, plain `<name>.py` twins; no `jupytext.toml`.
- `notebooks/pyproject.toml` (`aci-notebooks`, `requires-python >=3.11`) declares jupytext and ipykernel, not jupyterlab or nbconvert. No `.venv` exists in the repo.
- No `CLAUDE.md`, `Makefile` or `justfile`. Nothing documents tablet reading.

## 4. Findings: ml-explorations (`/Users/anton/projects/experiments/ml-explorations`)

- `.github/workflows/pages.yml` (50 lines): on push to `main` and `workflow_dispatch`; `setup-python` 3.12; `pip install nbconvert` (unpinned); `python tools/build_site.py`; `configure-pages@v5`, `upload-pages-artifact@v3` with `path: _site`; separate `deploy` job with `deploy-pages@v4`. Permissions `contents: read`, `pages: write`, `id-token: write`. One run so far (2026-09-03, success).
- `tools/build_site.py` (173 lines, stdlib):
  - Constants lines 20–25: `ROOT`, `SITE = ROOT / "_site"`, `SKIP_DIRS = {"_site", "tools", ".git", ".github", ".vscode", "node_modules"}`, `REPO_SLUG = os.environ.get("GITHUB_REPOSITORY", "anton-dergunov/ml-explorations")`, `BRANCH = os.environ.get("GITHUB_REF_NAME", "main")`.
  - `discover()` lines 40–47: `ROOT.rglob("*.ipynb")` sorted, skipping dot-prefixed parts and `SKIP_DIRS`.
  - `describe()` lines 50–72: title from the first markdown line starting `# `, summary from the first paragraph under it, fallback to the stem. **Port this.**
  - `render()` lines 75–88: `python -m nbconvert --to html --output-dir … --output <stem>.html <nb>` (default `lab` template).
  - `INDEX_CSS` lines 91–116, `write_index()` lines 119–147: one `<article>` card per notebook with "Read the write-up" and "Notebook on GitHub" links; title and lede hard-coded ("ML Explorations").
  - `main()` lines 150–169: wipes `_site`, touches `.nojekyll`, renders serially.
- Published at `https://anton-dergunov.github.io/ml-explorations/`, Pages `build_type: workflow`, public. `_site/` is gitignored.
- Output today (`_site/mem0-intuition/mem0-intuition.html`): 351 KB for a 49 KB notebook, JupyterLab Light, 14px text, prompt gutter kept, no wide-table scrolling, output lines broken mid-token (`word-break: break-all`), MathJax 2.7.7 and require.js from cdnjs, `<title>` is the file stem, no table of contents, no dark or Solarized theme.
- jupytext here uses `jupytext.toml` with `formats = "ipynb,.nb.py:percent"`; `*.nb.py` gitignored; `.ipynb` is the committed source. `CLAUDE.md` there says never strip outputs and never run `jupytext --sync`.
- README lines 68–76 and `CLAUDE.md` lines 73–81 are the "Publishing" sections to update; README line 75 holds the preview command.
- Other repos with notebooks and no rendering: `experiments/long-tail-multi-label-classification` (`notebooks/task.ipynb`, 308 KB, one `image/png`; git, no remote), `experiments/reuters-task` (not a git repo), `writing/blog-code` (`2024-07-maximal-marginal-relevance/maximal_marginal_relevance.ipynb`, 5 markdown cells with math; GitHub remote). Across all seven notebooks surveyed: no ANSI, attachments, widgets or plotly.

## 5. Findings: machine and conventions

- macOS; Homebrew Python 3.14.7; `uv` at `/opt/homebrew/bin/uv`; `qrencode` at `/opt/homebrew/bin/qrencode`.
- User-site packages (`~/Library/Python/3.14`): nbconvert 7.17.1, nbformat 5.10.4, mistune 3.3.2, Pygments 2.20.0 (ships `solarized-light`), jupyterlab 4.6.1, jupyter_server 2.20.0, jupytext 1.19.4, voila 0.5.13.
- Bonjour name: `Antons-MacBook-Air-13` (so `http://Antons-MacBook-Air-13.local:8642/`); LAN IP was 192.168.1.101.
- Ports free when checked: 8642, 8787, 8800, 8866, 8889. Port 8888 in use by JupyterLab.
- Headless Chrome 154 at `/Applications/Google Chrome.app`. Playwright browser builds cached in `~/Library/Caches/ms-playwright` (chromium, headless shell, webkit) but no Python `playwright` package installed.
- Tailscale installed and logged in (`/usr/local/bin/tailscale`); tailnet has two Macs and two iPads, no Android device; no serve config.
- LaunchAgent precedent: `com.anton.micguard` (from `tools/mic-guard/build.sh`).
- `/Users/anton/projects/tools` conventions (model: `agent-context-pipeline`): own git repo, `src/<package>/`, `tests/`, uv with `pyproject.toml` + `uv.lock` + `.python-version`, `[project.scripts]`, MIT (`Copyright (c) 2026 Anton Dergunov`), `CLAUDE.md`, `.github/workflows` for checks, README sections "What it does / Why it exists / How it works / Install / usage / License and credits".

### nbconvert internals (verified on this machine)

- Templates live under `~/Library/Python/3.14/share/jupyter/nbconvert/templates` and `/opt/homebrew/share/jupyter/nbconvert/templates`: `base`, `basic`, `classic`, `lab`, others.
- `base` has no `conf.json` or `index.html.j2`; only `null.j2`, `display_priority.j2`, `mathjax.html.j2`, `celltags.j2`, `cell_id_anchor.j2`, `jupyter_widgets.html.j2`.
- `basic/index.html.j2` is one line: `{%- extends 'classic/base.html.j2' -%}`. So the minimal parent to extend is **`classic/base.html.j2`**, which emits HTML fragments with no CSS.
- Blocks in `null.j2`: `header`, `body`, `body_header`, `body_loop`, `any_cell`, `codecell`, `input_group`, `in_prompt`, `input`, `output_group`, `output_prompt`, `outputs`, `output`, `execute_result`, `stream`, `stream_stdout`, `stream_stderr`, `stream_stdin`, `display_data`, `data_priority`, `error`, `traceback_line`, `markdowncell`, `rawcell`, `unknowncell`, `body_footer`, `footer`.
- Blocks in `display_priority.j2`: `data_pdf`, `data_svg`, `data_png`, `data_html`, `data_markdown`, `data_jpg`, `data_text`, `data_latex`, `data_mermaid`, `data_javascript`, `data_widget_view`, `data_native`, `data_other`.
- `classic/base.html.j2` fills the `data_*` blocks, `error`, `traceback_line`, streams (via `ansi2html`), and a `footer` that emits widget state; adds `empty_in_prompt`, `output_area_prompt`.
- Markdown: `HTMLExporter.markdown2html` at `nbconvert/exporters/html.py:246` builds `IPythonRenderer` and runs `MarkdownWithMath` (`nbconvert/filters/markdown_mistune.py`) on mistune with plugins `strikethrough`, `table`, `url`, `task_lists`, `def_list`; footnotes off. Pipe tables render. `$x_1$` and `$$…$$` pass through intact with delimiters kept as text. Fenced code becomes Pygments `<div class="highlight">`.
- Headings get `id` plus a `¶` anchor; `exclude_anchor_links=True` removes the id too, so keep anchors and hide `¶` in CSS.
- `sanitize_html=True` strips pandas `<style scoped>` and keeps `class="dataframe"` (not used; we clean tables ourselves).
- `CSSHTMLHeaderPreprocessor.style="solarized-light"` gives 5 KB of CSS (not used; we map tokens to theme variables).
- Prototype result: fragment 145 KB for `letta-intuition.ipynb` versus 437 KB with `lab`; 0.2–0.55 s per notebook including a 301 KB one.

## 6. Research facts (as of 2026-10-06)

**Prior art.** No maintained "browse a folder, tap a notebook, polished mobile page" tool. nbviewer `--localfiles` is desktop-oriented and its PyPI release dates from 2017; Voilà re-executes and hides source; Quarto and Jupyter Book are project builds; `dongweiming/Ipynb-viewer` abandoned in 2015.

**JupyterLab on touch.**
- [jupyterlab#19124](https://github.com/jupyterlab/jupyterlab/issues/19124): menu and context-menu items cannot be selected on touchscreens since 4.6.0; open. Fix merged in [lumino#834](https://github.com/jupyterlab/lumino/pull/834) on 2026-07-16; release status not verified.
- [jupyterlab#18279](https://github.com/jupyterlab/jupyterlab/issues/18279): involuntary scroll on tapping code cells on Android Chrome, open; also affects Notebook 7.3+.
- No tracked issue found for "touch scroll selects a cell" or the blue selection bar.
- Solarized Light for Lab 4: `a-lew/jupyterlab-theme-solarized-light` (0 stars, last push 2024-11, not on PyPI); `eco32i` fork (pushed 2026-06); upstream `AllanChain/jupyterlab-theme-solarized-dark` is dark only. Alternative is `--custom-css` with `~/.jupyter/custom/custom.css` (JupyterLab ≥ 4.1).

**jupyter-server 2.x option names.** `IdentityProvider.token`, `PasswordIdentityProvider.hashed_password`, `PasswordIdentityProvider.password_required`, `ServerApp.ip`, `ServerApp.port`, `ServerApp.port_retries` (0 for a fixed port), `ServerApp.root_dir`, `ServerApp.local_hostnames` (allows a `.local` name while keeping the Host check; `allow_remote_access=True` would disable it). `ServerApp.token` / `ServerApp.password` are deprecated spellings.

**VS Code.** [vscode#126212](https://github.com/microsoft/vscode/issues/126212) closed as not planned 2024-12-11; mobile Safari meta-issue [#85254](https://github.com/microsoft/vscode/issues/85254) in backlog since 2019.

**Full screen.**
- iPadOS 26: every site added to the Home Screen from Safari opens as a web app by default; no manifest or `apple-mobile-web-app-capable` needed ([WebKit, Safari 26.0](https://webkit.org/blog/17333/webkit-features-in-safari-26-0/)). No HTTPS requirement documented; behaviour over http on a `.local` name is likely but unverified. Adding from Chrome on iPad is unverified, so install from Safari.
- Android Chrome: standalone install needs a manifest (`name`, 192 and 512 icons, `start_url`, `display`) **and** trusted HTTPS or localhost ([MDN](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable)). Plain http on a LAN gives a shortcut that opens a tab. Self-signed certificates do not help.
- Android 12+ resolves `.local` mDNS names system-wide; whether the e-ink tablet's firmware does is unverified.
- `tailscale serve` gives a trusted HTTPS `*.ts.net` name with no root-certificate install; needs Tailscale on the tablet. mkcert needs the root installed and trusted on each device.

**E-ink.** Remove animations, transitions and smooth scrolling; prefer page steps to continuous scroll; maximise contrast, heavier weights. Onyx Boox's bundled browser is repackaged Chrome; standalone install support unverified.

**nbconvert options.** `TemplateExporter.extra_template_basedirs`, `exclude_input_prompt`, `exclude_output_prompt`, `HTMLExporter.embed_images`, `exclude_anchor_links`, `mathjax_url`, `sanitize_html`. Default templates load MathJax, require.js and jQuery from cdnjs (we load none). Plotly output saved with only the plotly MIME type renders blank in static HTML; widgets render only with saved state and never run callbacks.

## 7. Rendering design

### Exporter (`src/lectern/render/notebook.py`)

- `ReaderExporter(HTMLExporter)`: `exclude_input_prompt=True`, `exclude_output_prompt=True`, `exclude_anchor_links=False`, `embed_images=True`, `template_name="reader"`, `extra_template_basedirs=[<package>/templates]`.
- Disable `CSSHTMLHeaderPreprocessor`; ship `static/pygments.css` with token classes mapped to theme variables so switching theme recolours code.
- Override `markdown2html` to use `ReaderMarkdownRenderer(IPythonRenderer)` whose `inline_math`, `block_math`, `latex_environment` emit `<span class="math inline">` / `<div class="math display">` with escaped TeX. `has_math` is then exact and KaTeX only touches those elements (never `$` in stdout).
- Filters registered: `clean_table_html`, `stream_lines`.
- One exporter instance behind a `threading.Lock`.
- `render_notebook(path) -> Rendered(fragment, toc, title, summary, has_math)`.

### Template (`src/lectern/templates/reader/`)

`conf.json`: `{"base_template": "classic", "mimetypes": {"text/html": true}}`. `index.html.j2` extends `classic/base.html.j2`, overriding `codecell`, `input_group`, `in_prompt` (empty), `input`, `output_group`, `output`, `markdowncell`, `stream_stdout`, `stream_stderr`, `error`, `data_html`, `data_latex`, `data_javascript` (empty), `data_widget_view`, `footer` (empty).

### Page structure (`templates/page.html.j2`, shared with listings and markdown)

```
<html data-theme data-size>
<head> meta, manifest, boot.js (blocking, external), reader.css </head>
<body>
 <header class="bar">  back · breadcrumb · contents button · settings button
 <nav id="toc" hidden>  h1–h3 list
 <main class="doc" data-path data-mtime>
   <section class="cell md" id="c-<cellid>"> …prose… </section>
   <section class="cell code" id="c-<cellid>">
     <details class="src" open><summary>Code · N lines</summary><div class="highlight"><pre>…</pre></div></details>
     <div class="out"> <pre class="stream wrap">…</pre> | <div class="table-wrap">…</div> | <figure class="img">…</figure> | <pre class="error">…</pre> </div>
   </section>
 </main>
 <footer class="pager">  e-ink only: Prev · "3 / 17" · Next
```

### Per type

- **Markdown cells:** prose column at the reading measure. `render/links.py` rewrites relative links: `X.py` → `X.ipynb` when the pair exists; `.md` stays in the reader; external links get `target="_blank" rel="noopener"`.
- **Code cells:** no gutter. `<details class="src">` open up to 30 lines, collapsed above; summary is the first comment line or "Code · 84 lines". Per-device "Hide all code".
- **Streams:** wrap by default (`white-space: pre-wrap; overflow-wrap: anywhere`), since the lines are prose-like and panning sideways in portrait is worse. `stream_lines` wraps each line in `<span class="l">` with a hanging indent so continuations are visible. Per-block "No wrap" toggle switches to horizontal scroll. Over 60 lines: clamp with "Show all N lines". stderr gets a thin left rule.
- **pandas tables:** `clean_table_html` (BeautifulSoup) drops `<style scoped>` and `border="1"`, wraps in `<div class="table-wrap">` (`overflow-x: auto`), and classifies: any cell over 60 characters → `prose-table` (cells wrap, `min-width: 12ch`, top-aligned); otherwise `data-table` (nowrap, tabular numerals, numbers right-aligned). Sticky header row.
- **Images:** `<figure class="img">`, `max-width: 100%; height: auto`; png/jpeg as data URIs; SVG through `<img>` data URI so embedded scripts cannot run.
- **Errors:** `<pre class="error">` via `ansi2html`, red left rule, last line (`ename: evalue`) bold, collapsed above 25 lines.
- **Math:** KaTeX vendored in `static/vendor/katex/`; the shell adds its CSS/JS only when the fragment contains `class="math`. `text/latex` outputs use the same wrapper. Failed render shows the TeX source.
- **plotly / widgets:** use the bundle's `image/png` if present, otherwise a placeholder card "Interactive output, open in JupyterLab" linking to the Lab port. `application/javascript` is never emitted.
- **Contents:** `render/toc.py` extracts h1–h3 and de-duplicates ids.
- **Title:** first h1, falling back to the stem.
- **Reading position:** `localStorage["lectern:pos:"+path] = {cell, frac, mtime}`, anchored to cell id plus fractional offset (survives font-size changes). `history.scrollRestoration = "manual"`; restore after fonts load.
- **CSP:** `default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'`, as a header when serving and a `<meta>` in static builds.

## 8. Look

### Tokens (`static/reader.css`, `static/themes.css`)

`--bg`, `--bg-alt`, `--fg`, `--fg-strong`, `--fg-muted`, `--rule`, `--link`, `--accent`, `--code-fg`, `--err`; syntax `--syn-kw`, `--syn-str`, `--syn-num`, `--syn-com`, `--syn-fn`, `--syn-builtin`, `--syn-op`; type `--font-body`, `--font-code`, `--size`, `--leading`, `--measure`.

### Solarized Light

| Token | Value | Note |
|---|---|---|
| `--bg` | base3 `#fdf6e3` | |
| `--bg-alt` | base2 `#eee8d5` | code background, as in `custom.css` |
| `--fg` | base01 `#586e75` | 4.99:1; base00 `#657b83` is 4.13:1 |
| `--fg-strong` | base02 `#073642` | 12:1; headings and bold |
| `--fg-muted` | base1 `#93a1a1` | 2.48:1; metadata only |
| `--rule` | `#d9d2c5` | from `~/.jupyter/custom/custom.css` |
| `--link` | blue `#268bd2` | 3.41:1, so always underlined |
| `--code-fg` | base01 | base00 is 3.64:1 on base2 |
| `--err` | red `#dc322f` | |

Syntax, following the CodeMirror mapping in `custom.css`: keywords green `#859900`, strings and numbers cyan `#2aa198`, definitions blue `#268bd2`, builtins magenta `#d33682`, comments base1 italic, operators base00, inline code orange `#cb4b16` on base2.

### E-ink theme

`--bg #fff`, `--fg #000`, `--bg-alt #fff` with a 1px black border on code; syntax black, distinguished by weight and italics; links underlined black; body and code weight 500; `*{transition:none!important;animation:none!important;scroll-behavior:auto!important}`; no shadows or translucency; pager footer visible; tap zones and PageDown/PageUp step by `innerHeight` minus two lines, instantly.

### Fonts and sizes

- System stacks in milestone 1, no webfonts. Body `Charter, "Iowan Old Style", ui-serif, "Noto Serif", Georgia, serif`; code `ui-monospace, "SF Mono", Menlo, "Roboto Mono", "Noto Sans Mono", monospace`; UI `system-ui`.
- E-ink milestone: consider bundling one OFL text family and one mono as local woff2 referenced only by the e-ink theme (`@font-face` loads lazily, so the iPad never fetches them).
- For an 820 px portrait viewport: body 19px / 1.6; `--measure: 36rem` (about 70–75 characters), centred; code, outputs and tables break out to viewport minus 16 px padding; code 14px (88 columns fit unscrolled); streams 13.5px; h1 1.9rem, h2 1.4rem, h3 1.15rem; paragraph spacing 0.9em.
- Font-size steps S/M/L/XL = 17/19/21/23 px via `data-size`.

### Preferences without a flash

`localStorage["lectern:prefs"] = {theme, size, hideCode, follow}` (per device because per origin). `static/boot.js` is a small blocking external script in `<head>` that sets `data-theme` and `data-size` on `<html>` before first paint and updates `<meta name="theme-color">`. First visit: e-ink vendor user agent or `matchMedia("(monochrome)")` → `eink`, else `solarized`.

## 9. Server (`src/lectern/server/app.py`, handler `ReaderHandler`)

| Route | Purpose |
|---|---|
| `GET /` | Roots, plus "Continue reading" filled client-side from saved positions |
| `GET /<root>/<dir>/` | Directory listing |
| `GET /<root>/<path>.ipynb` | Rendered notebook |
| `GET /<root>/<path>.md` | Rendered markdown |
| `GET /<root>/<path>.<img>` | Raw image for relative references |
| `GET /_static/<hash>/<file>` | Assets, immutable caching |
| `GET /manifest.webmanifest` | Manifest |
| `GET /_ping` | `{"app":"lectern","version":…,"roots":[…]}` |

Other methods → 405. URLs are always `/<root-name>/<relative path>` so bookmarks and saved positions survive across launch modes.

- **Listing (`library.py`):** `discover(root)` walks with `os.scandir`, pruning dot-directories and `SKIP_DIRS` (`_site`, `node_modules`, `.venv`, `venv`, `__pycache__`, `.ipynb_checkpoints`, `dist`, `build`). Shows `.ipynb` and `.md`, and only directories containing one; hides a `.py` paired with a sibling `.ipynb`. `describe(path)` ported from `build_site.py`, cached by mtime, plus mtime and reading-time estimate. Tree order as the body with a "Recently changed" strip of five on top; notebooks as cards, markdown as compact rows.
- **Cache (`cache.py`):** in-memory LRU of 64, key `(realpath, st_mtime_ns, st_size, RENDER_VERSION)`, value fragment + toc + title + `has_math`. ETag from the key plus asset hash; `If-None-Match` → 304. No disk cache.
- **Path safety (`paths.py`, `resolve(root, rel)`):** reject NUL, backslash, and any component starting with `.`; `Path.resolve()` and require `is_relative_to(root.resolve())` (blocks symlink escape); extension allow-list `.ipynb .md .png .jpg .jpeg .gif .webp .svg`, everything else 404 (including `.py`, `.env`, `.json`, `.csv`). Host header allow-list: `<LocalHostName>.local`, LAN IPs, `localhost`, `127.0.0.1`, config `extra_hosts`; otherwise 421 (blocks DNS rebinding).
- **Mid-save or invalid notebook:** on `JSONDecodeError` or missing `cells`, retry once after 150 ms; then serve the previous render with a banner if there is one; otherwise a 503 page with `Retry-After: 2`.
- **Follow file changes:** off by default, per device. When on and the tab is visible, `reader.js` sends `HEAD` every 2 s, compares ETag, and on change fetches and swaps `<main>` keeping position by cell id. Hidden in the e-ink theme (full-panel refresh, ghosting, radio kept awake).

## 10. Launching, config, full screen

- One code path: `serve(roots: dict[str, Path], host, port)`.
- `lectern serve [PATH…]`: given paths or the current directory; root name is the directory basename. `lectern serve --all`: roots from config.
- If the port already answers `/_ping` as lectern, do not start a second server: print the deep URL if the directory is under a served root, otherwise suggest `lectern add .`.
- `lectern add PATH` / `lectern remove NAME` edit the config; the running server re-reads config when its mtime changes (no mutating HTTP endpoint).
- `lectern agent install|uninstall|status`: `~/Library/LaunchAgents/com.anton.lectern.plist`, `RunAtLoad`, `KeepAlive` with `SuccessfulExit=false`, log to `~/Library/Logs/lectern.log`, `ProgramArguments` = absolute path of the uv tool shim. Later milestone.
- Config `~/.config/lectern/config.toml` (stdlib `tomllib` to read, small hand-written emitter to write; directory derived from one `APP_NAME` constant):

  ```toml
  port = 8642
  lab_port = 8888
  extra_hosts = []            # e.g. the ts.net name
  [roots]
  agent-memory-eval = "~/projects/writing/agent-memory-eval"
  ml-explorations   = "~/projects/experiments/ml-explorations"
  ```

- Terminal summary (`netinfo.py`: `scutil --get LocalHostName`, `ipconfig getifaddr en0` then `en1`):

  ```
  lectern  serving agent-memory-eval (4 notebooks, 31 docs)
    http://Antons-MacBook-Air-13.local:8642/
    http://192.168.1.101:8642/        (fallback)
  ```

  `--qr` pipes the URL to `qrencode -t ANSIUTF8` if present. No Python QR dependency.

- Head tags:

  ```html
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-title" content="Lectern">
  <meta name="apple-mobile-web-app-status-bar-style" content="default">
  <meta name="theme-color" content="#fdf6e3">
  <link rel="manifest" href="/manifest.webmanifest">
  <link rel="apple-touch-icon" sizes="180x180" href="/_static/icons/apple-touch-icon.png">
  <link rel="icon" type="image/svg+xml" href="/_static/icons/icon.svg">
  ```

  Status bar style `default`, not `black-translucent` (white text on a light page is unreadable).
- Manifest: `name`, `short_name`, `start_url: "/"`, `scope: "/"`, `display: "standalone"`, `background_color` and `theme_color` `#fdf6e3`, icons 192, 512, maskable 512. Draw `icon.svg` once, rasterise with headless Chrome, commit the PNGs.
- In-app: bar and pager use `env(safe-area-inset-*)`; sticky top bar with a back chevron (`history.back()`, or parent directory with no history) and tappable breadcrumb; auto-hides on scroll down in Solarized, static in e-ink.
- iPad install: open the URL once in **Safari**, Share → Add to Home Screen.
- Android: optional `tailscale serve --bg --https=443 http://127.0.0.1:8642` with the ts.net name in `extra_hosts`; decided at milestone 3.

## 11. Static build, Lab backup, project layout, integration

### `lectern build`

```
lectern build [SRC=.] -o _site [--title T] [--description D] [--repo-url URL] [--branch B]
              [--theme solarized] [--include GLOB]… [--exclude GLOB]… [--clean]
```

Same `render_notebook()` and `page.html.j2` with `mode="static"`: relative asset URLs, CSP as meta, no follow toggle. Output `_site/<path>.html`, assets once in `_site/_static/`, `.nojekyll`; links between notebooks rewritten `.ipynb` → `.html`. Index from the listing template with "Read" and "Notebook on GitHub" links when the repo URL is known. Value precedence: flags → `lectern.toml` at the source root → `GITHUB_REPOSITORY` / `GITHUB_REF_NAME` → directory name.

```toml
# ml-explorations/lectern.toml
title = "ML Explorations"
description = "Small self-contained experiments, each one written up as a notebook and rendered here with the outputs it actually produced."
exclude = ["tools/**"]
```

Replacement build steps in `ml-explorations/.github/workflows/pages.yml` (deploy job unchanged):

```yaml
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - name: Render notebooks
        run: uvx --from "git+https://github.com/anton-dergunov/lectern@v0.1.0" lectern build . -o _site
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with: { path: _site }
```

### `lectern lab [DIR=.]` (`lab.py`)

1. Read `~/.jupyter/jupyter_server_config.json`; if `IdentityProvider.hashed_password` is missing, exit with "run `jupyter server password` first".
2. Find the binary: `DIR/.venv/bin/jupyter-lab`, `DIR/notebooks/.venv/bin/jupyter-lab`, `lab_command` from config, `shutil.which("jupyter-lab")`.
3. `exec`:

   ```
   jupyter-lab --no-browser \
     --ServerApp.ip=0.0.0.0 --ServerApp.port=8888 --ServerApp.port_retries=0 \
     --ServerApp.root_dir="$DIR" \
     --IdentityProvider.token='' --PasswordIdentityProvider.password_required=True \
     --ServerApp.local_hostnames="<LocalHostName>.local" \
     --custom-css
   ```

Prints `http://<name>.local:8888/lab`. No change to `~/.jupyter`. Cookie lifetime and survival across restarts are unverified.

### Layout

```
/Users/anton/projects/tools/lectern/
  pyproject.toml  uv.lock  .python-version (3.13)  LICENSE (MIT)  README.md  CLAUDE.md  .gitignore  HANDOFF.md
  .github/workflows/checks.yml          # uv sync --locked; pytest on 3.12 and 3.13; ruff check + format --check
  src/lectern/
    __init__.py  __main__.py  cli.py  config.py  netinfo.py  library.py  paths.py  cache.py  lab.py  agent.py  build.py
    render/__init__.py  notebook.py  markdown.py  filters.py  links.py  toc.py  page.py
    server/__init__.py  app.py
    templates/reader/conf.json  templates/reader/index.html.j2
    templates/page.html.j2  templates/listing.html.j2  templates/error.html.j2
    static/reader.css  themes.css  pygments.css  boot.js  reader.js  manifest.webmanifest
    static/icons/…  static/vendor/katex/…
  scripts/shots.py  scripts/make_fixtures.py
  tests/conftest.py  tests/fixtures/*.ipynb  tests/golden/*.html
  tests/test_render.py  test_filters.py  test_links.py  test_toc.py  test_library.py
  tests/test_paths.py  test_cache.py  test_server.py  test_build.py  test_config.py  test_lab.py
```

- Dependencies: `nbconvert>=7.16,<8`, `nbformat>=5.10`, `mistune>=3.0,<4`, `pygments>=2.18`, `jinja2>=3.1`, `beautifulsoup4>=4.12`. `requires-python = ">=3.12,<3.15"`. Build backend hatchling with `templates/` and `static/` in the wheel.
- Groups: `dev = ["pytest>=8.3", "ruff"]`, `shots = ["playwright"]`.
- Entry point: `[project.scripts] lectern = "lectern.cli:main"`; subcommands `serve`, `build`, `lab`, `add`, `remove`, `agent`.
- Local install: `uv tool install --editable /Users/anton/projects/tools/lectern`.

### Tests

- Golden fragments, one fixture notebook per case: markdown with pipe table and fenced code; long stream lines; stderr; ANSI stream; pandas table with `<style scoped>`; wide prose table; png; svg; error traceback; inline and display math; `text/latex`; plotly-only bundle; widget bundle; attachment image; code cell over 30 lines; no H1; nbformat 4.4 with no cell ids. `pytest --update-golden` regenerates.
- Across fixtures: no `In [` text, no `<style scoped`, no `<script` in the fragment, `has_math` correct, contents ids unique.
- Paths: `..`, `%2e%2e`, absolute paths, symlink escaping the root, dotfiles, `.py` and `.env` (404), bad Host (421), POST (405).
- Cache: same mtime renders once; touched file re-renders; ETag → 304; truncated JSON serves the last good render with banner, 503 with none.
- Build: output tree, relative asset paths at depth 0 and 2, `.ipynb` → `.html` rewriting, index values from `lectern.toml` versus env fallback.
- Lab: refusal without a hashed password; assembled argv.

### Integration (last milestone; touch nothing before then)

- **agent-memory-eval:** delete `jupyter-lab-qr.sh`, `jupyter-qr.sh`, `voila-qr.sh`, `custom.css`; add "Reading on a tablet" to `README.md` under "Running the notebooks" (`lectern serve` in the repo root, open `http://<mac>.local:8642/`, `lectern lab notebooks` for the rare edit). No Pages build while notebooks are ignored.
- **ml-explorations:** delete `tools/build_site.py`; add `lectern.toml`; replace the build steps in `pages.yml`; update README line 75 and the `CLAUDE.md` publishing section.
- **long-tail-multi-label-classification, blog-code:** `lectern add` each locally; Pages later by copying `pages.yml` and a three-line `lectern.toml`.

## 12. Sketches (not run; check against the installed nbconvert before trusting)

Check block names and bodies in `~/Library/Python/3.14/share/jupyter/nbconvert/templates/classic/base.html.j2` and `base/null.j2`, the `markdown2html` signature at `nbconvert/exporters/html.py:246`, and the math method names on `IPythonRenderer` in `nbconvert/filters/markdown_mistune.py`.

`templates/reader/conf.json`

```json
{"base_template": "classic", "mimetypes": {"text/html": true}}
```

`templates/reader/index.html.j2`

```jinja
{%- extends 'classic/base.html.j2' -%}

{%- block header -%}{%- endblock header -%}
{%- block footer -%}{%- endblock footer -%}
{%- block in_prompt -%}{%- endblock in_prompt -%}
{%- block output_prompt -%}{%- endblock output_prompt -%}
{%- block data_javascript -%}{%- endblock data_javascript -%}

{% block markdowncell scoped %}
<section class="cell md"{% if cell.id %} id="c-{{ cell.id }}"{% endif %}>
{{ cell.source | markdown2html | strip_files_prefix }}
</section>
{% endblock markdowncell %}

{% block codecell scoped %}
<section class="cell code"{% if cell.id %} id="c-{{ cell.id }}"{% endif %}>
{{ super() }}
</section>
{% endblock codecell %}

{% block input_group %}
{%- set n = cell.source.count('\n') + 1 -%}
<details class="src"{% if n <= 30 %} open{% endif %}>
<summary>Code · {{ n }} line{{ '' if n == 1 else 's' }}</summary>
{{ cell.source | highlight_code(metadata=cell.metadata) }}
</details>
{% endblock input_group %}

{% block output_group %}
<div class="out">{{ super() }}</div>
{% endblock output_group %}

{% block stream_stdout %}
<pre class="stream wrap">{{ output.text | ansi2html | stream_lines }}</pre>
{% endblock stream_stdout %}

{% block stream_stderr %}
<pre class="stream wrap stderr">{{ output.text | ansi2html | stream_lines }}</pre>
{% endblock stream_stderr %}

{% block data_html scoped %}
{{ output.data['text/html'] | clean_table_html }}
{% endblock data_html %}
```

Caveat: `classic/base.html.j2` wraps `codecell`, `output` and the `data_*` blocks in its own `div`s with classic class names; calling `super()` keeps those wrappers. Either accept them and style around them, or override the block fully without `super()`. Decide after reading the parent template.

`render/notebook.py`

```python
from dataclasses import dataclass
from pathlib import Path
import threading

import nbformat
from nbconvert import HTMLExporter
from nbconvert.filters.markdown_mistune import IPythonRenderer, MarkdownWithMath

from .filters import clean_table_html, stream_lines
from .toc import extract_toc

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
RENDER_VERSION = 1


class ReaderMarkdownRenderer(IPythonRenderer):
    # Method names to confirm in markdown_mistune.py.
    def inline_math(self, body):
        return f'<span class="math inline">{self.escape_html(body)}</span>'

    def block_math(self, body):
        return f'<div class="math display">{self.escape_html(body)}</div>'


class ReaderExporter(HTMLExporter):
    def __init__(self, **kw):
        super().__init__(
            template_name="reader",
            extra_template_basedirs=[str(TEMPLATES)],
            exclude_input_prompt=True,
            exclude_output_prompt=True,
            exclude_anchor_links=False,
            embed_images=True,
            **kw,
        )
        self.register_filter("clean_table_html", clean_table_html)
        self.register_filter("stream_lines", stream_lines)
    # Also: disable CSSHTMLHeaderPreprocessor, and override markdown2html to build
    # ReaderMarkdownRenderer with the same arguments the parent passes to IPythonRenderer.


@dataclass
class Rendered:
    fragment: str
    toc: list
    title: str
    has_math: bool


_exporter = ReaderExporter()
_lock = threading.Lock()


def render_notebook(path: Path) -> Rendered:
    nb = nbformat.read(path, as_version=4)
    with _lock:
        fragment, _ = _exporter.from_notebook_node(nb, resources={"metadata": {"path": str(path.parent)}})
    toc, title = extract_toc(fragment, fallback=path.stem)
    return Rendered(fragment, toc, title, 'class="math' in fragment)
```

`render/filters.py`

```python
from bs4 import BeautifulSoup
from markupsafe import Markup

PROSE_CELL = 60


def clean_table_html(html: str) -> Markup:
    soup = BeautifulSoup(html, "html.parser")
    for style in soup.find_all("style"):
        style.decompose()
    for table in soup.find_all("table"):
        table.attrs.pop("border", None)
        long = any(len(c.get_text()) > PROSE_CELL for c in table.find_all(["td", "th"]))
        table["class"] = [*table.get("class", []), "prose-table" if long else "data-table"]
        table.wrap(soup.new_tag("div", attrs={"class": "table-wrap"}))
    return Markup(str(soup))


def stream_lines(html: str) -> Markup:
    # Input is already escaped by ansi2html; ANSI spans crossing line breaks need care.
    return Markup("\n".join(f'<span class="l">{line}</span>' for line in html.split("\n")))
```

`paths.py`

```python
from pathlib import Path

ALLOWED = {".ipynb", ".md", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}


def resolve(root: Path, rel: str) -> Path | None:
    if "\x00" in rel or "\\" in rel:
        return None
    parts = [p for p in rel.split("/") if p]
    if any(p.startswith(".") for p in parts):
        return None
    target = root.joinpath(*parts).resolve()
    if not target.is_relative_to(root.resolve()):
        return None
    if target.is_file() and target.suffix.lower() not in ALLOWED:
        return None
    return target
```

`library.py` `describe()`, ported from `build_site.py:50-72` (re-read the original before finalising):

```python
import json
from pathlib import Path


def describe(path: Path) -> tuple[str, str]:
    title, summary = path.stem, ""
    try:
        cells = json.loads(path.read_text(encoding="utf-8")).get("cells", [])
    except (OSError, json.JSONDecodeError):
        return title, summary
    for cell in cells:
        if cell.get("cell_type") != "markdown":
            continue
        lines = "".join(cell.get("source", [])).splitlines()
        for i, line in enumerate(lines):
            if line.startswith("# "):
                title = line[2:].strip()
                para = []
                for rest in lines[i + 1:]:
                    if rest.strip():
                        para.append(rest.strip())
                    elif para:
                        break
                summary = " ".join(para)
                return title, summary
    return title, summary
```

## 13. Milestones

Screenshot check without the iPad:

```
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --window-size=820,1180 --force-device-scale-factor=2 --hide-scrollbars --screenshot=<scratch>/shot.png <url>
```

Read the PNG back and look at it. From M2, `uv run --group shots python scripts/shots.py` covers Chromium and WebKit (the closer stand-in for iPad Safari), both themes, first viewport and full page; may need `playwright install`.

1. **Usable on the iPad.** Scaffold, `ReaderExporter` and template, Solarized CSS with final typography, `serve` for one root, listing, notebook and markdown pages, link rewriting for `.md` / `.py`, path safety, mtime cache, Apple meta tags and touch icon. *Verify:* `pytest`; `lectern serve` in agent-memory-eval; `curl -s localhost:8642/agent-memory-eval/notebooks/letta-intuition.ipynb | grep -c 'In \['` gives 0; screenshots of all four notebooks; then the `.local` URL on the iPad in Safari and Add to Home Screen.
2. **Reading comfort.** Contents, position restore, code collapsing, stream wrap toggle and clamp, table classification, settings sheet with `boot.js`, `shots.py`. *Verify:* golden tests; shots in both engines; a Playwright script that scrolls, reloads and asserts the same cell is in view.
3. **E-ink.** Theme, pager, tap zones, first-visit detection, optional bundled fonts; decide the full-screen route on the device. *Verify:* shots with `data-theme=eink` at the tablet's viewport; no `transition` or `animation` in computed CSS; a reading session on the tablet.
4. **Static build.** `build`, `lectern.toml`, publish the repo, tag `v0.1.0`, swap ml-explorations. *Verify:* `lectern build <ml-explorations> -o <scratch>/_site`; page weight against the 351 KB baseline; open with `file://`; `workflow_dispatch` on a branch.
5. **Math and richer outputs.** Vendored KaTeX, plotly and widget fallbacks, error styling. *Verify:* the blog-code notebook (math) and the long-tail notebook (png); no KaTeX request on a page without math.
6. **Launch polish.** Config roots, `add` / `remove`, `/_ping` reuse, `agent install`, `lab`, `--qr`, follow-changes, Tailscale section in the README. *Verify:* `launchctl print gui/$(id -u)/com.anton.lectern`; `curl /_ping`; `lectern lab` reaches the password page and refuses to start without a hashed password (in a test fixture).
7. **Cleanup.** The integration changes in section 11.

## 14. Risks and open points

- **Template coupling:** a new nbconvert major could rename blocks in `classic/base.html.j2`; contained by the `<8` pin and golden tests.
- **Exposure:** anything on the Wi-Fi can read notebooks and markdown under the served roots, including secrets printed into outputs. Also applies on any other network the laptop joins while serving.
- **`.local` on the e-ink tablet** depends on its Android version and browser; the IP fallback changes with DHCP (a router reservation would help).
- **Laptop asleep** means no server.
- **Two laptops:** each has its own `.local` name, so each gets its own home-screen icon and saved positions (or one Tailscale name later).
- **Unverified until tried on devices:** http Add to Home Screen on iPadOS 26, status-bar and theme colour in standalone mode, edge-swipe back, Android install behaviour, e-ink system fonts.
- **Unverified locally:** KaTeX size and version to vendor; whether a launchd-spawned Python triggers the macOS firewall prompt; Jupyter cookie lifetime.
- **Still to ask Anton when relevant:** e-ink tablet model, Android version, browser, and whether it can install Tailscale; whether the agent-memory-eval notebooks stay gitignored (decides whether that repo can ever get a Pages build).
- JupyterLab from the old script was still running on port 8888 when this was written.

## 15. Working rules that apply to this project

From Anton's global instructions: after every change suggest a commit message (one-line summary, blank line, unwrapped body) and never run `git commit`; release-facing text describes only user-visible behaviour.
