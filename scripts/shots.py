"""Screenshots of the reader at the iPad's portrait size, to look at without the iPad.

    uv run --group shots python scripts/shots.py [ROOT] [--out DIR] [--page REL]...
        [--theme THEME]... [--engine ENGINE]... [--size PX] [--viewport WxH]

ROOT defaults to the test fixtures. With no --page, the listing and the first few documents
are taken. Each page is captured twice per engine and theme: the first screen, and the
whole page. WebKit is the closer stand-in for Safari on the iPad.

Needs the browsers once: `uv run --group shots playwright install chromium webkit`.
"""

import argparse
import json
import re
from pathlib import Path

from _local import FIXTURES, LocalServer
from playwright.sync_api import sync_playwright

from lectern import library

THEMES = ["solarized-light", "solarized-dark", "plain-light", "plain-dark"]
ENGINES = ["chromium", "webkit"]
DEFAULT_PAGES = 4


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("root", nargs="?", type=Path, default=FIXTURES)
    parser.add_argument("--out", type=Path, default=Path("shots"))
    parser.add_argument("--page", action="append", help="path under ROOT; '' is the listing")
    parser.add_argument("--theme", action="append", choices=[*THEMES, "all"])
    parser.add_argument("--engine", action="append", choices=ENGINES)
    parser.add_argument("--size", type=int, default=19, help="text size in px")
    parser.add_argument("--viewport", default="820x1180")
    args = parser.parse_args()

    themes = THEMES if "all" in (args.theme or []) else args.theme or THEMES[:1]
    width, height = (int(n) for n in args.viewport.split("x"))
    pages = args.page
    if pages is None:
        found = [p.relative_to(args.root).as_posix() for p in library.discover(args.root)]
        pages = ["", *found[:DEFAULT_PAGES]]
    args.out.mkdir(parents=True, exist_ok=True)

    with LocalServer(args.root) as server, sync_playwright() as playwright:
        for engine in args.engine or ENGINES:
            browser = getattr(playwright, engine).launch()
            for theme in themes:
                family, mode = theme.split("-")
                prefs = {"family": family, "mode": mode, "size": args.size}
                context = browser.new_context(viewport={"width": width, "height": height})
                context.add_init_script(
                    f"localStorage.setItem('lectern:prefs', {json.dumps(json.dumps(prefs))})"
                )
                page = context.new_page()
                for rel in pages:
                    page.goto(server.url(rel))
                    page.wait_for_load_state("networkidle")
                    slug = re.sub(r"[^A-Za-z0-9]+", "-", rel).strip("-") or "listing"
                    stem = args.out / f"{engine}-{theme}-{slug}"
                    page.screenshot(path=f"{stem}-top.png")
                    page.screenshot(path=f"{stem}-full.png", full_page=True)
                    print(f"{stem}-top.png")
                context.close()
            browser.close()


if __name__ == "__main__":
    main()
