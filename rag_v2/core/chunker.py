"""
rag_v2/core/chunker.py
----------------------
Recursive structural text chunker.

Splitting priority:
  1. Markdown headers  (# / ## / ###)
  2. Page markers      (--- Page N ---)
  3. Slide markers     (### Slide N)
  4. Sheet markers     (### Sheet:)
  5. Paragraph breaks  (double newline)
  6. Sentence breaks   (punctuation boundaries)
  7. Hard character split (last resort)
"""

import re
import logging
from typing import List

logger = logging.getLogger("rag_v2.core.chunker")

# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------
_RE_MARKDOWN_HEADER = re.compile(r"(?m)^(#{1,3})\s+.+$")
_RE_PAGE_MARKER = re.compile(r"---\s*Page\s+\d+\s*---", re.IGNORECASE)
_RE_SLIDE_MARKER = re.compile(r"#{1,3}\s*Slide\s+\d+", re.IGNORECASE)
_RE_SHEET_MARKER = re.compile(r"#{1,3}\s*Sheet\s*:", re.IGNORECASE)
_RE_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _split_by_pattern(text: str, pattern: re.Pattern) -> List[str]:
    """Split *text* on every match of *pattern*, keeping the delimiter."""
    parts: List[str] = []
    prev = 0
    for m in pattern.finditer(text):
        pre = text[prev : m.start()].strip()
        if pre:
            parts.append(pre)
        prev = m.start()
    tail = text[prev:].strip()
    if tail:
        parts.append(tail)
    return parts if len(parts) > 1 else []


def _split_on_structural_markers(text: str) -> List[str]:
    """
    Try splitting on structural markers in priority order.
    Returns a non-empty list of segments if a splitter fires, else [].
    """
    for pattern in (
        _RE_MARKDOWN_HEADER,
        _RE_PAGE_MARKER,
        _RE_SLIDE_MARKER,
        _RE_SHEET_MARKER,
    ):
        segments = _split_by_pattern(text, pattern)
        if segments:
            logger.debug("Split by pattern %s → %d segments", pattern.pattern, len(segments))
            return segments
    return []


def _split_by_paragraphs(text: str) -> List[str]:
    parts = [p.strip() for p in re.split(r"\n\s*\n", text)]
    return [p for p in parts if p]


def _split_by_sentences(text: str) -> List[str]:
    parts = [s.strip() for s in _RE_SENTENCE_BOUNDARY.split(text)]
    return [p for p in parts if p]


def _hard_split(text: str, size: int) -> List[str]:
    """Last-resort: chop at fixed character boundaries."""
    return [text[i : i + size] for i in range(0, len(text), size)]


# ---------------------------------------------------------------------------
# Recursive merger: joins short segments and re-splits long ones
# ---------------------------------------------------------------------------

def _merge_and_split(
    segments: List[str],
    target_size: int,
    overlap: int,
    depth: int = 0,
) -> List[str]:
    """
    Merge segments that are too small, split segments that are too large,
    and apply overlap between adjacent chunks.
    """
    if depth > 6:
        # Safety valve against infinite recursion
        return [s for s in segments if len(s) > 10]

    chunks: List[str] = []
    buffer = ""

    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue

        if len(seg) > target_size:
            # Flush buffer first
            if buffer:
                chunks.append(buffer)
                buffer = ""
            # Recursively break the large segment
            sub = _recursive_split(seg, target_size, overlap, depth + 1)
            chunks.extend(sub)
        elif len(buffer) + len(seg) + 1 <= target_size:
            buffer = (buffer + "\n" + seg).strip() if buffer else seg
        else:
            if buffer:
                chunks.append(buffer)
            buffer = seg

    if buffer:
        chunks.append(buffer)

    # Apply overlap: prepend tail of previous chunk to current
    if overlap > 0 and len(chunks) > 1:
        overlapped: List[str] = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_tail = chunks[i - 1][-overlap:].strip()
            merged = (prev_tail + " " + chunks[i]).strip()
            overlapped.append(merged)
        chunks = overlapped

    return [c for c in chunks if len(c) > 10]


def _recursive_split(
    text: str,
    target_size: int,
    overlap: int,
    depth: int = 0,
) -> List[str]:
    """Core recursive splitting logic for a single text block."""
    text = text.strip()
    if not text:
        return []

    if len(text) <= target_size:
        return [text] if len(text) > 10 else []

    # 1. Try structural markers
    segments = _split_on_structural_markers(text)

    # 2. Paragraph split
    if not segments:
        segments = _split_by_paragraphs(text)

    # 3. Sentence split
    if not segments or (len(segments) == 1 and len(segments[0]) > target_size):
        segments = _split_by_sentences(text)

    # 4. Hard split
    if not segments or (len(segments) == 1 and len(segments[0]) > target_size):
        segments = _hard_split(text, target_size)

    return _merge_and_split(segments, target_size, overlap, depth)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def recursive_chunk(
    text: str,
    target_size: int = 600,
    overlap: int = 100,
) -> List[str]:
    """
    Recursively chunk *text* into segments of approximately *target_size*
    characters with *overlap* characters of context carry-over between chunks.

    Splitting priority:
      Markdown headers → page/slide/sheet markers → paragraphs → sentences → hard split

    Parameters
    ----------
    text : str
        The raw text to chunk.
    target_size : int
        Target character length per chunk (default 600).
    overlap : int
        Number of trailing characters from the previous chunk to prepend to
        the next chunk for context continuity (default 100).

    Returns
    -------
    List[str]
        A list of non-empty string chunks, each > 10 characters.
    """
    if not text or not text.strip():
        logger.warning("recursive_chunk received empty text")
        return []

    logger.debug(
        "Chunking text of %d chars (target=%d, overlap=%d)",
        len(text),
        target_size,
        overlap,
    )

    chunks = _recursive_split(text, target_size, overlap, depth=0)
    logger.info("Produced %d chunks from %d-char text", len(chunks), len(text))
    return chunks
