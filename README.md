# lectern

Read Jupyter notebooks and markdown on a tablet, served from your laptop over home Wi-Fi.

## What it does

`lectern serve` in a project directory starts a small web server. Open its address on a tablet and you get:

- a listing of the notebooks and markdown files in that directory tree, with each notebook's title, opening paragraph and reading time;
- each notebook as a readable page: prose in a comfortable column, code without the prompt gutter, the outputs that were saved with the notebook, wide tables that scroll sideways on their own;
- math typeset, plots shown from the pictures saved with them, and a short note where an output needs a running notebook (a widget, an interactive plot saved without a picture);
- markdown files as pages in the same style, with the links between notebooks and documents working;
- a contents list for each notebook, and your place in it kept: reopen a notebook and you are where you stopped reading;
- sections that fold: a marker beside each heading hides everything under it, and the contents list can collapse the whole notebook to its outline and open the part you pick;
- a way back: after following a link to another document, the arrow in the top bar returns to the one you came from, at the place you left it, and a second arrow goes forward again;
- long code cells folded away until you ask for them, long printed output cut to its first lines, and a small cell number on each code cell to find it again in Jupyter;
- reading settings saved per device, starting from sizes that suit a tablet, a phone, a desktop or an e-ink reader: text size, column width from narrow to the full window, Solarized or black-and-white colours in light or dark (or following the system), and code cells hidden altogether;
- an e-ink theme, chosen by itself on e-ink readers: black on white, nothing animated, and pages turned with buttons, a tap on either edge of the screen, or the page keys instead of scrolling. A page starts and ends on a whole line, and begins with the last two lines of the page before. For an e-ink screen with colour it can colour code and printed output; pictures are in colour either way. A tap on the page number hides the top bar, and another brings it back;
- a top bar that gets out of the way while you read down and comes back when you scroll up;
- a page that can be added to the iPad Home Screen and then opens full screen, with no browser bars;
- the same pages as a static site, with `lectern build`, to publish committed notebooks on GitHub Pages or any other host.

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

If lectern is stopped while a page is open, following a link shows "Lectern is not running" instead of a browser error. The page carries on by itself once `lectern serve` is running again; **Try again** asks at once.

`lectern serve PATH…` serves other directories, each under its own name. `--port` changes the port (default 8642), `--host` the address to listen on, `--qr` also shows the address as a QR code (needs `qrencode`), and `--verbose` prints each request.

Running `lectern serve` while lectern is already running does not start a second one. It prints the address of the folder you are in if that is being served, and says how to get it served if not.

With **Reload automatically** switched on in a page's settings, the page reloads by itself, in the same place, when the notebook is saved again. It is off by default, and not offered in the e-ink theme.

### Folders you read often

```sh
lectern add ~/projects/writing/agent-memory-eval    # or just `lectern add` inside it
lectern list
lectern remove agent-memory-eval
lectern serve --all
```

`serve --all` serves every saved folder, each under its own name, from one address. A folder added or removed while it runs appears or disappears within a second; nothing needs restarting. The list is kept in `~/.config/lectern/config.toml`, which also holds the port.

### Always on

```sh
lectern agent install
lectern agent status
lectern agent uninstall
```

`agent install` starts `lectern serve --all` now and at every login, so the saved folders can be read whenever the Mac is awake. Its output goes to `~/Library/Logs/lectern.log`. Remember that this puts the saved folders on every network the Mac joins; `lectern agent install --host 127.0.0.1` keeps it to the Mac itself, for use behind Tailscale (below).

### Running a cell

Lectern never runs code. For the rare time something has to be run from the tablet:

```sh
lectern lab notebooks
```

starts JupyterLab for that folder on port 8888, using the folder's own `.venv` if it has one. Lab does run code, so it is never started open: it uses the password already set for Jupyter on the Mac, typed once per device, and `lectern lab` refuses to start if there is none (`jupyter server password` sets it).

### Away from home, and full screen on Android

Over plain `http`, Android only offers a shortcut that opens in a browser tab. A proper full-screen app there needs HTTPS, which [Tailscale](https://tailscale.com/) provides without certificates to install:

```sh
tailscale serve --bg --https=443 http://127.0.0.1:8642
```

Then add the Mac's Tailscale name to `extra_hosts` in `~/.config/lectern/config.toml`, since lectern only answers to names it knows:

```toml
extra_hosts = ["your-mac.your-tailnet.ts.net"]
```

and open `https://your-mac.your-tailnet.ts.net/` on any device signed in to the same Tailscale account. The same address works away from home.

`tailscale serve --bg` is remembered: it comes back by itself after a restart of the Mac or of Tailscale, until `tailscale serve reset` removes it. It only forwards, so `lectern serve` (or the login agent) still has to be running.

Over HTTPS lectern also stays in charge when it is stopped: opening or reloading any page shows "Lectern is not running", with a Try again button, in place of the browser's own error page, and the page loads by itself once lectern is back.

### Full screen on an iPad

Open the address once in **Safari**, then Share → Add to Home Screen. The icon opens lectern full screen. The icon is tied to the address, so keep the port the same.

### Publishing as a static site

```sh
lectern build . -o _site
```

writes every notebook under the current directory as a page, an index of them, and the stylesheets and scripts they need, into `_site`. The pages look and behave as they do when served, settings included, and open from any static host or straight from the disk.

Markdown files become pages only when a notebook links to them, so a repository's README and working notes are not published by accident; `--markdown all` builds every one, `--markdown none` builds none. Links to other files in the repository (scripts, data) point at the repository when it is known.

Settings can live in a `lectern.toml` at the top of the directory instead of on the command line:

```toml
title = "ML Explorations"
description = "Small self-contained experiments, each one written up as a notebook."
repo_url = "https://github.com/you/ml-explorations"
exclude = ["tools/*"]
```

Also available: `branch` (for the links to the repository, default `main`), `theme` (`solarized`, `plain` or `eink`: the colours a first-time visitor sees), `markdown` and `include`. `include` and `exclude` are patterns matched against each path from the top of the directory, where `*` also matches `/`. In GitHub Actions the repository and branch are taken from the environment, so neither needs setting there.

`--clean` empties the output directory first, and only if an earlier build filled it.

To publish from GitHub Actions, replace the build steps of a Pages workflow with:

```yaml
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - name: Render notebooks
        run: uvx --from "git+https://github.com/anton-dergunov/lectern@v0.1.0" lectern build . -o _site
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with: { path: _site }
```

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

MIT, see [LICENSE](LICENSE). Colours are Ethan Schoonover's [Solarized](https://ethanschoonover.com/solarized/). Notebook conversion is [nbconvert](https://nbconvert.readthedocs.io/). Math is typeset by [KaTeX](https://katex.org/) (MIT).

On devices without Apple's fonts the pages use [Charis SIL](https://software.sil.org/charis/), [JetBrains Mono](https://www.jetbrains.com/lp/mono/) and [Inter](https://rsms.me/inter/), each under the SIL Open Font License; the licences are in `src/lectern/static/fonts`.
