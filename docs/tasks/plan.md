# Tasks beyond the milestones

Ideas and postponed items that came out of using lectern. The milestones themselves are in `HANDOFF.md`, section 13. Nothing here is started.

## 1. Notes and highlights on a notebook

**The idea (Anton, 2026-10-06, after the first iPad session).** Reading is the main use, but sometimes a passage deserves a mark: select some text and keep it highlighted, or attach a remark to a part of the notebook. The marks are saved in a file somewhere, so they are there again when the same notebook is opened on the tablet or on the desktop.

**Decided (Anton, 2026-10-08): only where lectern serves the pages.** A site made by `lectern build`, such as the notebooks published from a GitHub workflow, is for other people to read: its pages offer no way to mark or remark on anything and carry nobody's notes. Like the link guard and the start page, whatever is built for this is skipped when the page has `data-static`.

**Decided the same day, before building:**

- **The server will accept one kind of write.** A single `PUT` that can only replace the notes file of a document it already serves: the server works out the file's name, the request never names a path. It checks Host and Origin, takes JSON only (which a foreign web page cannot send), caps the size, checks the shape and writes the file itself. Still no token; what a device on the Wi-Fi can do is add and delete notes. On by default, with a setting in `config.toml` to turn it off.
- **Notes live beside the document:** `analysis.ipynb` gets `analysis.notes.json`. Visible in git and travelling with the repository. Never handed out as a file and never published by `lectern build`.
- **A mark finds its text again** by the id of its cell, the quoted words and 32 characters either side. One whose words are gone is kept and shown as orphaned.
- **Back to the laptop:** `lectern notes PATH` prints markdown, each remark under its cell number and nearest heading. The JSON is the only file written.
- **The touch interaction is tried before the rest is built**, in two variants.

**Stage 1, built 2026-10-08: the interaction, kept in the browser.** Marks are in `localStorage` on the one device; nothing is sent to the server yet. Settings has "Marking text" with the two variants and Off:

- **On selection:** select text the usual way; a small strip with Highlight and Note appears at the top or the bottom of the screen, whichever is farther from the selection. The first try put it under the selection, where the iPad puts its own menu (Android puts its above); a page can neither add to those menus nor tell where they will be, but they are always close to the selection.
- **Marking mode:** a pen in the top bar switches it on; while it is on, whatever is selected becomes a highlight when the finger lifts.
- Either way, a tap on a mark shows its note, with Add or Edit note and Remove.

**To judge on the iPad (Safari, Chrome, the Home Screen app) and the Boox:** whether the strip is noticed at the edge and stays clear of the system's own menu; whether a tap on a mark lands; whether a word marked in the mode before the selection could be widened is a nuisance (press, drag, then lift is the way to mark more than a word); how the marks read on e-ink, where black-only shows them as a heavy underline and a double one for a note.

**Stage 2, after a variant is chosen:** the notes file and the `PUT`, the setting that turns it off, a list of the document's notes with the orphaned ones, `lectern notes`, and the losing variant and its setting removed. Not planned: a remark on something with no text to select (a figure, a whole cell), and highlight colours.

## 2. Postponed from the first round of feedback

- **Column width as a free setting.** There are five fixed steps now (narrow, medium, wide, wider, full), and everything shares one column. A slider if the steps turn out too coarse.
- **A more file-oriented listing.** First impression was that it should show more of the files; after using it, it seemed fine. Left as it is, apart from naming the file on every row.
- **Leaving folders out.** `lectern serve` in agent-memory-eval also serves its `private/` directory. An ignore list (per folder, or a `.lecternignore`) would let a folder be served without everything in it.
- **"Continue reading" on the listing**, filled from the saved reading positions (HANDOFF section 9).
- **Reading the fold marker and the page turns on the devices.** Both were built on 2026-10-08 and checked only in desktop browsers. To judge on the iPad and the Boox: whether the marker beside a heading is easy enough to hit, whether two lines carried over to the next page is the right number (`CARRY_LINES` in `reader.js`), and whether the blank strip above the footer reads as the end of the page or as something missing.
- **Fonts for e-ink.** Nothing is bundled; the theme uses whatever serif and monospace the tablet has. Decide after seeing it on the device.
