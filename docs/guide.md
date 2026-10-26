# Using lectern

Everything lectern can do and how to set it up. The [README](../README.md) has the short version; [architecture.md](architecture.md) explains how it is built.

- [Install](#install)
- [Reading on a tablet](#reading-on-a-tablet)
- [Reading a page](#reading-a-page)
- [Choosing which code is shown](#choosing-which-code-is-shown)
- [Highlights and notes](#highlights-and-notes)
- [Keeping files out of sight](#keeping-files-out-of-sight)
- [Folders you read often](#folders-you-read-often)
- [Always on (macOS)](#always-on-macos)
- [Full screen on an iPad](#full-screen-on-an-ipad)
- [Away from home, and full screen on Android](#away-from-home-and-full-screen-on-android)
- [Running a cell](#running-a-cell)
- [Publishing as a website](#publishing-as-a-website)
- [What it hands out, and who can see it](#what-it-hands-out-and-who-can-see-it)

## Install

Lectern needs Python 3.12 or newer and [uv](https://docs.astral.sh/uv/).

```sh
uv tool install git+https://github.com/anton-dergunov/lectern
```

To work on lectern itself, install it from a checkout instead, so that changes take effect without reinstalling:

```sh
uv tool install --editable /path/to/lectern
```

Lectern is developed and used on macOS. Serving, building and `lectern notes` are plain Python and should work on Linux and Windows too. Two things are macOS-only: `lectern agent`, which starts lectern at login, and the fallback IP address that `lectern serve` prints, which is read with a macOS tool and is missing elsewhere.

## Reading on a tablet

In the folder you want to read, start lectern:

```sh
cd ~/notes/ml-study
lectern serve
```

```
lectern  serving ml-study (4 notebooks, 4 markdown files)
  http://your-desktop.local:8642/
  http://192.168.1.20:8642/        (fallback)
```

Open the first address on the tablet, phone or e-ink reader. It uses your computer's name on the local network, so it keeps working when the router hands out a new IP address. The second address is for devices that cannot resolve `.local` names, and it changes when the computer's address changes.

Notebooks are shown as they were last saved, including ones you have not committed. Save the notebook and reload the page to see the change. With **Reload automatically** switched on in a page's settings, the page reloads by itself, in the same place, whenever the notebook is saved again. It is off by default, and not offered in the e-ink theme.

**Serving several folders.** `lectern serve PATH…` serves each folder under its own name, which becomes the first part of its addresses. A name starting with `.` or `_` is served without it (`_drafts` as `drafts`), and `--name` gives a single folder another name. For folders you read all the time, see [Folders you read often](#folders-you-read-often).

**Options.** `--port` changes the port (8642 by default), `--host` the address to listen on, `--qr` also prints the address as a QR code (it needs `qrencode`), and `--verbose` prints every request.

**Already running.** Running `lectern serve` while lectern is already running does not start a second one. If the folder you are in is being served, it prints its address; if not, it tells you how to get it served.

**When lectern is stopped.** If you stop lectern while a page is open, following a link shows "Lectern is not running" instead of a browser error. The page carries on by itself once `lectern serve` is running again, and **Try again** checks at once.

## Reading a page

**The listing.** The start page lists the notebooks and markdown files in the folder and below it, each with its title, opening paragraph and reading time. **Files** shows just the folders and files of the current folder instead, as a file browser would.

**Notebooks and markdown.** Prose is set in a comfortable column. Code is shown without the prompt gutter, followed by the outputs that were saved with the notebook. Math is typeset. Plots are shown from the pictures saved with them. Mermaid diagrams, from a ```` ```mermaid ```` block in markdown or a notebook output, are drawn in the reading theme's colours. Where an output needs a running notebook (a widget, or an interactive plot saved without a picture), a short note takes its place. Markdown files get the same style, and links between notebooks and documents work.

**Tables** wrap their text to fit the column. A table with too many columns borrows what it lacks from the margins, and scrolls sideways only if it is wider than the screen.

**Long code and output.** A code cell longer than 30 lines starts folded until you ask for it (see [Choosing which code is shown](#choosing-which-code-is-shown)). Long printed output is cut to its first lines. Each code cell carries a small cell number, so you can find it again in Jupyter.

**Finding your way.** Each notebook has a contents list. A marker beside each heading folds everything under it, and the contents list can collapse the whole notebook to its outline and open just the part you pick. Reopen a notebook and you are where you stopped reading. After following a link to another document, the arrow in the top bar takes you back to the one you came from, at the place you left it, and a second arrow goes forward again. The top bar gets out of the way while you read down and comes back when you scroll up.

**Reading settings.** The **Aa** button sets the text size, the column width (from narrow to the full window), the colours (Solarized or black and white, light or dark, or following the system) and whether code cells are shown at all. Settings are kept on each device. They start from sizes that suit the device: a tablet, a phone, a desktop or an e-ink reader.

**E-ink.** On an e-ink reader the e-ink theme is chosen by itself: black on white, with nothing animated. Pages are turned with the buttons, a tap on either edge of the screen, or the page keys, instead of scrolling. A page starts and ends on a whole line, and begins with the last two lines of the page before, so you never lose your place. On an e-ink screen with colour, it can colour code and printed output. Pictures are in colour either way. A tap on the page number hides the top bar, and another brings it back.

## Choosing which code is shown

A code cell longer than 30 lines starts folded. A cell tag decides for one cell instead. `hide-input` folds it whatever its length, which suits setup, imports and plumbing. `show-input` keeps it open however long it is. These are the same tags Jupyter Book uses, and if a cell has both, `hide-input` wins.

A cell you open or fold yourself stays that way on that device the next time you read the notebook. **Hidden** in the reading settings folds every cell, and **Shown** puts each back as its tag or your own choice says.

Tags are kept in the notebook, so editors and converters carry them along:

- VS Code: **Add Cell Tag** from the command palette (the Jupyter extension);
- JupyterLab: the property inspector in the right sidebar, under **Common Tools**;
- a jupytext script: `# %% tags=["hide-input"]` on the cell's marker line (` ```python tags=["hide-input"] ` in markdown).

## Highlights and notes

The pen in the top bar switches marking on. While it is on, select some text and it is highlighted when you let go. On a touch screen, press on a word and drag to where the passage ends. Tap a highlight to add a note to it, read the note, or remove the highlight. Once a document has marks, a second button lists them, each one a way back to its place.

Marks are saved on your computer, in a file beside the document: `analysis.ipynb` gets `analysis.notes.json`. That makes them the same on every device you read from, and lets them travel with the repository if you commit the file. Add `*.notes.json` to `.gitignore` if you would rather they did not. If the notebook changes, a mark stays with its words. A mark whose words are gone is kept and listed separately.

A red dot on the pen means something you marked has not reached your computer yet. It is sent as soon as lectern can be reached again.

```sh
lectern notes notebooks/analysis.ipynb    # what was marked, as markdown
lectern notes                             # the same for every document under this folder
```

Each passage is printed under its heading, with the cell number for code, followed by the note made on it.

Saving a mark is the one thing a device can change on your computer, and anyone who can reach lectern can add or delete marks. To keep lectern to reading only, start it with `lectern serve --no-notes`, or put `notes = false` in `~/.config/lectern/config.toml`. Sites made with `lectern build` have no marking and never include anyone's notes.

## Keeping files out of sight

A `.lecternignore` file at the top of a served folder names what lectern should leave out of it:

```
# not for the tablet
private/
*.draft.md
notes/scratch.ipynb
```

A line with no `/` in it is a file or folder name, left out wherever it appears. A line with a `/` is a path from the top of the folder. `*` and `?` work as in a shell (`*` also matches `/`), and letter case does not matter. A folder that is left out takes everything in it along. Lines starting with `#` are comments.

What is left out is not listed, and cannot be opened by its address either, images included. A change to the file takes effect at once. `lectern build` leaves the same things out of a published site.

## Folders you read often

```sh
lectern add ~/notes/ml-study    # or just `lectern add` inside it
lectern list
lectern remove ml-study
lectern serve --all
```

`serve --all` serves every saved folder, each under its own name (`add --name` chooses another), from one address. A folder you add or remove while it runs appears or disappears within a second, with nothing to restart. The list is kept in `~/.config/lectern/config.toml`, which also holds the port.

## Always on (macOS)

```sh
lectern agent install
lectern agent status
lectern agent uninstall
```

`agent install` starts `lectern serve --all` now and at every login, so the saved folders can be read whenever the Mac is awake. Its output goes to `~/Library/Logs/lectern.log`. Remember that this puts the saved folders on every network the Mac joins. `lectern agent install --host 127.0.0.1` keeps it to the Mac itself, for use behind Tailscale ([below](#away-from-home-and-full-screen-on-android)).

`agent status` also says when the running lectern is older than the one installed, and how to restart it. The reading settings on a device show which version it is reading from.

The agent keeps serving the code it started with. After updating lectern (or changing its code, when it is installed from a checkout with `--editable`), restart it:

```sh
launchctl kickstart -k gui/$(id -u)/com.anton.lectern
```

`-k` stops the running lectern, and launchd starts it again at once with the same settings. There is no need to uninstall and install. A page already open on a device picks up the new version when it is reloaded.

## Full screen on an iPad

Open the address once in **Safari**, then choose Share → Add to Home Screen. The icon opens lectern full screen, with no browser bars. The icon is tied to the address, so keep the port the same.

Two things are there only when lectern is opened from the icon:

- **Find.** The magnifier in the top bar searches the document you are reading. Type a word or a phrase, in any case, and it says how many times it occurs. Return or the arrows put the keyboard away and step through the matches, opening a folded section or hidden code when a match is inside one. In a browser, use the browser's own Find instead.
- **Picking up where you left off.** If the iPad closes the app while it is in the background, the icon opens the page you were on, at your place, and the back arrow still leads to the document you came from. If that page did not finish loading last time, the app opens the listing instead, so a page that will not open cannot trap you.

## Away from home, and full screen on Android

Over plain `http`, Android only offers a shortcut that opens in a browser tab. A proper full-screen app there needs HTTPS, which [Tailscale](https://tailscale.com/) provides without any certificates to install:

```sh
tailscale serve --bg --https=443 http://127.0.0.1:8642
```

Then add your computer's Tailscale name to `extra_hosts` in `~/.config/lectern/config.toml`, since lectern only answers to names it knows:

```toml
extra_hosts = ["your-desktop.your-tailnet.ts.net"]
```

Now open `https://your-desktop.your-tailnet.ts.net/` on any device signed in to the same Tailscale account. The same address works away from home.

`tailscale serve --bg` is remembered: it comes back by itself after a restart of the computer or of Tailscale, until `tailscale serve reset` removes it. It only forwards requests, so `lectern serve` (or the login agent) still has to be running.

Over HTTPS, lectern also stays in charge when it is stopped. Opening or reloading any page shows "Lectern is not running", with a **Try again** button, in place of the browser's own error page, and the page loads by itself once lectern is back.

## Running a cell

Lectern never runs code. For the rare time something has to be run from the tablet:

```sh
lectern lab notebooks
```

This starts JupyterLab for that folder on port 8888, using the folder's own `.venv` if it has one. JupyterLab does run code, so it is never started open. It uses the password already set for Jupyter on your computer, typed once per device, and `lectern lab` refuses to start if there is none (`jupyter server password` sets it).

## Publishing as a website

```sh
lectern build . -o _site
```

This writes every notebook under the current folder as a page, an index of them, and the stylesheets and scripts they need, into `_site`. The pages look and behave as they do when served, reading settings and e-ink included. They open from any static host, or straight from the disk.

Markdown files become pages only when a notebook links to them, so a repository's README and working notes are not published by accident. `--markdown all` builds every one, and `--markdown none` builds none. Links to other files in the repository (scripts, data) point at the repository when it is known. `--clean` empties the output folder first, and only if an earlier build filled it.

Settings can live in a `lectern.toml` at the top of the folder instead of on the command line:

```toml
title = "ML Explorations"
description = "Small self-contained experiments, each one written up as a notebook."
repo_url = "https://github.com/you/ml-explorations"
exclude = ["tools/*"]
```

Also available:

- `branch`: the branch for links to the repository (default `main`);
- `theme`: `solarized`, `plain` or `eink`, the colours a first-time visitor sees;
- `markdown`: as the command-line option;
- `include`, `exclude`: patterns matched against each path from the top of the folder, where `*` also matches `/`.

In GitHub Actions, the repository and branch are taken from the environment, so neither needs setting there.

### On GitHub Pages

To publish from GitHub Actions, use the build steps below in a Pages workflow (Settings → Pages → Source: GitHub Actions):

```yaml
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - name: Render notebooks
        run: uvx --from "git+https://github.com/anton-dergunov/lectern@v0.4.0" lectern build . -o _site
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with: { path: _site }
```

[Agent memory, call by call](https://anton-dergunov.github.io/agent-memory-eval/) is a site published this way.

## What it hands out, and who can see it

Lectern never starts a kernel and never runs a cell, which is why it needs no password or token. The only thing it writes is the file of highlights and notes you make while reading, and that can be switched off ([Highlights and notes](#highlights-and-notes)).

It hands out only notebooks, markdown files and images under the folders you serve. Hidden files, paths that lead out of the folder (symlinks included), anything a `.lecternignore` names and every other file type get a 404. Requests whose `Host` header is not your computer's `.local` name, `localhost`, an IP address or a name in `extra_hosts` are refused.

**Anyone on the same network can read what you serve**, including anything a notebook printed into its outputs. Use it on a network you trust, and stop it when you leave, or keep it to your own devices with Tailscale ([above](#away-from-home-and-full-screen-on-android)).
