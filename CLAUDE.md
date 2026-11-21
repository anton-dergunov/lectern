# lectern

A read-only reader for Jupyter notebooks and markdown, served from a Mac to tablets on home Wi-Fi. `docs/architecture.md` describes the approach, how a page is made and where each part lives. Read it before changing behaviour; the rules below are settled, so do not re-open one without a reason.

## Commands

```sh
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run lectern serve PATH --host 127.0.0.1    # try it locally
uv run lectern build PATH -o /some/scratch/_site  # the static site; never into the project being built
uv run lectern notes PATH                     # what was marked while reading, as markdown
uv run --group shots python scripts/check_reader.py     # browser behaviour, Chromium and WebKit
uv run --group shots python scripts/shots.py --out DIR  # screenshots at the iPad's size
uv run pytest --update-golden                 # after a deliberate rendering change; read the diff
uv run --group example python scripts/make_example.py   # rewrite and run the sample notebook in examples/
uv run --group shots python scripts/picture.py          # the README picture, docs/pictures/lectern.png
```

## Rules

- The reader executes nothing and runs with no token. Both follow from each other: never add anything that starts a kernel or runs code from a notebook. The server answers `GET` and `HEAD` only, with one exception: `PUT /_notes/<root>/<document>` replaces the notes kept on a served document.
- That `PUT` is the only thing a device can change on the Mac, and it must stay that narrow. The request names a document, never a file; `notes.py` works out the path, checks every field and composes the file itself. It needs an `Origin` that is this server and a JSON body, and `OPTIONS` stays refused, so a web page from elsewhere cannot send it. Do not add a second write, and do not loosen these to make a client easier.
- Pages carry no inline scripts and nothing from another origin; the CSP in `server/app.py` enforces it. The only scripts are `static/boot.js` (before paint: theme and text size) and `static/reader.js` (everything after load). Notebook output HTML is untrusted input.
- `static/sw.js` must stay network-first and keep nothing but the "not running" page and its assets: a service worker that answers for the server would show stale notebooks. Every response carries `X-Lectern`, which is how it tells lectern's own error pages from a proxy's.
- A page must stay readable with `reader.js` missing: enhancements are added by the script, not required by the markup.
- After changing `reader.js`, `reader.css` or the page templates, run `scripts/check_reader.py`; the unit tests do not load a browser.
- `lectern build` writes pages for the public. It must not publish what was not asked for: markdown only when linked from a notebook unless told otherwise, and nothing but documents and the images they use.
- Served pages and built pages share `page.html.j2`, `reader.js` and the stylesheets. Anything that needs the server (the link guard, the start page) must be skipped when the page carries `data-static`.
- Only notebooks, markdown and images under a served root are handed out (`paths.py`). A new file type is a deliberate decision, not a convenience.
- What a root's `.lecternignore` names does not exist as far as a device is concerned: `paths.resolve()` refuses it, by the path asked for and by the file a symlink leads to, without regard to letter case. Leaving it out of the listing alone is not enough, and `lectern build` must leave it out too.
- `templates/reader/index.html.j2` extends nbconvert's `classic/base.html.j2` by block name. After any nbconvert upgrade, run the tests and look at a rendered page.
- Raise `RENDER_VERSION` in `render/__init__.py` when the HTML for an unchanged file changes; it is part of the cache key and the ETag.
- `static/fonts` and `static/vendor` are other people's files, with their licences beside them. Do not edit them; replace them whole, and say which version in `docs/architecture.md`.
- Colours live only in `static/themes.css`. `reader.css` and `pygments.css` use the variables.
- Apart from notes, the server changes nothing on request. `lectern add` reaches a running server through the settings file it re-reads, not through an endpoint; keep it that way.
- Notes are for served pages only. A built page offers no marking and `lectern build` never copies a `*.notes.json`.
- `/_ping` tells a caller on the loopback address where the served folders are on disk, and no one else.
- `lectern lab` must never start JupyterLab without a password, with a token, or with its Host check off.
- When testing against a real project, pass `--host 127.0.0.1`: serving on the default address puts that project's documents on the network.

## Looking at a page without the iPad

`scripts/shots.py` takes the first screen and the full page of each document in Chromium and WebKit (the closer stand-in for Safari) at 820×1180, the iPad in portrait. `--theme all` covers the four themes; `ROOT` can be any project directory. Look at the PNGs; do not assume.
