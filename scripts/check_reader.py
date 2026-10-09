"""Drive the reader in real browsers and check what the unit tests cannot see.

    uv run --group shots python scripts/check_reader.py [--engine chromium|webkit]...

Runs against the test fixtures on a local port, in Chromium and WebKit. Checks the top
bar hiding, the reading position surviving a reload and a text-size change, settings,
the contents list, folding sections, long output, the e-ink theme's page turning, marking
text, going back and forward between documents, and what happens when the server stops.

Needs the browsers once: `uv run --group shots playwright install chromium webkit`.
"""

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

from _local import FIXTURES, LocalServer
from playwright.sync_api import Page, expect, sync_playwright

from lectern.build import SiteOptions, build

ENGINES = ["chromium", "webkit"]

# Where the reader's own script measures from: the first cell still showing below the bar.
PLACE = """() => {
  const line = document.querySelector('.bar').offsetHeight + 12;
  for (const cell of document.querySelectorAll('main.doc > .cell')) {
    const box = cell.getBoundingClientRect();
    if (box.bottom > line) return {cell: cell.id, frac: (line - box.top) / box.height};
  }
}"""


# Lines of text that the bar above or the footer (with the strip over it) below cuts through.
# The box of a line reaches a little past its letters, so a pixel or two is not a cut.
CUT_LINES = """() => {
  const top = document.querySelector('.bar').offsetHeight;
  const trim = document.querySelector('.page-trim');
  const bottom = innerHeight - document.querySelector('.pager').offsetHeight
    - (trim ? trim.offsetHeight : 0);
  const cut = [];
  const walker = document.createTreeWalker(document.querySelector('main.doc'), NodeFilter.SHOW_TEXT);
  const range = document.createRange();
  for (let node; (node = walker.nextNode()); ) {
    if (!node.data.trim()) continue;
    range.selectNodeContents(node);
    for (const box of range.getClientRects()) {
      for (const [name, edge] of [['top', top], ['bottom', bottom]]) {
        if (box.height && box.top < edge - 2 && box.bottom > edge + 2) {
          cut.push([name, Math.round(box.top), Math.round(box.bottom), edge]);
        }
      }
    }
  }
  return cut;
}"""

# Where the page's first line and the top of the strip are, measured down the document.
PAGE_EDGES = """() => {
  const trim = document.querySelector('.page-trim');
  const bottom = innerHeight - document.querySelector('.pager').offsetHeight
    - (trim ? trim.offsetHeight : 0);
  return {top: scrollY + document.querySelector('.bar').offsetHeight, bottom: scrollY + bottom,
          trim: trim ? trim.offsetHeight : 0};
}"""

# Selects words in a cell as a reader would, and brings them into view: in the middle of the
# screen, or with `block` at its start or its end.
SELECT = """([cell, words, nth, block]) => {
  const walker = document.createTreeWalker(document.getElementById(cell), NodeFilter.SHOW_TEXT);
  for (let node; (node = walker.nextNode()); ) {
    let at = -1;
    for (let n = 0; n <= nth; n++) at = node.data.indexOf(words, at + 1);
    if (at < 0) continue;
    const range = document.createRange();
    range.setStart(node, at);
    range.setEnd(node, at + words.length);
    node.parentElement.scrollIntoView({block: block || 'center'});
    getSelection().removeAllRanges();
    getSelection().addRange(range);
    return true;
  }
  return false;
}"""

# The marks on the page: how many plain and with a note, and for the first of them the cell
# it is in, how far into its paragraph it starts, and a point on it to tap.
MARKED = """() => {
  const plain = [...(CSS.highlights.get('lectern-mark') || [])];
  const noted = [...(CSS.highlights.get('lectern-note') || [])];
  const first = plain[0] || noted[0];
  const box = first && first.getClientRects()[0];
  return {
    plain: plain.length, noted: noted.length,
    cell: first ? first.startContainer.parentElement.closest('.cell').id : '',
    offset: first ? first.startOffset : -1,
    text: first ? String(first) : '',
    x: box ? box.left + box.width / 2 : 0, y: box ? box.top + box.height / 2 : 0,
  };
}"""

FONT_SIZE = "getComputedStyle(document.documentElement).fontSize"


def settle(page: Page) -> None:
    page.wait_for_timeout(500)


def theme(page: Page) -> str:
    return page.evaluate("document.documentElement.dataset.theme")


def bar_hidden(page: Page) -> bool:
    return page.evaluate("document.documentElement.classList.contains('bar-away')")


def check(name: str, ok: bool, detail: object = "") -> bool:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}{f'  ({detail})' if detail and not ok else ''}")
    return ok


def run(engine_name: str, playwright) -> bool:
    print(engine_name)
    results: list[bool] = []
    browser = getattr(playwright, engine_name).launch()
    context = browser.new_context(viewport={"width": 820, "height": 1180})
    # A test browser looks like a desktop; start from what a tablet starts with instead.
    context.add_init_script(
        """if (!localStorage.getItem('lectern:prefs'))
             localStorage.setItem('lectern:prefs', '{"size": 19, "width": "m"}')"""
    )
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    with LocalServer(FIXTURES) as server:
        long_read = server.url("long-read.ipynb")

        # ---- Top bar ----
        page.goto(long_read)
        page.evaluate("window.scrollTo(0, 2500)")
        try:
            # Not a fixed wait: the first page of a run can still be settling.
            page.wait_for_function(
                "document.documentElement.classList.contains('bar-away')", timeout=4000
            )
        except Exception:
            pass
        results.append(check("bar hides when reading down", bar_hidden(page)))
        page.evaluate("window.scrollTo(0, 2300)")
        settle(page)
        results.append(check("bar returns when scrolling up", not bar_hidden(page)))

        # ---- Reading position ----
        page.evaluate("window.scrollTo(0, 6000)")
        settle(page)
        before = page.evaluate(PLACE)
        page.reload()
        settle(page)
        after = page.evaluate(PLACE)
        same = after["cell"] == before["cell"] and abs(after["frac"] - before["frac"]) < 0.02
        results.append(check("same place after a reload", same, f"{before} -> {after}"))

        column = "document.querySelector('.cell.md p').getBoundingClientRect().width"
        column_before = page.evaluate(column)
        page.get_by_role("button", name="Reading settings").click()
        for _ in range(3):
            page.get_by_label("Larger text").click()
        size = page.evaluate("getComputedStyle(document.documentElement).fontSize")
        results.append(check("text size follows the setting", size == "22px", size))
        column_after = page.evaluate(column)
        unchanged = column_before == column_after == 700
        results.append(
            check(
                "and leaves the column as wide as it was", unchanged, (column_before, column_after)
            )
        )
        resized = page.evaluate(PLACE)
        same = resized["cell"] == after["cell"] and abs(resized["frac"] - after["frac"]) < 0.03
        results.append(check("same place after a text-size change", same, f"{after} -> {resized}"))

        # ---- Settings ----
        page.get_by_role("button", name="Dark", exact=True).click()
        results.append(check("dark mode", theme(page) == "solarized-dark", theme(page)))
        page.get_by_role("button", name="Black & white").click()
        results.append(check("black and white", theme(page) == "plain-dark", theme(page)))
        page.get_by_role("button", name="Hidden").click()
        open_cells = page.locator("details.src[open]").count()
        results.append(check("code hidden", open_cells == 0, open_cells))
        page.locator("#settings").get_by_role("button", name="Done").click()
        page.reload()
        settle(page)
        bar_color = page.evaluate("document.querySelector('meta[name=theme-color]').content")
        kept = theme(page) == "plain-dark" and bar_color == "#000000"
        kept = kept and page.locator("details.src[open]").count() == 0
        results.append(check("settings kept after a reload", kept, f"{theme(page)} {bar_color}"))
        page.get_by_role("button", name="Reading settings").click()
        page.get_by_role("button", name="Shown").click()
        page.get_by_role("button", name="Solarized").click()
        page.get_by_role("button", name="Light", exact=True).click()
        page.locator("#settings").get_by_role("button", name="Done").click()
        results.append(check("code shown again", page.locator("details.src[open]").count() > 0))

        # ---- Contents ----
        page.get_by_role("button", name="Contents").click()
        current = page.locator("#toc a[aria-current]").count()
        results.append(check("contents marks the current section", current == 1, current))
        page.locator("#toc").get_by_role("link", name="Part 9").click()
        settle(page)
        top = page.evaluate("document.getElementById('Part-9').getBoundingClientRect().top")
        landed = 0 <= top < 160 and not page.locator("#toc").is_visible()
        results.append(check("contents jumps to the heading", landed, top))
        results.append(check("bar stays after the jump", not bar_hidden(page)))

        # ---- Folding sections ----
        page.evaluate("window.scrollTo(0, 600)")
        settle(page)
        heading = page.locator("#Part-2")
        under = [page.locator("#Part-2 + p"), page.locator("#c-cell-4")]
        top = "e => e.getBoundingClientRect().top"
        before = heading.evaluate(top)
        heading.locator(".fold").click()
        folded = not any(block.is_visible() for block in under)
        results.append(check("a heading folds what is under it", folded))
        next_shown = page.locator("#Part-3").is_visible()
        results.append(check("up to the next heading of its level", next_shown))
        results.append(
            check("and stays where it was", abs(heading.evaluate(top) - before) < 1, before)
        )
        page.reload()
        settle(page)
        still = not any(block.is_visible() for block in under)
        results.append(check("folded sections are kept after a reload", still))
        page.get_by_role("button", name="Contents").click()
        marked = page.locator("#toc a[data-folded]").all_inner_texts()
        results.append(check("the contents list marks them", marked == ["Part 2"], marked))
        page.locator("#toc").get_by_role("button", name="Collapse all").click()
        shown = page.locator("main.doc .cell.code:visible").count()
        outline = page.locator("#Part-7").is_visible() and page.locator("h1").is_visible()
        aside = page.locator("#Aside-1").is_visible()
        results.append(
            check("collapse all leaves the outline", shown == 0 and outline and not aside, shown)
        )
        page.locator("#toc").get_by_role("link", name="Aside 1").click()
        settle(page)
        at = page.locator("#Aside-1").evaluate(top)
        # With everything else folded the page is too short to bring it to the top.
        opened = page.locator("#Aside-1 + p").is_visible() and 0 <= at < 600
        results.append(check("a contents link opens the way to its section", opened, at))
        results.append(check("and nothing else", not page.locator("#c-cell-4").is_visible()))
        page.get_by_role("button", name="Contents").click()
        page.locator("#toc").get_by_role("button", name="Expand all").click()
        page.locator("#toc").get_by_role("button", name="Done").click()
        every = page.locator("main.doc .cell.code:visible").count()
        kept = page.evaluate("Object.keys(localStorage).filter(k => k.startsWith('lectern:fold'))")
        results.append(check("expand all shows everything again", every == 12 and not kept, every))
        moved = page.locator("#Aside-1").evaluate(top) - at
        results.append(check("and keeps the place", abs(moved) < 1, moved))

        # ---- Long and wide output ----
        page.goto(server.url("tall-stream.ipynb"))
        lines = page.locator("pre.stream .l")
        shown = sum(1 for i in range(lines.count()) if lines.nth(i).is_visible())
        results.append(check("long output starts at 30 lines", shown == 30, shown))
        page.get_by_role("button", name="Show all 80 lines").click()
        shown = sum(1 for i in range(lines.count()) if lines.nth(i).is_visible())
        results.append(check("and opens to all of them", shown == 80, shown))

        page.goto(server.url("long-stream-lines.ipynb"))
        fits = "pre => pre.scrollWidth <= pre.clientWidth"
        results.append(check("wide output wraps", page.locator("pre.stream").evaluate(fits)))
        page.get_by_role("button", name="No wrap").click()
        results.append(check("or scrolls", not page.locator("pre.stream").evaluate(fits)))

        page.goto(server.url("long-code-cell.ipynb"))
        number = page.locator(".cell-n").inner_text()
        closed = page.locator("details.src[open]").count() == 0
        results.append(check("cell number, long cell closed", number == "[7]" and closed, number))
        name_token = page.locator(".highlight .n").first
        page.locator("details.src summary").click()
        position = name_token.evaluate("e => getComputedStyle(e).position")
        results.append(check("code tokens are laid out normally", position == "static", position))

        # ---- Math ----
        fetched: list[str] = []
        page.on("request", lambda request: fetched.append(request.url))
        page.goto(server.url("math.ipynb"))
        typeset = page.locator(".math.typeset .katex").count()
        results.append(check("math is typeset", typeset == 3, typeset))
        printed = page.locator("pre.stream").inner_text()
        results.append(check("a printed dollar sign is left alone", "$x$" in printed, printed))
        page.goto(server.url("latex-output.ipynb"))
        shown = page.locator(".out .math.typeset").inner_text()
        results.append(
            check("a LaTeX output is typeset too", "$" not in shown and "x" in shown, shown)
        )
        fetched.clear()
        page.goto(server.url("stderr.ipynb"))
        page.wait_for_load_state("networkidle")
        asked = [url for url in fetched if "katex" in url]
        results.append(check("a page without math fetches no math typesetting", not asked, asked))

        page.goto(server.url("long-traceback.ipynb"))
        folded = not page.locator("pre.error").is_visible()
        page.locator(".traceback summary").click()
        opened = page.locator("pre.error").is_visible()
        results.append(check("a long traceback starts folded and opens", folded and opened))

        # ---- Raw HTML, pictures, and which file this is ----
        page.goto(server.url("raw-html-in-markdown.ipynb"))
        hidden = page.get_by_text("Hidden text.")
        folded = not hidden.is_visible()
        page.get_by_text("More").click()
        results.append(check("raw <details> folds and opens", folded and hidden.is_visible()))
        weight = page.locator(".cell.md b").evaluate("e => getComputedStyle(e).fontWeight")
        results.append(check("raw <b> is bold", int(weight) >= 600, weight))
        here = page.locator(".crumbs .here")
        named = here.inner_text() == "raw-html-in-markdown.ipynb"
        results.append(
            check("the bar names the file", named and here.is_visible(), here.inner_text())
        )
        page.goto(server.url("plotly-with-picture.ipynb"))
        size = page.locator("figure.img img").evaluate("e => [e.naturalWidth, e.clientWidth]")
        results.append(check("a saved picture is shown at its size", size == [480, 480], size))

        # ---- One column ----
        page.goto(long_read)
        widths = page.evaluate(
            """() => ['.cell.md p', '.cell.code .highlight', '.cell.code .out'].map(
                 s => Math.round(document.querySelector(s).getBoundingClientRect().right))"""
        )
        results.append(
            check("prose, code and output end at the same edge", len(set(widths)) == 1, widths)
        )
        page.get_by_role("button", name="Reading settings").click()
        offered = page.locator("[data-pref=width]:visible").all_inner_texts()
        # Wide already fills this screen, so the steps beyond it are left out.
        results.append(
            check(
                "widths that change nothing are not offered",
                offered == ["Narrow", "Medium", "Wide"],
                offered,
            )
        )

        # ---- E-ink ----
        page.get_by_role("button", name="E-ink").click()
        results.append(check("e-ink theme", theme(page) == "eink", theme(page)))
        results.append(
            check(
                "light and dark do not apply to it", not page.locator("[data-modes]").is_visible()
            )
        )
        page.locator("#settings").get_by_role("button", name="Done").click()
        page.evaluate("window.scrollTo(0, 0)")
        settle(page)
        label = page.locator(".pager output")
        first = label.inner_text()
        results.append(
            check("pager counts pages", first.startswith("1 / ") and int(first[4:]) > 3, first)
        )
        page.get_by_role("button", name="Next").click()
        page.wait_for_timeout(150)
        moved = page.evaluate("window.scrollY")
        screen = page.evaluate("window.innerHeight")
        results.append(
            check("next turns most of a screen, at once", 0.6 * screen < moved < screen, moved)
        )
        results.append(
            check("and counts it", label.inner_text().startswith("2 / "), label.inner_text())
        )
        results.append(
            check("on whole lines", not page.evaluate(CUT_LINES), page.evaluate(CUT_LINES))
        )
        edges = page.evaluate(PAGE_EDGES)
        page.mouse.click(790, 500)
        results.append(
            check("a tap on the right edge turns on", page.evaluate("window.scrollY") > moved * 1.7)
        )
        # What the footer was about to cut through is on the new page, a line or two down.
        carried = edges["bottom"] - page.evaluate(PAGE_EDGES)["top"]
        results.append(check("carrying over the last lines", 30 < carried < 130, carried))
        cut = []
        for _ in range(8):
            page.get_by_role("button", name="Next").click()
            cut += page.evaluate(CUT_LINES)
        for _ in range(8):
            page.get_by_role("button", name="Previous").click()
            cut += page.evaluate(CUT_LINES)
        results.append(check("every turn ends on whole lines", not cut, cut))
        # Not every page ends in the middle of a line; go on to one that does.
        covered = 0
        for _ in range(6):
            page.get_by_role("button", name="Next").click()
            covered = page.evaluate(PAGE_EDGES)["trim"]
            if covered:
                break
        page.evaluate("window.scrollBy(0, 37)")
        settle(page)
        gone = page.evaluate(PAGE_EDGES)["trim"] == 0
        results.append(check("scrolling by hand uncovers the last line", covered and gone, covered))
        page.evaluate("window.scrollTo(0, %d)" % moved)
        page.mouse.click(790, 500)
        page.mouse.click(30, 500)
        back = page.evaluate("window.scrollY")
        results.append(check("a tap on the left edge turns back", abs(back - moved) < 1, back))
        # Through code and printed output, where a line is not the height of a line of prose.
        strayed = []
        for _ in range(7):
            page.get_by_role("button", name="Next").click()
            here = page.evaluate(PAGE_EDGES)
            page.get_by_role("button", name="Previous").click()
            page.get_by_role("button", name="Previous").click()
            page.get_by_role("button", name="Next").click()
            page.get_by_role("button", name="Next").click()
            if page.evaluate(PAGE_EDGES) != here:
                strayed.append((here, page.evaluate(PAGE_EDGES)))
        results.append(check("back and then forward again is the same page", not strayed, strayed))
        back = page.evaluate("window.scrollY")
        page.mouse.click(400, 500)
        results.append(
            check("a tap in the middle does nothing", page.evaluate("window.scrollY") == back)
        )
        page.keyboard.press("PageDown")
        results.append(
            check("the page key turns on", page.evaluate("window.scrollY") > back + 0.6 * screen)
        )
        page.get_by_role("button", name="End", exact=True).click()
        page.wait_for_timeout(150)
        last_page = label.inner_text().split(" / ")
        at_end = page.evaluate(
            "window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 1"
        )
        results.append(
            check("end goes to the last page", at_end and last_page[0] == last_page[1], last_page)
        )

        bar_height = page.locator(".bar").evaluate("e => e.offsetHeight")
        label.click()
        hidden = not page.locator(".bar").is_visible()
        page.reload()
        settle(page)
        still_hidden = not page.locator(".bar").is_visible()
        results.append(
            check(
                "a tap on the page number puts the bar away, and it stays away",
                hidden and still_hidden,
            )
        )
        label.click()
        back_again = page.locator(".bar").evaluate("e => e.offsetHeight") == bar_height
        results.append(check("and another brings it back", back_again))

        page.get_by_role("button", name="Reading settings").click()
        page.get_by_role("button", name="With colour").click()
        coloured = page.locator(".highlight .nb").first.evaluate("e => getComputedStyle(e).color")
        text = page.evaluate("getComputedStyle(document.body).color")
        results.append(
            check(
                "colour e-ink colours code, not text",
                theme(page) == "eink-colour" and coloured != text == "rgb(0, 0, 0)",
                (coloured, text),
            )
        )
        page.get_by_role("button", name="Black only").click()
        mono = page.locator(".highlight .nb").first.evaluate("e => getComputedStyle(e).color")
        results.append(
            check("black only is black", theme(page) == "eink" and mono == "rgb(0, 0, 0)", mono)
        )
        page.locator("#settings").get_by_role("button", name="Done").click()

        page.get_by_role("button", name="Start", exact=True).click()
        page.wait_for_timeout(150)
        at_top = page.evaluate("window.scrollY") == 0
        results.append(
            check("top goes to the top", at_top and label.inner_text().startswith("1 / "))
        )
        blank = page.get_by_role("button", name="Previous").evaluate(
            "e => e.disabled && getComputedStyle(e).color === 'rgba(0, 0, 0, 0)'"
        )
        results.append(check("a button with nowhere to go is blank", blank))
        results.append(check("the bar stays put", not bar_hidden(page)))
        still = page.evaluate(
            """() => [...document.querySelectorAll('.bar, .sheet, .src summary, a')].every(e => {
                 const style = getComputedStyle(e);
                 return style.transitionDuration.split(', ').every(d => d === '0s')
                     && style.animationName === 'none';
               })"""
        )
        results.append(check("nothing is animated", still))
        page.goto(server.url("markdown-table-and-fence.ipynb"))
        wraps = page.locator(".highlight pre").first.evaluate("e => getComputedStyle(e).whiteSpace")
        results.append(check("code wraps instead of scrolling", wraps == "pre-wrap", wraps))
        page.get_by_role("button", name="Reading settings").click()
        page.get_by_role("button", name="Solarized").click()
        page.locator("#settings").get_by_role("button", name="Done").click()
        results.append(check("pager gone outside e-ink", not page.locator(".pager").is_visible()))

        reader = browser.new_context(
            viewport={"width": 702, "height": 936},
            user_agent="Mozilla/5.0 (Linux; Android 12; NoteAir3C BOOX) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
        )
        first_visit = reader.new_page()
        first_visit.goto(long_read)
        detected = theme(first_visit)
        results.append(
            check("an e-ink device starts in the e-ink theme", detected == "eink", detected)
        )
        size = first_visit.evaluate(FONT_SIZE)
        results.append(check("with smaller text", size == "16px", size))
        reader.close()

        pocket = browser.new_context(viewport={"width": 390, "height": 844})
        phone = pocket.new_page()
        phone.goto(long_read)
        size = phone.evaluate(FONT_SIZE)
        results.append(check("a phone starts with smaller text", size == "16px", size))
        phone.get_by_role("button", name="Reading settings").click()
        no_choice = not phone.locator("[data-width-setting]").is_visible()
        results.append(check("and is not asked for a column width", no_choice))
        pocket.close()

        wide = browser.new_context(viewport={"width": 1440, "height": 900})
        desktop = wide.new_page()
        desktop.goto(long_read)
        start = (
            desktop.evaluate(FONT_SIZE),
            desktop.evaluate("document.documentElement.dataset.width"),
        )
        results.append(check("a desktop starts at 17 px and wide", start == ("17px", "w"), start))
        desktop.get_by_role("button", name="Reading settings").click()
        offered = desktop.locator("[data-pref=width]:visible").all_inner_texts()
        results.append(check("a desktop is offered all five widths", len(offered) == 5, offered))
        desktop.get_by_role("button", name="Full").click()
        column = desktop.locator(".cell.md p").first.evaluate(
            "e => e.getBoundingClientRect().width"
        )
        results.append(check("full uses the whole window", column > 1380, column))
        wide.close()

        # ---- The server stops while a page is open ----
        page.goto(long_read)
        server.stop()
        page.locator(".crumbs a").last.click()
        try:
            expect(page.locator("#offline")).to_contain_text("not running", timeout=6000)
            results.append(check("following a link says lectern is not running", True))
        except AssertionError as error:
            results.append(check("following a link says lectern is not running", False, error))
        still_here = page.url == long_read
        results.append(check("and stays on the page", still_here, page.url))
        server.start()
        try:
            page.wait_for_url(server.url(""), timeout=8000)
            results.append(check("and goes on by itself once it is back", True))
        except Exception as error:
            results.append(check("and goes on by itself once it is back", False, error))

        # ---- Opening a page directly while the server is stopped ----
        # This address counts as secure, so the service worker is installed here as it is
        # behind HTTPS, and stands in for the browser's own error page.
        direct = context.new_page()
        direct.goto(long_read)
        try:
            direct.evaluate("navigator.serviceWorker.ready.then(() => true)")
            direct.wait_for_function("navigator.serviceWorker.controller !== null", timeout=5000)
            server.stop()
            direct.goto(long_read)
            expect(direct.locator(".offline-msg")).to_contain_text("not running", timeout=6000)
            results.append(check("a page asked for directly says lectern is not running", True))
            logo = direct.locator(".offline-icon").evaluate("e => e.naturalWidth > 0")
            styled = (
                direct.evaluate(FONT_SIZE) != "16px" or direct.locator("[data-retry]").is_visible()
            )
            results.append(check("with its logo, styles and a retry button", logo and styled))
            direct.get_by_role("button", name="Try again").click()
            server.start()
            direct.wait_for_selector("main.doc", timeout=8000)
            results.append(
                check("and loads that page once it is back", direct.url == long_read, direct.url)
            )
        except Exception as error:
            print(f"  note no service worker here  ({str(error).splitlines()[0][:90]})")
            results.append(engine_name == "webkit")
            if not server._server:
                server.start()
        direct.close()

        # ---- Opening the app with the server stopped ----
        start = context.new_page()
        start.goto(server.origin + "/")
        try:
            start.wait_for_url(server.url(""), timeout=8000)
            results.append(check("start page goes to the listing", True))
        except Exception as error:
            results.append(check("start page goes to the listing", False, error))
        start.close()
        server.stop()
        start = context.new_page()
        try:
            start.goto(server.origin + "/")
            expect(start.locator(".offline-msg")).to_be_visible(timeout=6000)
            results.append(check("start page opens from cache and says not running", True))
            server.start()
            start.wait_for_url(server.url(""), timeout=8000)
            results.append(check("and opens the listing once it is back", True))
        except Exception as error:
            # WebKit asks the network for a page it holds a fresh copy of, so with the
            # server stopped it shows its own error instead. Reported, not counted.
            print(f"  note start page not shown from cache  ({str(error).splitlines()[0]})")
            results.append(engine_name == "webkit")

    # ---- A notebook saved again while it is being read ----
    with tempfile.TemporaryDirectory() as work:
        notebook = Path(work, "desk", "draft.ipynb")
        notebook.parent.mkdir()
        original = (FIXTURES / "long-read.ipynb").read_text()
        notebook.write_text(original)
        with LocalServer(notebook.parent) as desk:
            follower = context.new_page()
            follower.goto(desk.url("draft.ipynb"))
            follower.get_by_role("button", name="Reading settings").click()
            follower.get_by_role("button", name="Reload automatically").click()
            follower.locator("#settings").get_by_role("button", name="Done").click()
            follower.evaluate("window.scrollTo(0, 4000)")
            follower.wait_for_timeout(2500)
            place = follower.evaluate(PLACE)
            notebook.write_text(original.replace("A shorter remark.", "A remark, revised."))
            try:
                expect(follower.get_by_text("A remark, revised.").first).to_be_attached(
                    timeout=8000
                )
                again = follower.evaluate(PLACE)
                kept = again["cell"] == place["cell"] and abs(again["frac"] - place["frac"]) < 0.05
                results.append(
                    check("a saved notebook is shown again, in the same place", kept, again)
                )
            except AssertionError:
                results.append(check("a saved notebook is shown again, in the same place", False))
            follower.get_by_role("button", name="Reading settings").click()
            follower.get_by_role("button", name="Keep this page").click()
            follower.close()

    # ---- Marking text ----
    # In a copy of the fixture: the notes are written to a file beside the notebook.
    with tempfile.TemporaryDirectory() as work:
        desk_dir = Path(work, "desk")
        desk_dir.mkdir()
        shutil.copy(FIXTURES / "long-read.ipynb", desk_dir)
        notes_file = desk_dir / "long-read.notes.json"

        def kept() -> list[dict]:
            return json.loads(notes_file.read_text())["notes"] if notes_file.exists() else []

        def centre_first_mark(page: Page) -> None:
            page.evaluate(
                """() => [...CSS.highlights.get('lectern-mark'), ...CSS.highlights.get('lectern-note')][0]
                         .startContainer.parentElement.scrollIntoView({block: 'center'})"""
            )

        marker = context.new_page()
        marker.on("pageerror", lambda error: errors.append(str(error)))
        can_mark = marker.evaluate("Boolean(window.Highlight && window.CSS && CSS.highlights)")
        if not can_mark:
            print("  note marking text needs the CSS highlight API, which this browser lacks")
        with LocalServer(desk_dir, notes=False) as reading_only:
            marker.goto(reading_only.url("long-read.ipynb"))
            settle(marker)
            none = marker.locator(".mark-pen").is_hidden()
            results.append(check("a server that keeps no notes offers no pen", none))
        with LocalServer(desk_dir) as desk:
            marker.goto(desk.url("long-read.ipynb"))
            pen = marker.get_by_role("button", name="Mark what is selected")
            pop = marker.locator(".mark-pop")
            listed = marker.get_by_role("button", name="Notes")
            if can_mark:
                expect(pen).to_be_visible()
                marker.evaluate(SELECT, ["c-cell-5", "prose to read", 2])
                marker.wait_for_timeout(1300)
                idle = marker.evaluate(MARKED)["plain"] == 0 and not listed.is_visible()
                results.append(check("with the pen off, selecting marks nothing", idle))
                pen.click()
                # The same words many times over in the cell: the third of them is marked.
                marker.evaluate(SELECT, ["c-cell-5", "prose to read", 2])
                marker.wait_for_timeout(1300)
                made = marker.evaluate(MARKED)
                done = made["plain"] == 1 and made["text"] == "prose to read"
                done = done and marker.evaluate("String(getSelection())") == ""
                results.append(check("with it on, a selection becomes a mark", done, made))
                saved = [note["quote"] for note in kept()] == ["prose to read"]
                results.append(check("and is written beside the notebook", saved, kept()))
                marker.reload()
                settle(marker)
                centre_first_mark(marker)
                again = marker.evaluate(MARKED)
                same = again["plain"] == 1 and again["cell"] == "c-cell-5"
                same = same and again["offset"] == made["offset"]
                same = same and pen.get_attribute("aria-pressed") == "false"
                results.append(check("the mark is there again, on the same words", same, again))

                marker.mouse.click(again["x"], again["y"])
                pop.get_by_role("button", name="Add note").click()
                marker.locator(".note-editor textarea").fill("Is this the third?")
                marker.locator(".note-editor").get_by_role("button", name="Save").click()
                settle(marker)
                noted = marker.evaluate(MARKED)
                written = noted["noted"] == 1 and noted["plain"] == 0
                written = written and [note["note"] for note in kept()] == ["Is this the third?"]
                results.append(check("a note can be put on it", written, (noted, kept())))

                # Another device marks the title meanwhile; this page does not know.
                theirs = {
                    "id": "theirs",
                    "cell": "c-no-longer",
                    "start": 0,
                    "quote": "A long read",
                    "prefix": "",
                    "suffix": "An opening paragraph",
                }
                gone = {
                    "id": "gone",
                    "cell": "c-cell-1",
                    "start": 12,
                    "quote": "words that were deleted",
                    "prefix": "before ",
                    "suffix": " after",
                    "note": "Kept all the same",
                }
                notes_file.write_text(json.dumps({"version": 1, "notes": [*kept(), theirs, gone]}))
                pen.click()
                marker.evaluate(SELECT, ["c-cell-7", "prose to read", 0])
                marker.wait_for_timeout(1500)
                ids = {note["id"] for note in kept()}
                both = len(ids) == 4 and {"theirs", "gone"} < ids
                both = both and marker.evaluate(MARKED)["plain"] == 2
                results.append(check("marks made on two devices at once are all kept", both, ids))
                pen.click()

                listed.click()
                sheet = marker.locator("#notes")
                # Not modal: that makes the page inert, and WebKit takes marks off inert text.
                behind = marker.evaluate(
                    """() => !document.querySelector('#notes').matches(':modal')
                             && !document.querySelector('.sheet-shade').hidden"""
                )
                results.append(check("the list leaves the page behind it as it is", behind))
                entries = sheet.locator(".noted")
                lost = sheet.locator("div.noted")
                shown = entries.count() == 4 and lost.count() == 1
                shown = shown and "words that were deleted" in lost.text_content()
                results.append(
                    check("the list has every mark, the one whose words are gone apart", shown)
                )
                first = sheet.locator("a.noted").first
                found = first.locator("q").text_content() == "A long read"
                results.append(check("a mark is found again in a cell that was replaced", found))
                sheet.locator("a.noted").last.click()
                settle(marker)
                there = marker.evaluate(
                    """() => { const box = [...CSS.highlights.get('lectern-mark')].pop().getBoundingClientRect();
                               return !document.querySelector('#notes').open && box.top > 0 && box.top < innerHeight / 2; }"""
                )
                results.append(check("and each entry leads to its place", there))
                listed.click()
                lost.get_by_role("button", name="Remove").click()
                settle(marker)
                dropped = lost.count() == 0 and "gone" not in {note["id"] for note in kept()}
                results.append(check("a mark with nowhere to be can be removed there", dropped))
                marker.mouse.click(20, 400)
                settle(marker)
                shut = not sheet.is_visible() and marker.locator(".sheet-shade").is_hidden()
                results.append(check("a tap beside the list puts it away", shut))

                # The Mac asleep: what is marked waits, and is saved when it is back.
                desk.stop()
                pen.click()
                marker.evaluate(SELECT, ["c-cell-10", "prose to read", 0])
                marker.wait_for_timeout(1500)
                waiting = pen.get_attribute("data-unsaved") is not None and len(kept()) == 3
                desk.start()
                marker.wait_for_timeout(6500)
                arrived = pen.get_attribute("data-unsaved") is None and len(kept()) == 4
                results.append(
                    check(
                        "a mark made with the server away is saved on its return",
                        waiting and arrived,
                    )
                )
                pen.click()

                marker.reload()
                settle(marker)
                noted = marker.evaluate(MARKED)
                marker.evaluate(
                    """() => [...CSS.highlights.get('lectern-note')][0].startContainer.parentElement
                             .scrollIntoView({block: 'center'})"""
                )
                noted = marker.evaluate(
                    """() => { const box = [...CSS.highlights.get('lectern-note')][0].getClientRects()[0];
                               return {x: box.left + box.width / 2, y: box.top + box.height / 2}; }"""
                )
                marker.mouse.click(noted["x"], noted["y"])
                shown = pop.locator("p").text_content() == "Is this the third?"
                results.append(check("a tap on the mark shows the note", shown))
                marker.evaluate("window.notedBefore = CSS.highlights.get('lectern-note')")
                pop.get_by_role("button", name="Remove").click()
                settle(marker)
                removed = marker.evaluate(MARKED)["noted"] == 0 and len(kept()) == 3
                results.append(check("Remove takes the mark and its note", removed, kept()))
                # Safari repaints the words a range leaves, not those of a replaced highlight.
                emptied = marker.evaluate(
                    "CSS.highlights.get('lectern-note') === window.notedBefore"
                )
                results.append(
                    check("by emptying the highlight it was in, not replacing it", emptied)
                )

                marker.get_by_role("button", name="Reading settings").click()
                marker.get_by_role("button", name="E-ink").click()
                marker.locator("#settings").get_by_role("button", name="Done").click()
                marker.evaluate("window.scrollTo(0, 0)")
                settle(marker)
                title = marker.evaluate(MARKED)
                marker.mouse.click(title["x"], title["y"])
                stayed = pop.is_visible() and marker.evaluate("window.scrollY") == 0
                marker.mouse.click(700, 600)
                settle(marker)
                stayed = stayed and not pop.is_visible() and marker.evaluate("window.scrollY") == 0
                results.append(
                    check("on e-ink a tap on a mark, or to put it away, turns no page", stayed)
                )
                pop_gone = marker.evaluate(MARKED)
                marker.mouse.click(pop_gone["x"], pop_gone["y"])
                pop.get_by_role("button", name="Remove").click()
                for _ in range(2):
                    settle(marker)
                    left = marker.evaluate(MARKED)
                    marker.evaluate("window.scrollTo(0, 0)")
                    centre_first_mark(marker)
                    left = marker.evaluate(MARKED)
                    marker.mouse.click(left["x"], left["y"])
                    pop.get_by_role("button", name="Remove").click()
                settle(marker)
                cleared = not notes_file.exists() and not listed.is_visible()
                results.append(check("with the last mark gone, so is the file", cleared, kept()))
        marker.close()

    # ---- Back and forward between documents ----
    with tempfile.TemporaryDirectory() as work:
        shelf = Path(work, "shelf")
        shelf.mkdir()
        prose = "Sentence after sentence of prose to read. " * 30
        first_text = f"# First\n\n{prose}\n\n" * 4 + f"See [the other](second.md).\n\n{prose}\n"
        Path(shelf, "first.md").write_text(first_text)
        Path(shelf, "second.md").write_text(f"# Second\n\n{prose}\n")
        with LocalServer(shelf) as library:
            walker = context.new_page()
            walker.on("pageerror", lambda error: errors.append(str(error)))
            walker.goto(library.url("first.md"))
            chevron = walker.locator(".bar a.back")
            fresh = chevron.get_attribute("aria-label") == "Back to shelf"
            fresh = fresh and walker.locator(".bar a.forward").count() == 0
            results.append(check("a page opened by itself has the folder behind it", fresh))
            walker.get_by_role("link", name="the other").scroll_into_view_if_needed()
            settle(walker)
            left_at = walker.evaluate("window.scrollY")
            walker.get_by_role("link", name="the other").click()
            walker.wait_for_url(library.url("second.md"))
            walker.get_by_role("link", name="Back to First").click()
            walker.wait_for_url(library.url("first.md"))
            settle(walker)
            returned = walker.evaluate("window.scrollY")
            same = left_at > 40 and abs(returned - left_at) < 3
            results.append(
                check("back returns to the document and the place", same, (left_at, returned))
            )
            walker.get_by_role("link", name="Forward to Second").click()
            walker.wait_for_url(library.url("second.md"))
            there = walker.locator(".bar a.forward").count() == 0
            there = there and chevron.get_attribute("aria-label") == "Back to First"
            results.append(check("forward goes on again", there))
            walker.go_back()
            walker.wait_for_url(library.url("first.md"))
            settle(walker)
            followed = walker.locator(".bar a.forward").get_attribute("aria-label")
            results.append(
                check(
                    "the browser's own back is followed", followed == "Forward to Second", followed
                )
            )
            walker.locator(".crumbs a").last.click()
            walker.wait_for_url(library.url(""))
            results.append(
                check(
                    "a new turning forgets the way forward",
                    walker.locator("a.forward").count() == 0,
                )
            )
            walker.close()

    # ---- A static build, opened straight from the disk ----
    with tempfile.TemporaryDirectory() as site:
        build(FIXTURES, Path(site), SiteOptions(title="Fixtures"))
        blocked: list[str] = []
        local = context.new_page()
        local.on("pageerror", lambda error: errors.append(str(error)))
        local.on("console", lambda m: blocked.append(m.text) if m.type == "error" else None)
        local.goto(Path(site, "index.html").as_uri())
        local.get_by_role("link", name="A long read").click()
        opened = local.url.endswith("/long-read.html") and local.locator("main.doc").is_visible()
        results.append(check("built pages open from the disk and link to each other", opened))
        results.append(check("with their styles", local.evaluate(FONT_SIZE) == "19px"))
        local.get_by_role("button", name="Reading settings").click()
        local.get_by_role("button", name="Dark", exact=True).click()
        results.append(check("and their settings", theme(local) == "solarized-dark", theme(local)))
        local.get_by_role("button", name="Light", exact=True).click()
        local.locator("#settings").get_by_role("button", name="Done").click()
        local.get_by_role("link", name="Back to Fixtures").click()
        local.wait_for_url("**/index.html")
        local.get_by_role("link", name="Forward to A long read").click()
        local.wait_for_url("**/long-read.html")
        local.locator("#Part-1 .fold").click()
        works = not local.locator("#Part-1 + p").is_visible()
        results.append(check("back, forward and folding work there too", works))
        local.evaluate(SELECT, ["c-cell-5", "prose to read", 0])
        local.wait_for_timeout(600)
        unmarked = local.locator(".mark-pop, .mark-pen, .mark-list").count() == 0
        results.append(check("a published page offers no marking", unmarked))
        results.append(check("nothing blocked by the page's own policy", not blocked, blocked))
        local.close()

    results.append(check("no script errors", not errors, errors))
    browser.close()
    return all(results)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--engine", action="append", choices=ENGINES)
    args = parser.parse_args()
    with sync_playwright() as playwright:
        passed = [run(engine, playwright) for engine in args.engine or ENGINES]
    return 0 if all(passed) else 1


if __name__ == "__main__":
    sys.exit(main())
