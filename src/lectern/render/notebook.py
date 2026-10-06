"""A notebook to an HTML fragment, from its saved outputs. Nothing is executed."""

import threading
from pathlib import Path

import nbformat
from jinja2 import pass_context
from nbconvert import HTMLExporter
from traitlets.config import Config

from .document import Rendered, finish
from .filters import clean_table_html, error_html, placeholder, stream_lines
from .markdown import markdown_to_html

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"

# nbconvert's order without the widget and javascript types: the reader runs no scripts, so
# an output saved with one of those falls through to its HTML, image or text form.
DISPLAY_PRIORITY = [
    "text/html",
    "text/markdown",
    "image/svg+xml",
    "text/latex",
    "image/png",
    "image/jpeg",
    "text/plain",
]


# Outputs that are drawn by code running in the browser. Their saved HTML form, if any, is
# only a script, so it must not be what gets picked.
INTERACTIVE = {
    "application/vnd.plotly.v1+json": "Interactive plot.",
    "application/vnd.jupyter.widget-view+json": "Interactive widget.",
    "application/vnd.bokehjs_exec.v0+json": "Interactive plot.",
    "application/vnd.vegalite.v5+json": "Interactive chart.",
    "application/vnd.vegalite.v4+json": "Interactive chart.",
}
IMAGES = ("image/svg+xml", "image/png", "image/jpeg")


def _still_outputs(nb) -> None:
    """Give every output a form that can be shown without running anything.

    An interactive output keeps only its saved picture when it has one. Without a picture,
    or when nothing in an output is of a kind the reader shows, a note takes its place:
    better than an empty gap, or a widget's `repr` standing in for the widget.
    """
    for cell in nb.cells:
        for output in cell.get("outputs", []):
            data = output.get("data")
            if not data:
                continue
            kind = next((INTERACTIVE[mime] for mime in data if mime in INTERACTIVE), None)
            pictures = {mime: data[mime] for mime in IMAGES if mime in data}
            if kind and pictures:
                output["data"] = pictures
            elif kind:
                output["data"] = {"text/html": placeholder(kind)}
            elif not any(mime in data for mime in DISPLAY_PRIORITY):
                output["data"] = {"text/html": placeholder("Output.")}


class ReaderExporter(HTMLExporter):
    def __init__(self, **kw) -> None:
        super().__init__(
            template_name="reader",
            extra_template_basedirs=[str(TEMPLATES)],
            exclude_input_prompt=True,
            exclude_output_prompt=True,
            # Headings keep their ids and anchors; the stylesheet hides the pilcrow.
            exclude_anchor_links=False,
            embed_images=True,
            **kw,
        )
        self.register_filter("clean_table_html", clean_table_html)
        self.register_filter("stream_lines", stream_lines)
        self.register_filter("error_html", error_html)

    @property
    def default_config(self) -> Config:
        config = super().default_config
        config.NbConvertBase.display_data_priority = DISPLAY_PRIORITY
        return config

    @pass_context
    def markdown2html(self, context, source: str) -> str:
        cell = context.get("cell", {})
        return markdown_to_html(
            source,
            attachments=cell.get("attachments", {}),
            embed_images=self.embed_images,
            path=context.get("resources", {}).get("metadata", {}).get("path", ""),
            anchor_link_text=self.anchor_link_text,
            exclude_anchor_links=self.exclude_anchor_links,
            **self.lexer_options,
        )


_exporter: ReaderExporter | None = None
_lock = threading.Lock()


def render_notebook(path: Path) -> Rendered:
    global _exporter
    nb = nbformat.read(path, as_version=4)
    code_cells = 0
    for index, cell in enumerate(nb.cells):
        # Notebooks older than nbformat 4.5 have no cell ids; the template anchors on them.
        if not cell.get("id"):
            cell["id"] = f"n{index}"
        if cell.cell_type == "code":
            # What Jupyter shows beside the cell; for one that was never run, which code
            # cell it is, counting code cells only, as a run from the top would number it.
            code_cells += 1
            count = cell.get("execution_count")
            cell.metadata["lectern_label"] = f"[{count}]" if count else f"#{code_cells}"
    _still_outputs(nb)
    # One exporter for the process: building it is slow, and it is not thread-safe.
    with _lock:
        if _exporter is None:
            _exporter = ReaderExporter()
        resources = {"metadata": {"path": str(path.parent)}}
        fragment, _ = _exporter.from_notebook_node(nb, resources=resources)
    return finish(fragment, path)
