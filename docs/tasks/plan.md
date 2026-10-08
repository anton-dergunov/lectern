# Tasks beyond the milestones

Ideas and postponed items that came out of using lectern. The milestones themselves are in `HANDOFF.md`, section 13. Nothing here is started.

## 1. Postponed from the first round of feedback

- **Column width as a free setting.** There are five fixed steps now (narrow, medium, wide, wider, full), and everything shares one column. A slider if the steps turn out too coarse.
- **A more file-oriented listing.** First impression was that it should show more of the files; after using it, it seemed fine. Left as it is, apart from naming the file on every row.
- **Leaving folders out.** `lectern serve` in agent-memory-eval also serves its `private/` directory. An ignore list (per folder, or a `.lecternignore`) would let a folder be served without everything in it.
- **"Continue reading" on the listing**, filled from the saved reading positions (HANDOFF section 9).
- **Reading the fold marker and the page turns on the devices.** Both were built on 2026-10-08 and checked only in desktop browsers. To judge on the iPad and the Boox: whether the marker beside a heading is easy enough to hit, whether two lines carried over to the next page is the right number (`CARRY_LINES` in `reader.js`), and whether the blank strip above the footer reads as the end of the page or as something missing.
- **Fonts for e-ink.** Nothing is bundled; the theme uses whatever serif and monospace the tablet has. Decide after seeing it on the device.

## 2. Left over from highlights and notes

Built on 2026-10-08; `HANDOFF.md` describes it. Not done:

- **A remark on something with no text to select:** a figure, or a whole cell.
- **Highlight colours.**
- **Showing on the listing which documents have notes.**
- **Trying the saving on the tablets.** The marking itself was tried on the iPad and on Android while marks were still kept in the browser. Saving to the Mac, the list of marks and the dot for an unsaved mark have only been checked in desktop browsers.
