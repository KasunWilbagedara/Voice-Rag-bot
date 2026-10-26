"""
rag_v2/ingestion/parser.py
---------------------------
Multi-format document parser.  Converts raw file bytes (or a URL) into a
single plain-text string ready for chunking.

Supported formats
-----------------
.pdf   – pypdf
.docx  – python-docx
.xlsx / .xls – openpyxl (fallback: pandas)
.pptx  – python-pptx
.txt / .md – UTF-8 decode
.csv   – pandas (Markdown table)
URL    – rag_v2.ingestion.web_scraper.scrape_url
"""

import io
import logging

from rag_v2.ingestion.web_scraper import scrape_url

logger = logging.getLogger("rag_v2.ingestion.parser")

# Extensions this module supports
_SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xls", ".pptx", ".txt", ".md", ".csv"}


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF using pypdf."""
    from pypdf import PdfReader  # lazy import – optional dependency

    reader = PdfReader(io.BytesIO(file_bytes))
    pages: list[str] = []
    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append(f"--- Page {page_num} ---\n{text.strip()}")
    return "\n\n".join(pages)


def _parse_docx(file_bytes: bytes) -> str:
    """Extract paragraphs and tables from a .docx file."""
    import docx  # python-docx

    doc = docx.Document(io.BytesIO(file_bytes))
    parts: list[str] = []

    for element in doc.element.body:
        tag = element.tag.split("}")[-1]  # strip namespace
        if tag == "p":
            # Paragraph
            para = docx.text.paragraph.Paragraph(element, doc)
            text = para.text.strip()
            if text:
                parts.append(text)
        elif tag == "tbl":
            # Table
            table = docx.table.Table(element, doc)
            rows: list[str] = []
            for row in table.rows:
                cell_texts = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                rows.append("| " + " | ".join(cell_texts) + " |")
            if rows:
                # Insert Markdown header separator after first row
                header_sep = "| " + " | ".join(["---"] * len(table.rows[0].cells)) + " |"
                rows.insert(1, header_sep)
                parts.append("\n".join(rows))

    return "\n\n".join(parts)


def _parse_xlsx(file_bytes: bytes) -> str:
    """Format each sheet of an Excel workbook as a Markdown table.

    Tries openpyxl first; falls back to pandas if openpyxl is unavailable.
    """
    try:
        import openpyxl

        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        sheets_text: list[str] = []

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                continue

            sheet_parts = [f"### Sheet: {sheet_name}"]
            # First row → header
            header = ["" if v is None else str(v) for v in rows[0]]
            sheet_parts.append("| " + " | ".join(header) + " |")
            sheet_parts.append("| " + " | ".join(["---"] * len(header)) + " |")
            for row in rows[1:]:
                cells = ["" if v is None else str(v) for v in row]
                sheet_parts.append("| " + " | ".join(cells) + " |")

            sheets_text.append("\n".join(sheet_parts))

        return "\n\n".join(sheets_text)

    except ImportError:
        logger.warning("openpyxl not available – falling back to pandas for Excel parsing.")
        import pandas as pd

        xls = pd.ExcelFile(io.BytesIO(file_bytes))
        sheets_text = []
        for sheet_name in xls.sheet_names:
            df = xls.parse(sheet_name)
            sheets_text.append(f"### Sheet: {sheet_name}\n{df.to_markdown(index=False)}")
        return "\n\n".join(sheets_text)


def _parse_pptx(file_bytes: bytes) -> str:
    """Extract slide content from a .pptx file."""
    from pptx import Presentation  # python-pptx
    from pptx.util import Pt  # noqa: F401 – available but unused; import ensures pptx present

    prs = Presentation(io.BytesIO(file_bytes))
    slides_text: list[str] = []

    for slide_num, slide in enumerate(prs.slides, start=1):
        slide_parts: list[str] = []

        # Title
        title_text = ""
        if slide.shapes.title and slide.shapes.title.has_text_frame:
            title_text = slide.shapes.title.text.strip()

        slide_parts.append(f"### Slide {slide_num}: {title_text}")

        for shape in slide.shapes:
            # Skip the title shape to avoid duplication
            if shape == slide.shapes.title:
                continue

            # Text frames
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    line = para.text.strip()
                    if line:
                        slide_parts.append(line)

            # Tables
            if shape.has_table:
                table = shape.table
                rows: list[str] = []
                for row_idx, row in enumerate(table.rows):
                    cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                    rows.append("| " + " | ".join(cells) + " |")
                    if row_idx == 0:
                        rows.append("| " + " | ".join(["---"] * len(cells)) + " |")
                slide_parts.append("\n".join(rows))

        # Notes
        if slide.has_notes_slide:
            notes_frame = slide.notes_slide.notes_text_frame
            if notes_frame:
                notes_text = notes_frame.text.strip()
                if notes_text:
                    slide_parts.append(f"**Notes:** {notes_text}")

        slides_text.append("\n".join(slide_parts))

    return "\n\n".join(slides_text)


def _parse_csv(file_bytes: bytes) -> str:
    """Format a CSV file as a Markdown table using pandas."""
    import pandas as pd

    df = pd.read_csv(io.BytesIO(file_bytes))
    return df.to_markdown(index=False)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def parse_file(file_bytes: bytes, filename: str) -> str:
    """Parse *file_bytes* according to the extension in *filename*.

    Parameters
    ----------
    file_bytes:
        Raw bytes of the file to parse.
    filename:
        Original file name, used to determine the format via its extension.

    Returns
    -------
    str
        Extracted plain text (may include Markdown formatting for structured
        formats such as tables).

    Raises
    ------
    ValueError
        If the file extension is not in the supported set.
    """
    import os

    ext = os.path.splitext(filename)[1].lower()
    logger.info("Parsing file '%s' (extension: %s, size: %d bytes)", filename, ext, len(file_bytes))

    if ext == ".pdf":
        text = _parse_pdf(file_bytes)
    elif ext == ".docx":
        text = _parse_docx(file_bytes)
    elif ext in (".xlsx", ".xls"):
        text = _parse_xlsx(file_bytes)
    elif ext == ".pptx":
        text = _parse_pptx(file_bytes)
    elif ext in (".txt", ".md"):
        text = file_bytes.decode("utf-8", errors="replace")
    elif ext == ".csv":
        text = _parse_csv(file_bytes)
    else:
        raise ValueError(
            f"Unsupported file extension '{ext}'. "
            f"Supported extensions: {sorted(_SUPPORTED_EXTENSIONS)}"
        )

    logger.info("Parsed '%s' → %d characters.", filename, len(text))
    return text


def parse_url(url: str) -> str:
    """Fetch and parse the content at *url*.

    Parameters
    ----------
    url:
        Fully-qualified URL to scrape.

    Returns
    -------
    str
        Cleaned text representation of the page.
    """
    logger.info("Parsing URL: %s", url)
    return scrape_url(url)
