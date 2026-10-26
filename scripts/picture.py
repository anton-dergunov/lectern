"""Make the README picture, docs/pictures/lectern.png, from the sample notebook in examples/.

    uv run --group shots python scripts/picture.py

The sample is served from a copy, so the highlight and note made on it never reach the repo.
WebKit takes an iPad in Solarized Light, with a note open, and a phone in Solarized Dark, at the
table and the diagram; docs/pictures/frame.html puts the two in their devices. pngquant, when
installed, makes the file a third of the size.

Needs the browsers once: `uv run --group shots playwright install chromium webkit`.
"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from _local import REPO, LocalServer
from playwright.sync_api import Browser, sync_playwright

PICTURES = REPO / "docs" / "pictures"
DOCUMENT = "step-size.ipynb"
NOTE = "The steep axis sets the limit on η; this gentle one sets the pace."

# The words to highlight: the cell, and words on one line of its source.
MARK = ["c-rule", "whose curvature is gentlest along one axis", 0]

# As in check_reader.py: select the nth occurrence of some words inside a cell.
SELECT = """([cell, words, nth]) => {
  const walker = document.createTreeWalker(document.getElementById(cell), NodeFilter.SHOW_TEXT);
  for (let node; (node = walker.nextNode()); ) {
    let at = -1;
    for (let n = 0; n <= nth; n++) at = node.data.indexOf(words, at + 1);
    if (at < 0) continue;
    const range = document.createRange();
    range.setStart(node, at);
    range.setEnd(node, at + words.length);
    node.parentElement.scrollIntoView({block: 'center'});
    getSelection().removeAllRanges();
    getSelection().addRange(range);
    return true;
  }
  return false;
}"""

# A point on the first mark, to tap.
MARK_POINT = """() => {
  const mark = [...(CSS.highlights.get('lectern-note') || []), ...(CSS.highlights.get('lectern-mark') || [])][0];
  const box = mark.getClientRects()[0];
  return {x: box.left + box.width / 2, y: box.top + box.height / 2};
}"""


def device(browser: Browser, width: int, height: int, prefs: dict):
    context = browser.new_context(
        viewport={"width": width, "height": height}, device_scale_factor=2
    )
    context.add_init_script(
        f"localStorage.setItem('lectern:prefs', {json.dumps(json.dumps(prefs))})"
    )
    return context.new_page()


def scroll_to(page, selector: str) -> None:
    """Bring an element to the top of the screen, below the top bar."""
    page.locator(selector).first.evaluate("e => e.scrollIntoView()")
    page.wait_for_timeout(300)
    # Scrolling down hides the top bar; a little back up brings it back.
    page.mouse.move(200, 400)
    page.mouse.wheel(0, -90)
    page.wait_for_timeout(700)


def ipad(browser: Browser, url: str, out: Path) -> None:
    page = device(
        browser, 820, 1180, {"family": "solarized", "mode": "light", "size": 19, "width": "m"}
    )
    page.goto(url)
    page.wait_for_load_state("networkidle")
    page.get_by_role("button", name="Mark what is selected").click()
    page.evaluate(SELECT, MARK)
    page.wait_for_timeout(1300)
    point = page.evaluate(MARK_POINT)
    page.mouse.click(point["x"], point["y"])
    page.locator(".mark-pop").get_by_role("button", name="Add note").click()
    page.locator(".note-editor textarea").fill(NOTE)
    page.locator(".note-editor").get_by_role("button", name="Save").click()
    page.wait_for_timeout(500)

    # The model's code folded, so the formula, the code and the plot share one screen.
    page.locator("#c-valley details.src > summary").click()
    scroll_to(page, "#c-rule h2")
    point = page.evaluate(MARK_POINT)
    page.mouse.click(point["x"], point["y"])
    page.wait_for_timeout(500)
    page.screenshot(path=out)
    page.context.close()


def phone(browser: Browser, url: str, out: Path) -> None:
    page = device(browser, 390, 844, {"family": "solarized", "mode": "dark", "size": 17})
    page.goto(url)
    page.wait_for_load_state("networkidle")
    scroll_to(page, "#c-table .out")
    page.screenshot(path=out)
    page.context.close()


def main() -> None:
    with tempfile.TemporaryDirectory() as work:
        served, shots = Path(work, "examples"), Path(work, "shots")
        shutil.copytree(REPO / "examples", served)
        shots.mkdir()
        shutil.copy(PICTURES / "frame.html", shots)
        with LocalServer(served) as server, sync_playwright() as playwright:
            webkit = playwright.webkit.launch()
            ipad(webkit, server.url(DOCUMENT), shots / "ipad.png")
            phone(webkit, server.url(DOCUMENT), shots / "phone.png")
            webkit.close()

            chromium = playwright.chromium.launch()
            page = chromium.new_page(
                viewport={"width": 1040, "height": 1040}, device_scale_factor=2
            )
            page.goto((shots / "frame.html").as_uri())
            page.wait_for_load_state("load")
            out = PICTURES / "lectern.png"
            page.screenshot(path=out, omit_background=True)
            chromium.close()

    if shutil.which("pngquant"):
        subprocess.run(["pngquant", "--force", "--skip-if-larger", "--output", out, "256", out])
    else:
        print("pngquant is not installed; the picture is left uncompressed")
    print(out)


if __name__ == "__main__":
    main()
