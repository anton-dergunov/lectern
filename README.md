# lectern

Read Jupyter notebooks and markdown on a tablet, served from your laptop over home Wi-Fi.

## What it does

`lectern serve` in a project directory starts a small web server. Open its address on a tablet and you get:

- a listing of the notebooks and markdown files in that directory tree, with each notebook's title, opening paragraph and reading time;
- each notebook as a readable page: prose in a comfortable column, code without the prompt gutter, the outputs that were saved with the notebook, wide tables that scroll sideways on their own;
- markdown files as pages in the same style, with the links between notebooks and documents working;
- a contents list for each notebook, and your place in it kept: reopen a notebook and you are where you stopped reading;
- long code cells folded away until you ask for them, long printed output cut to its first lines, and a small cell number on each code cell to find it again in Jupyter;
- reading settings saved per device: text size, column width from narrow to the full window, Solarized or black-and-white colours in light or dark (or following the system), and code cells hidden altogether;
- an e-ink theme, chosen by itself on e-ink readers: black on white, nothing animated, and pages turned with buttons, a tap on either edge of the screen, or the page keys instead of scrolling;
- a top bar that gets out of the way while you read down and comes back when you scroll up;
- a page that can be added to the iPad Home Screen and then opens full screen, with no browser bars.

Notebooks are shown as they were last saved, including ones you have not committed. Save the notebook and reload the page to see the change.

## Why it exists

A notebook with its outputs saved is a document, and a tablet is a better place to read a document than a laptop. JupyterLab on a touch screen gets in the way of that: scrolling selects cells, menus close under the finger, and every device needs a token. Rendering to GitHub Pages only covers what is already committed and pushed.

Lectern only reads. It never starts a kernel and never runs a cell, which is why it needs no password or token.

## How it works

Notebooks are converted with nbconvert, using a template of lectern's own that produces plain HTML for the page shell and stylesheet in this repository. The server is Python's standard library HTTP server and answers only `GET` and `HEAD`. Rendered pages are kept in memory and re-rendered when the file changes on disk.

What the server will hand out is limited to notebooks, markdown files and images under the directories you serve. Hidden files, paths that leave the directory (including through symlinks) and every other file type get a 404. Requests whose `Host` header is not this machine's `.local` name, `localhost` or an IP address are refused.

**Anyone on the same network can read what you serve**, including anything a notebook printed into its outputs. Use it on a network you trust, and stop it when you leave.

## Install

Requires Python 3.12 or newer and [uv](https://docs.astral.sh/uv/).

```sh
uv tool install --editable /path/to/lectern
```

## Usage

```sh
cd ~/projects/writing/agent-memory-eval
lectern serve
```

```
lectern  serving agent-memory-eval (4 notebooks, 4 markdown files)
  http://Antons-MacBook-Air-13.local:8642/
  http://192.168.1.101:8642/        (fallback)
```

Open the first address on the tablet. The second is for devices that cannot resolve `.local` names; it changes when the router hands the laptop a different address.

If lectern is stopped while a page is open, following a link shows "Lectern is not running" instead of a browser error, and the page carries on by itself once `lectern serve` is running again.

`lectern serve PATH…` serves other directories, each under its own name. `--port` changes the port (default 8642), `--host` the address to listen on, and `--verbose` prints each request.

### Full screen on an iPad

Open the address once in **Safari**, then Share → Add to Home Screen. The icon opens lectern full screen. The icon is tied to the address, so keep the port the same.

## Development

```sh
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Two scripts drive real browsers (Chromium and WebKit) against the test fixtures. They need the browsers once: `uv run --group shots playwright install chromium webkit`.

```sh
uv run --group shots python scripts/check_reader.py     # behaviour: position, settings, contents, server stopped
uv run --group shots python scripts/shots.py --out shots  # screenshots at the iPad's size
```

After a deliberate change to how notebooks render, `uv run pytest --update-golden` rewrites `tests/golden`; read the diff before committing it.

`HANDOFF.md` holds the design and the milestones still to build; `docs/tasks/plan.md` holds ideas outside them.

## License and credits

MIT, see [LICENSE](LICENSE). Colours are Ethan Schoonover's [Solarized](https://ethanschoonover.com/solarized/). Notebook conversion is [nbconvert](https://nbconvert.readthedocs.io/).
