import io
import json
import logging
from typing import Optional

from pypdf import PdfReader
from docx import Document
from google import genai
from google.genai import types

from backend_pure_rag.config import get_api_key, is_gemini_key

logger = logging.getLogger("pure_rag.document_parser")


def extract_excel_text(file_bytes: bytes) -> str:
    """Parses Excel .xlsx / .xls files and formats sheets into clean Markdown tables."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        markdown_sections = []

        for sheet_name in wb.sheetnames:
            sheet = wb[sheet_name]
            rows = list(sheet.iter_rows(values_only=True))
            if not rows:
                continue

            non_empty_rows = [[str(cell).strip() if cell is not None else "" for cell in row] for row in rows]
            non_empty_rows = [r for r in non_empty_rows if any(cell for cell in r)]

            if not non_empty_rows:
                continue

            markdown_sections.append(f"### Sheet: {sheet_name}\n")
            header = non_empty_rows[0]
            header_str = " | ".join(header)
            separator_str = " | ".join(["---"] * len(header))
            markdown_sections.append(f"| {header_str} |")
            markdown_sections.append(f"| {separator_str} |")

            for row in non_empty_rows[1:]:
                row_str = " | ".join(row)
                markdown_sections.append(f"| {row_str} |")
            markdown_sections.append("\n")

        return "\n".join(markdown_sections).strip()
    except Exception as e:
        logger.warning(f"openpyxl note, attempting pandas fallback: {e}")
        try:
            import pandas as pd
            excel_file = pd.ExcelFile(io.BytesIO(file_bytes))
            sections = []
            for sheet in excel_file.sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet)
                if not df.empty:
                    sections.append(f"### Sheet: {sheet}\n" + df.to_markdown(index=False))
            return "\n\n".join(sections).strip()
        except Exception as err:
            raise ValueError(f"Failed to parse Excel file: {err}")


def extract_pptx_text(file_bytes: bytes) -> str:
    """Extracts text content and tables from PowerPoint .pptx presentations."""
    try:
        from pptx import Presentation
        prs = Presentation(io.BytesIO(file_bytes))
        slides_text = []

        for slide_idx, slide in enumerate(prs.slides, start=1):
            slide_parts = [f"### Slide {slide_idx}"]
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        text = para.text.strip()
                        if text:
                            slide_parts.append(text)
                elif shape.has_table:
                    table = shape.table
                    rows_data = []
                    for row in table.rows:
                        row_vals = [cell.text.strip() for cell in row.cells]
                        if any(row_vals):
                            rows_data.append(row_vals)
                    if rows_data:
                        header = rows_data[0]
                        slide_parts.append(" | ".join(header))
                        slide_parts.append(" | ".join(["---"] * len(header)))
                        for r in rows_data[1:]:
                            slide_parts.append(" | ".join(r))

            if len(slide_parts) > 1:
                slides_text.append("\n".join(slide_parts))

        return "\n\n".join(slides_text).strip()
    except Exception as e:
        raise ValueError(f"Failed to parse PowerPoint presentation: {e}")


def extract_pdf_native_text(file_bytes: bytes) -> str:
    """Attempts native text extraction from digital PDF documents."""
    text_content = []
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        for page_idx, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text and len(page_text.strip()) > 10:
                text_content.append(f"--- Page {page_idx + 1} ---\n{page_text.strip()}")

        if text_content:
            return "\n\n".join(text_content).strip()
    except Exception as e:
        logger.debug(f"pypdf extraction note: {e}")

    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            plumber_content = []
            for page_idx, page in enumerate(pdf.pages):
                txt = page.extract_text()
                if txt and len(txt.strip()) > 10:
                    plumber_content.append(f"--- Page {page_idx + 1} ---\n{txt.strip()}")
            if plumber_content:
                return "\n\n".join(plumber_content).strip()
    except Exception as e:
        logger.debug(f"pdfplumber extraction note: {e}")

    return ""


def extract_pdf_with_multimodal_vision(file_bytes: bytes, custom_api_key: Optional[str] = None) -> str:
    """Extracts text from scanned or image-based PDFs using Gemini Multimodal Vision."""
    api_key = get_api_key(custom_api_key)
    if not is_gemini_key(api_key):
        raise ValueError("Multimodal OCR for scanned PDFs requires a Google Gemini API Key.")

    client = genai.Client(api_key=api_key)
    pdf_part = types.Part.from_bytes(
        data=file_bytes,
        mime_type="application/pdf",
    )

    prompt = (
        "Extract ALL text and information from this document exactly as written. "
        "Preserve table structures using Markdown tables (| Header | ... |). "
        "Extract both Sinhala and English text with 100% precision. "
        "Do not summarize or skip any sections."
    )

    models_to_try = [
        "gemini-3.5-flash-lite",
        "gemini-flash-lite-latest",
        "gemini-3.5-flash",
    ]

    last_error = None
    for model_name in models_to_try:
        try:
            res = client.models.generate_content(
                model=model_name,
                contents=[pdf_part, prompt],
            )
            if res and res.text and res.text.strip():
                return res.text.strip()
        except Exception as e:
            last_error = e
            logger.debug(f"OCR model {model_name} failed: {e}")
            continue

    raise RuntimeError(f"Multimodal PDF extraction failed: {last_error}")


def parse_pdf(file_bytes: bytes, custom_api_key: Optional[str] = None) -> str:
    native_text = extract_pdf_native_text(file_bytes)
    if native_text and len(native_text.strip()) > 40:
        return native_text
    logger.info("PDF contains insufficient embedded text. Falling back to Gemini Multimodal OCR.")
    return extract_pdf_with_multimodal_vision(file_bytes, custom_api_key)


def parse_docx(file_bytes: bytes) -> str:
    doc = Document(io.BytesIO(file_bytes))
    paragraphs = []
    for para in doc.paragraphs:
        t = para.text.strip()
        if t:
            paragraphs.append(t)

    for table in doc.tables:
        rows_data = []
        for row in table.rows:
            row_vals = [cell.text.strip() for cell in row.cells]
            if any(row_vals):
                rows_data.append(row_vals)
        if rows_data:
            header = rows_data[0]
            paragraphs.append(" | ".join(header))
            paragraphs.append(" | ".join(["---"] * len(header)))
            for r in rows_data[1:]:
                paragraphs.append(" | ".join(r))

    return "\n\n".join(paragraphs).strip()


def extract_csv_text(file_bytes: bytes) -> str:
    """
    Parses CSV files into rich, human-readable records and structured Markdown tables.
    Transforms rows into:
    1. Table Summary (Columns, Row count, sample values)
    2. Structured Markdown table chunks (with repeated headers)
    3. Natural language Key-Value entity record summaries for high-accuracy semantic and lexical search.
    """
    import csv
    text = ""
    for enc in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
        try:
            text = file_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if not text:
        raise ValueError("Could not decode CSV text file.")

    reader = list(csv.reader(io.StringIO(text)))
    if not reader:
        return ""

    header = [c.strip() for c in reader[0]]
    rows = [[c.strip() for c in r] for r in reader[1:] if any(c.strip() for c in r)]

    if not rows:
        return f"CSV Table with columns: {', '.join(header)}"

    output_sections = [
        f"### Dataset Summary: {len(rows)} Total Rows, {len(header)} Columns: {', '.join(header)}\n"
    ]

    # Group into structured table chunks of 15 rows each with preserved headers
    block_size = 15
    for b_idx in range(0, len(rows), block_size):
        chunk_rows = rows[b_idx:b_idx + block_size]
        start_row = b_idx + 1
        end_row = b_idx + len(chunk_rows)

        block_lines = [
            f"### Table Block {b_idx // block_size + 1} (Rows {start_row} to {end_row} of {len(rows)}):",
            "| " + " | ".join(header) + " |",
            "| " + " | ".join(["---"] * len(header)) + " |",
        ]
        for r in chunk_rows:
            block_lines.append("| " + " | ".join(r[c] if c < len(r) else "" for c in range(len(header))) + " |")

        # Include clear key-value record summaries for each entity in this block for BM25 and vector search
        block_lines.append("\nRecords in this block:")
        for idx, r in enumerate(chunk_rows, start=start_row):
            parts = [f"{header[c]}: {r[c]}" for c in range(min(len(header), len(r))) if r[c]]
            block_lines.append(f"- Record {idx}: {', '.join(parts)}")

        output_sections.append("\n".join(block_lines))

    return "\n\n".join(output_sections)


def parse_document(file_bytes: bytes, filename: str, custom_api_key: Optional[str] = None) -> str:
    """Parses uploaded files into clean Markdown/text representation for Pure RAG ingestion."""
    fn_lower = filename.lower()
    if fn_lower.endswith(".pdf"):
        return parse_pdf(file_bytes, custom_api_key)
    elif fn_lower.endswith(".docx"):
        return parse_docx(file_bytes)
    elif fn_lower.endswith((".xlsx", ".xls")):
        return extract_excel_text(file_bytes)
    elif fn_lower.endswith(".csv"):
        return extract_csv_text(file_bytes)
    elif fn_lower.endswith(".pptx"):
        return extract_pptx_text(file_bytes)
    elif fn_lower.endswith((".txt", ".md")):
        try:
            return file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return file_bytes.decode("latin-1")
            except Exception as e:
                raise ValueError(f"Could not decode text file: {e}")
    else:
        raise ValueError(f"Unsupported document format: {filename}. Supported: PDF, DOCX, XLSX, PPTX, TXT, MD, CSV.")
