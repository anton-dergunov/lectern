# Tasks beyond the milestones

Ideas and postponed items that came out of using lectern. The milestones themselves are in `HANDOFF.md`, section 13. Section 1 is built; nothing else here is started.

## 1. Notes and highlights on a notebook

**The idea (Anton, 2026-10-06, after the first iPad session).** Reading is the main use, but sometimes a passage deserves a mark: select some text and keep it highlighted, or attach a remark to a part of the notebook. The marks are saved in a file somewhere, so they are there again when the same notebook is opened on the tablet or on the desktop.

**Decided (Anton, 2026-10-08): only where lectern serves the pages.** A site made by `lectern build`, such as the notebooks published from a GitHub workflow, is for other people to read: its pages offer no way to mark or remark on anything and carry nobody's notes. Like the link guard and the start page, whatever is built for this is skipped when the page has `data-static`.

**Decided the same day, before building:**

- **The server will accept one kind of write.** A single `PUT` that can only replace the notes file of a document it already serves: the server works out the file's name, the request never names a path. It checks Host and Origin, takes JSON only (which a foreign web page cannot send), caps the size, checks the shape and writes the file itself. Still no token; what a device on the Wi-Fi can do is add and delete notes. On by default, with a setting in `config.toml` to turn it off.
- **Notes live beside the document:** `analysis.ipynb` gets `analysis.notes.json`. Visible in git and travelling with the repository. Never handed out as a file and never published by `lectern build`.
- **A mark finds its text again** by the id of its cell, the quoted words and 32 characters either side. One whose words are gone is kept and shown as orphaned.
- **Back to the laptop:** `lectern notes PATH` prints markdown, each remark under its cell number and nearest heading. The JSON is the only file written.
- **The touch interaction is tried before the rest is built**, in two variants.
- **After trying them (Anton): marking mode only.** A pen in the top bar, always there; while it is on, whatever is selected is marked. No setting for it in the page.

**Built 2026-10-08, in two stages.** The first had only the interaction, with the marks kept in the browser, so that it could be tried on the iPad and the Boox before anything was written to disk. Two ways of marking were tried there: a bar beside the selection, and a marking mode. The bar landed on the system's own selection menu, which is below the selection on the iPad and above it on Android; a page can neither add to that menu nor tell where it will be. A strip at the far edge of the screen avoided it, but Anton chose to keep the marking mode alone. `HANDOFF.md` describes what is built.

**Left for later:** a remark on something with no text to select (a figure, a whole cell); highlight colours; an indication on the listing of which documents have notes.

## 2. Postponed from the first round of feedback

- **Column width as a free setting.** There are five fixed steps now (narrow, medium, wide, wider, full), and everything shares one column. A slider if the steps turn out too coarse.
- **A more file-oriented listing.** First impression was that it should show more of the files; after using it, it seemed fine. Left as it is, apart from naming the file on every row.
- **Leaving folders out.** `lectern serve` in agent-memory-eval also serves its `private/` directory. An ignore list (per folder, or a `.lecternignore`) would let a folder be served without everything in it.
- **"Continue reading" on the listing**, filled from the saved reading positions (HANDOFF section 9).
- **Reading the fold marker and the page turns on the devices.** Both were built on 2026-10-08 and checked only in desktop browsers. To judge on the iPad and the Boox: whether the marker beside a heading is easy enough to hit, whether two lines carried over to the next page is the right number (`CARRY_LINES` in `reader.js`), and whether the blank strip above the footer reads as the end of the page or as something missing.
- **Fonts for e-ink.** Nothing is bundled; the theme uses whatever serif and monospace the tablet has. Decide after seeing it on the device.
