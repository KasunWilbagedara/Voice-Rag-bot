"""
rag_v2/ingestion/web_scraper.py
--------------------------------
Fetches and cleans HTML content from a URL, returning plain text suitable for
chunking and embedding.
"""

import re
import logging

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("rag_v2.ingestion.web_scraper")

# Tags whose entire subtree should be removed before text extraction
_NOISE_TAGS = ["script", "style", "nav", "footer", "header", "aside"]

_MIN_CONTENT_LENGTH = 50


def scrape_url(url: str, timeout: int = 15) -> str:
    """Fetch *url*, strip boilerplate HTML, and return clean text.

    Parameters
    ----------
    url:
        The fully-qualified URL to scrape.
    timeout:
        Request timeout in seconds (default 15).

    Returns
    -------
    str
        Formatted string: ``# {title}\\nSource: {url}\\n\\n{clean_text}``

    Raises
    ------
    ValueError
        If the HTTP status code is not 200, or if the extracted content is
        shorter than ``_MIN_CONTENT_LENGTH`` characters.
    requests.RequestException
        Propagated from ``requests.get`` for network-level errors.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }

    logger.info("Scraping URL: %s", url)
    response = requests.get(url, headers=headers, timeout=timeout)

    if response.status_code != 200:
        raise ValueError(
            f"Failed to fetch URL '{url}'. "
            f"HTTP status code: {response.status_code}"
        )

    soup = BeautifulSoup(response.content, "lxml")

    # ── Remove noise elements ───────────────────────────────────────────────
    for tag_name in _NOISE_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # ── Extract page title ──────────────────────────────────────────────────
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else url

    # ── Extract main content ────────────────────────────────────────────────
    content_element = (
        soup.find("main")
        or soup.find("article")
        or soup.find("body")
    )

    if content_element is None:
        raw_text = soup.get_text(separator="\n")
    else:
        raw_text = content_element.get_text(separator="\n")

    # ── Normalise whitespace ────────────────────────────────────────────────
    # Collapse runs of spaces/tabs on a single line to one space
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in raw_text.splitlines()]
    # Remove fully blank lines then collapse multiple blank lines to at most 2
    normalised_lines: list[str] = []
    consecutive_blank = 0
    for line in lines:
        if line == "":
            consecutive_blank += 1
            if consecutive_blank <= 2:
                normalised_lines.append("")
        else:
            consecutive_blank = 0
            normalised_lines.append(line)

    clean_text = "\n".join(normalised_lines).strip()

    if len(clean_text) < _MIN_CONTENT_LENGTH:
        raise ValueError(
            f"Extracted content from '{url}' is too short "
            f"({len(clean_text)} chars). Minimum is {_MIN_CONTENT_LENGTH}."
        )

    logger.info(
        "Scraped '%s' — title: %r, content length: %d chars",
        url,
        title,
        len(clean_text),
    )

    return f"# {title}\nSource: {url}\n\n{clean_text}"
