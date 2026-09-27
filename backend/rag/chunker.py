"""
rag/chunker.py — Recursive Structural Text Chunker
====================================================
Splits raw document text into semantically-coherent, size-bounded chunks
using a multi-level hierarchy:
  1. Markdown headings / Slide / Page / Sheet structural boundaries
  2. Paragraph splitting with token-aware overlap
  3. Sentence-level fallback for oversized paragraphs
"""

import re
import logging
from typing import List

logger = logging.getLogger("voicerag.rag.chunker")


def recursive_structural_chunk(
    text: str,
    target_size: int = 500,
    overlap: int = 90,
) -> List[str]:
    """
    Splits *text* into overlapping, semantically-bounded chunks.

    Splitting hierarchy:
      1. Structural boundaries: ``## Heading``, ``--- Page N ---``,
         ``### Slide N``, ``### Sheet:``
      2. Double-newline paragraph boundaries.
      3. Sentence boundaries (``[.!?;]\\s+``) for oversized paragraphs.

    Args:
        text:        Raw document text (any encoding normalised to LF).
        target_size: Soft maximum characters per chunk (default 500).
        overlap:     Allowed character budget above *target_size* before a
                     new chunk is started (default 90).

    Returns:
        List of non-empty text chunks, each > 8 characters.
        Falls back to ``[text[:target_size]]`` when no chunks can be formed.
    """
    cleaned = text.replace("\r\n", "\n").strip()
    if not cleaned:
        return []

    # --- Level 1: structural boundary split ---
    sections = re.split(
        r"(?=\n#{1,3}\s+|\n--- Page \d+ ---\n|\n### Slide \d+|\n### Sheet:)",
        cleaned,
    )
    chunks: List[str] = []

    for section in sections:
        sec_text = section.strip()
        if not sec_text:
            continue

        if len(sec_text) <= target_size + overlap:
            if len(sec_text) > 8:
                chunks.append(sec_text)
        else:
            # --- Level 2: paragraph split ---
            paragraphs = sec_text.split("\n\n")
            current_chunk = ""

            for para in paragraphs:
                para_clean = para.strip()
                if not para_clean:
                    continue

                if len(current_chunk) + len(para_clean) + 2 <= target_size:
                    current_chunk += ("\n\n" if current_chunk else "") + para_clean
                else:
                    if current_chunk and len(current_chunk) > 8:
                        chunks.append(current_chunk.strip())

                    if len(para_clean) > target_size:
                        # --- Level 3: sentence split ---
                        sentences = re.split(r"(?<=[.!?;])\s+", para_clean)
                        sub_chunk = ""
                        for sent in sentences:
                            if len(sub_chunk) + len(sent) + 1 <= target_size:
                                sub_chunk += (" " if sub_chunk else "") + sent
                            else:
                                if sub_chunk and len(sub_chunk) > 8:
                                    chunks.append(sub_chunk.strip())
                                sub_chunk = sent
                        if sub_chunk and len(sub_chunk) > 8:
                            chunks.append(sub_chunk.strip())
                        current_chunk = ""
                    else:
                        current_chunk = para_clean

            if current_chunk and len(current_chunk) > 8:
                chunks.append(current_chunk.strip())

    return chunks if chunks else [cleaned[:target_size]]
