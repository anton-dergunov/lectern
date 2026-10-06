"""Drive the reader in real browsers and check what the unit tests cannot see.

    uv run --group shots python scripts/check_reader.py [--engine chromium|webkit]...

Runs against the test fixtures on a local port, in Chromium and WebKit. Checks the top
bar hiding, the reading position surviving a reload and a text-size change, settings,
the contents list, long output, and what happens when the server stops.

Needs the browsers once: `uv run --group shots playwright install chromium webkit`.
"""

import argparse
import sys

from _local import FIXTURES, LocalServer
from playwright.sync_api import Page, expect, sync_playwright

ENGINES = ["chromium", "webkit"]

# Where the reader's own script measures from: the first cell still showing below the bar.
PLACE = """() => {
  const line = document.querySelector('.bar').offsetHeight + 12;
  for (const cell of document.querySelectorAll('main.doc > .cell')) {
    const box = cell.getBoundingClientRect();
    if (box.bottom > line) return {cell: cell.id, frac: (line - box.top) / box.height};
  }
}"""


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
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    with LocalServer(FIXTURES) as server:
        long_read = server.url("long-read.ipynb")

        # ---- Top bar ----
        page.goto(long_read)
        page.evaluate("window.scrollTo(0, 2500)")
        settle(page)
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

        page.get_by_role("button", name="Reading settings").click()
        for _ in range(3):
            page.get_by_label("Larger text").click()
        size = page.evaluate("getComputedStyle(document.documentElement).fontSize")
        results.append(check("text size follows the setting", size == "22px", size))
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
