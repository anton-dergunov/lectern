# Tasks beyond the milestones

Ideas and postponed items that came out of using lectern. The milestones themselves are in `HANDOFF.md`, section 13. Nothing here is started.

## 1. Notes and highlights on a notebook

**The idea (Anton, 2026-10-06, after the first iPad session).** Reading is the main use, but sometimes a passage deserves a mark: select some text and keep it highlighted, or attach a remark to a part of the notebook. The marks are saved in a file somewhere, so they are there again when the same notebook is opened on the tablet or on the desktop.

**Out of scope for now.** Recorded so it can be picked up as a follow-up.

**What has to be decided before building it:**

- **It needs the server to accept writes.** Today lectern answers `GET` and `HEAD` only, and running without a token rests on that: nothing a device sends can change anything on the Mac (HANDOFF decisions 2 and 7). Saving a note is a write. The narrowest form would be one endpoint that can only append to or replace a notes file lectern itself owns, never a path the request names. Whether that is still acceptable without a token is the first question.
- **Where the notes live.** Beside the notebook (`name.notes.json`, visible in git and travelling with the repo), or in lectern's own directory keyed by path (invisible to the repo, lost if the notebook moves).
- **How a mark finds its text again after the notebook changes.** Cell id plus the quoted text and a little context around it is the usual answer; a mark whose text is gone should be shown as orphaned, not dropped.
- **Selecting text on a touch screen** competes with the system's own selection menu; the interaction needs trying on the iPad before anything else is built.
- **Getting the notes back to the laptop** in a form that is useful there: a markdown export per notebook, with each remark under the cell number it belongs to, may be worth more than the highlights themselves.

## 2. Postponed from the first round of feedback

- **Collapse and expand sections by heading**, working together with the contents list. Cells are rendered one after another with no section wrapper, so this means grouping cells under their heading at render time.
- **Column width as a free setting.** There are three steps now (narrow, medium, wide). A slider, or separate control over how much wider code and tables run than the prose, if the steps turn out too coarse.
- **Default text size on the desktop.** It reads slightly large there and slightly small on the tablet at the same 19 px. The setting is per device, so this may need nothing; otherwise a different default above a certain screen width.
- **A more file-oriented listing.** First impression was that it should show more of the files; after using it, it seemed fine. Left as it is, apart from naming the file on every row.
- **"Continue reading" on the listing**, filled from the saved reading positions (HANDOFF section 9).
- **Opening the Home Screen app while lectern is stopped.** In Chromium the start page is shown from the browser's cache and says that lectern is not running. WebKit, in testing, asks the network anyway and shows its own failure. A page that opens with no server needs a service worker, which browsers only allow over HTTPS; that makes this part of the Tailscale decision at the e-ink milestone (HANDOFF decision 12).
