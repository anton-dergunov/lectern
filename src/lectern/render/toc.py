"""The document's headings, for the title now and the contents list later."""

from dataclasses import dataclass

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class Heading:
    level: int
    id: str
    text: str


def extract_toc(soup: BeautifulSoup) -> tuple[list[Heading], str | None]:
    """Headings h1 to h3 outside cell outputs, and the text of the first h1.

    Two headings with the same text get the same id from the markdown renderer; later
    ones are renamed in place so every entry links to its own heading.
    """
    toc: list[Heading] = []
    title: str | None = None
    seen: dict[str, int] = {}
    for tag in soup.find_all(["h1", "h2", "h3"]):
        if tag.find_parent(class_="out"):
            continue
        anchor = tag.find("a", class_="anchor-link")
        text = tag.get_text()
        if anchor:
            text = text.removesuffix(anchor.get_text())
        text = " ".join(text.split())
        level = int(tag.name[1])
        if level == 1 and title is None and text:
            title = text
        heading_id = tag.get("id")
        if not heading_id:
            continue
        seen[heading_id] = seen.get(heading_id, 0) + 1
        if seen[heading_id] > 1:
            heading_id = f"{heading_id}-{seen[heading_id]}"
            tag["id"] = heading_id
            if anchor:
                anchor["href"] = f"#{heading_id}"
        toc.append(Heading(level, heading_id, text))
    return toc, title
