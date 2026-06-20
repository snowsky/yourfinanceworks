"""Render an InvoiceViewModel + config to HTML (Jinja2) and PDF (WeasyPrint)."""
import asyncio
import os
from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
_env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR),
                   autoescape=select_autoescape(["html", "xml"]))


def _css() -> str:
    with open(os.path.join(_TEMPLATE_DIR, "invoice", "default.css"), encoding="utf-8") as f:
        return f.read()


def render_invoice_html(vm, config) -> str:
    return _env.get_template("invoice/default.html").render(vm=vm, cfg=config, css=_css())


def render_invoice_pdf(vm, config) -> bytes:
    from weasyprint import HTML
    html = render_invoice_html(vm, config)
    return HTML(string=html).write_pdf()


async def render_invoice_pdf_async(vm, config) -> bytes:
    # WeasyPrint is sync CPU work — offload so it never blocks the event loop.
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, render_invoice_pdf, vm, config)
