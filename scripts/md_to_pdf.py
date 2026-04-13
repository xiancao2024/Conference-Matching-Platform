#!/usr/bin/env python3
"""
Simple Markdown-to-PDF converter that writes lines as wrapped paragraphs.
Requires reportlab: `pip install reportlab`.
Usage: python3 scripts/md_to_pdf.py input.md output.pdf
"""
import sys
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas


def render_markdown_to_pdf(md_path: Path, out_path: Path) -> None:
    text = md_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    c = canvas.Canvas(str(out_path), pagesize=letter)
    width, height = letter
    left = inch * 0.75
    right = width - inch * 0.75
    y = height - inch * 0.75
    line_height = 12
    max_width = right - left
    c.setFont("Helvetica", 10)

    for raw in lines:
        if not raw.strip():
            y -= line_height
            if y < inch:
                c.showPage()
                c.setFont("Helvetica", 10)
                y = height - inch * 0.75
            continue
        # collapse headers: make them bold larger
        if raw.startswith("#"):
            text = raw.lstrip('# ').strip()
            c.setFont("Helvetica-Bold", 14)
            c.drawString(left, y, text)
            c.setFont("Helvetica", 10)
            y -= line_height * 1.6
        else:
            # naive wrap
            words = raw.split()
            cur = ""
            for w in words:
                test = (cur + " " + w).strip()
                if c.stringWidth(test, "Helvetica", 10) < max_width:
                    cur = test
                else:
                    c.drawString(left, y, cur)
                    y -= line_height
                    if y < inch:
                        c.showPage()
                        c.setFont("Helvetica", 10)
                        y = height - inch * 0.75
                    cur = w
            if cur:
                c.drawString(left, y, cur)
                y -= line_height
                if y < inch:
                    c.showPage()
                    c.setFont("Helvetica", 10)
                    y = height - inch * 0.75
    c.save()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: md_to_pdf.py input.md output.pdf")
        sys.exit(2)
    md = Path(sys.argv[1])
    out = Path(sys.argv[2])
    render_markdown_to_pdf(md, out)
