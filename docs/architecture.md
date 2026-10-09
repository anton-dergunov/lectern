# Approach and architecture

What lectern is built to be, how a page gets made, and where each part lives. The [README](../README.md) covers using it.

## Approach

**A reader, not a notebook server.** Lectern shows a notebook as it was last saved: the prose, the code and the outputs stored in the file. It never starts a kernel and never runs a cell. That is the decision the rest follows from: because it cannot run code, it needs no password or token, and a tablet can open it by address alone. Running a cell is left to JupyterLab, which `lectern lab` starts with its password on.

**Plain HTML, made on the Mac.** A notebook is converted to an HTML fragment by nbconvert with a template of lectern's own, and placed in a page shell with lectern's stylesheets. Nothing of JupyterLab's interface or CSS is used, so there is nothing on the page that misbehaves under a finger. Notebook output is treated as untrusted: pages carry no inline scripts and load nothing from another origin, and a Content-Security-Policy enforces it.

**The page works without its script.** The server sends a page that can be read as it is. Everything else (reading position, folding, settings, page turns, marking) is added by `reader.js` after load.

**One write.** The server answers `GET` and `HEAD`, plus one `PUT` that replaces the highlights and notes kept on a document. The request names a served document, never a file; `notes.py` works out the path, checks every field and writes the file itself. It must be JSON from one of lectern's own pages (`Origin` equal to `Host`), and `OPTIONS` is refused, so a page on another site cannot send it. Nothing else on the Mac can be changed from a device: `lectern add` reaches a running server through the settings file, which the server re-reads.

**One renderer for served and published pages.** `lectern build` writes the same pages to a directory for a static host. They share the template, the script and the stylesheets with served pages; what needs the server is skipped on a page marked `data-static`. A built site carries nobody's notes.

## How a page is made

1. **Which file.** `paths.resolve()` maps the URL onto a file under a served folder. It refuses hidden files, anything outside the folder (symlinks are resolved first), anything named in the folder's `.lecternignore`, and every type but notebooks, markdown and images. Everything a device asks for goes through it, the notes address included.
2. **Render.** `render/notebook.py` runs nbconvert's `HTMLExporter` with the template in `templates/reader/`, which extends nbconvert's `classic/base.html.j2` by block name; `render/markdown.py` handles `.md` files and markdown cells. Interactive outputs keep their saved picture, or a short note in its place.
3. **Finish.** `render/document.py` makes one pass over the fragment whatever it came from: tables are wrapped so they scroll by themselves, relative links are pointed at what the reader can open, headings are collected for the title and the contents list.
4. **Shell.** `render/page.py` puts the fragment into `templates/page.html.j2`. Listings and error pages use the same shell.
5. **Cache.** `cache.py` keeps rendered documents in memory, keyed on the file's path, time and size and on `RENDER_VERSION`. The same key gives the ETag, which is also what "Reload automatically" polls. A notebook caught half-saved is shown as it last rendered.

## The server

`server/app.py` is Python's `ThreadingHTTPServer` with one handler.

| Address | What it is |
|---|---|
| `/` | The start page. Cached for a long time, so it can say "Lectern is not running" when that is so; otherwise it goes on to `/_home`. |
| `/_home` | The listing of the one served folder, or the list of folders. |
| `/<folder>/…` | A listing, a document or an image. |
| `/_notes/<folder>/<document>` | The document's notes: `GET`, and the one `PUT`. |
| `/_ping` | Name, version and folders. A caller on the loopback address is also told where the folders are on disk. |
| `/_static/<hash>/…` | Stylesheets, scripts, fonts and icons, under a hash of their contents. |
| `/_sw.js`, `/_offline` | The service worker and the "not running" page it keeps. |

A request whose `Host` is not this Mac's `.local` name, `localhost`, an IP address or a name listed in the settings is refused, which is what stops another site from reading through the browser. Every response carries `X-Lectern`; the service worker uses it to tell lectern's own error pages from those of a proxy in front of it. The worker is network-first and keeps only the "not running" page, so it can never show a stale notebook.

## In the browser

- `static/boot.js` runs before the first paint and applies the saved theme and text size, so a page never flashes in the wrong colours.
- `static/reader.js` does everything after load. Settings, reading positions and folded sections are kept per device in `localStorage`.
- Highlights are drawn with the CSS highlight API, which paints over the text without changing an element, so folding, reading positions and page turns are unaffected by them.
- A Home Screen app (`navigator.standalone`, or `display-mode: standalone`) gets two things a browser tab does not need. A find field in the top bar: matches are painted with the highlight API like marks, and going to one opens what hides it. And a way back in: the trail of pages, which lives in `sessionStorage`, is copied to `localStorage`, and the start page hands it back and goes to the page it ends on. The start page marks that it is doing so and the page clears the mark once loaded, so a page that never loads is not gone back to twice.
- The e-ink theme replaces scrolling with page turns that start and end on a whole line.
- Colours are variables in `static/themes.css`, one block per theme; the other stylesheets only use them.

## Where things are

| Path | What is there |
|---|---|
| `src/lectern/cli.py` | The `lectern` command and its subcommands. |
| `src/lectern/server/` | The HTTP server and its routes. |
| `src/lectern/render/` | Notebook and markdown to HTML, links, contents, the page shell. |
| `src/lectern/paths.py` | What may be handed out, and the ignore list. |
| `src/lectern/library.py` | Finding documents and describing them for a listing. |
| `src/lectern/cache.py` | Rendered documents in memory. |
| `src/lectern/notes.py` | The notes file beside a document, and `lectern notes`. |
| `src/lectern/build.py` | The static site. |
| `src/lectern/config.py`, `agent.py`, `lab.py`, `netinfo.py` | Saved folders, the login agent, JupyterLab, the Mac's names on the network. |
| `src/lectern/templates/`, `static/` | Page templates; scripts, stylesheets, fonts and icons. |
| `tests/` | Unit tests. `tests/fixtures` has one notebook per rendering case, `tests/golden` what each should render to. |
| `scripts/` | `check_reader.py` and `shots.py` drive Chromium and WebKit, for what unit tests cannot see; `make_fixtures.py` writes the fixtures. |

## Other people's files

Kept whole and unedited, with their licences beside them.

| Where | What |
|---|---|
| `static/vendor/katex` | KaTeX 0.19.0: the script, the stylesheet and the woff2 fonts. Added to a page only when it has math. |
| `static/fonts` | Charis SIL 6.101 for text, JetBrains Mono 2.211 for code and Inter 4.001 for the interface, Latin subsets as woff2. The font stacks name Apple's own fonts first, so an iPad or a Mac never fetches these. |
