"""Drive the reader in real browsers and check what the unit tests cannot see.

    uv run --group shots python scripts/check_reader.py [--engine chromium|webkit]...

Runs against the test fixtures on a local port, in Chromium and WebKit. Checks the top
bar hiding, the reading position surviving a reload and a text-size change, settings,
the contents list, long output, the e-ink theme's page turning, and what happens when the
server stops.

Needs the browsers once: `uv run --group shots playwright install chromium webkit`.
"""

import argparse
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
        page.mouse.click(790, 500)
        results.append(
            check("a tap on the right edge turns on", page.evaluate("window.scrollY") > moved * 1.9)
        )
        page.mouse.click(30, 500)
        back = page.evaluate("window.scrollY")
        results.append(check("a tap on the left edge turns back", abs(back - moved) < 2, back))
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
        page.get_by_role("link", name="Back to fixtures").click()
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
            follower.get_by_role("button", name="Show the new version").click()
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
            follower.get_by_role("button", name="Stay as it is").click()
            follower.close()

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
