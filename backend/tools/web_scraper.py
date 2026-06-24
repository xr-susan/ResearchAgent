"""
Web scraper tool for ResearchAgent.

Extracts content from web pages with support for different content types.
Handles encoding, timeouts, and content cleaning.
"""

import re
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from backend.utils.logger import get_logger

logger = get_logger("web_scraper")


class ScrapeInput(BaseModel):
    """Input schema for web scraper tool."""
    url: str = Field(description="The URL to scrape content from")
    extract_mode: str = Field(
        default="text",
        description="Extraction mode: 'text' for plain text, 'links' for hyperlinks, 'table' for tables, 'all' for everything"
    )


class WebScraperTool(BaseTool):
    """Tool for extracting content from web pages.

    Supports extracting plain text, links, tables, or all content.
    Handles encoding detection and content cleaning.
    """

    name: str = "web_scraper"
    description: str = (
        "Scrape and extract content from a web page. Use this tool when you need to "
        "read the full content of a specific webpage. Input should be a valid URL. "
        "Use extract_mode='text' for articles, 'table' for data tables, 'links' for hyperlinks."
    )
    args_schema: type[BaseModel] = ScrapeInput

    # Common headers to avoid bot detection
    _headers: dict = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    def _run(self, url: str, extract_mode: str = "text") -> str:
        """Synchronous scrape."""
        import asyncio
        try:
            return asyncio.run(self._arun(url, extract_mode))
        except Exception as e:
            return f"Scraping failed: {str(e)}"

    async def _arun(self, url: str, extract_mode: str = "text") -> str:
        """Scrape content from a web page.

        Args:
            url: URL to scrape.
            extract_mode: What to extract (text/links/table/all).

        Returns:
            Extracted content as formatted string.
        """
        logger.info(f"Scraping: {url} (mode={extract_mode})")

        # Validate URL
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return f"Invalid URL: {url}. Please provide a complete URL with http:// or https://"

        try:
            response = requests.get(url, headers=self._headers, timeout=30, allow_redirects=True)
            response.raise_for_status()

            # Detect encoding
            if response.encoding and response.encoding.lower() != 'utf-8':
                response.encoding = response.apparent_encoding

            soup = BeautifulSoup(response.text, 'lxml')

            # Remove script and style elements
            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                tag.decompose()

            if extract_mode == "text":
                return self._extract_text(soup, url)
            elif extract_mode == "links":
                return self._extract_links(soup, url)
            elif extract_mode == "table":
                return self._extract_tables(soup)
            elif extract_mode == "all":
                return self._extract_all(soup, url)
            else:
                return self._extract_text(soup, url)

        except requests.exceptions.Timeout:
            return f"Timeout while scraping {url}. The page took too long to respond."
        except requests.exceptions.HTTPError as e:
            return f"HTTP error {e.response.status_code} while scraping {url}"
        except Exception as e:
            logger.error(f"Scraping error for {url}: {e}")
            return f"Failed to scrape {url}: {str(e)}"

    def _extract_text(self, soup: BeautifulSoup, url: str) -> str:
        """Extract clean text content from page.

        Args:
            soup: BeautifulSoup object.
            url: Source URL.

        Returns:
            Formatted text content.
        """
        # Get title
        title = soup.find('title')
        title_text = title.get_text(strip=True) if title else "No title"

        # Get main content
        # Try to find article/main content first
        main = soup.find('article') or soup.find('main') or soup.find('div', {'role': 'main'})
        if main:
            text = main.get_text(separator='\n', strip=True)
        else:
            body = soup.find('body')
            text = body.get_text(separator='\n', strip=True) if body else soup.get_text(separator='\n', strip=True)

        # Clean up whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)

        # Truncate if too long
        max_chars = 8000
        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n[Content truncated...]"

        return f"**Page Title:** {title_text}\n**Source:** {url}\n\n**Content:**\n{text}"

    def _extract_links(self, soup: BeautifulSoup, url: str) -> str:
        """Extract hyperlinks from page.

        Args:
            soup: BeautifulSoup object.
            url: Source URL for resolving relative URLs.

        Returns:
            Formatted list of links.
        """
        from urllib.parse import urljoin

        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(strip=True)
            if href and not href.startswith(('#', 'javascript:', 'mailto:')):
                full_url = urljoin(url, href)
                if text:
                    links.append(f"- [{text}]({full_url})")

        # Deduplicate while preserving order
        seen = set()
        unique_links = []
        for link in links:
            if link not in seen:
                seen.add(link)
                unique_links.append(link)

        if not unique_links:
            return "No links found on the page."

        return f"**Links found ({len(unique_links)}):**\n\n" + "\n".join(unique_links[:50])

    def _extract_tables(self, soup: BeautifulSoup) -> str:
        """Extract tables from page as formatted text.

        Args:
            soup: BeautifulSoup object.

        Returns:
            Formatted table data.
        """
        tables = soup.find_all('table')
        if not tables:
            return "No tables found on the page."

        result_parts = []
        for i, table in enumerate(tables[:5], 1):
            rows = []
            for tr in table.find_all('tr'):
                cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
                if cells:
                    rows.append(cells)

            if rows:
                # Format as markdown table
                max_cols = max(len(row) for row in rows)
                header = rows[0] if rows else []
                # Pad rows to same length
                for row in rows:
                    while len(row) < max_cols:
                        row.append("")

                md_table = "| " + " | ".join(header) + " |\n"
                md_table += "| " + " | ".join(["---"] * max_cols) + " |\n"
                for row in rows[1:]:
                    md_table += "| " + " | ".join(row) + " |\n"

                result_parts.append(f"**Table {i}:**\n{md_table}")

        return "\n\n".join(result_parts)

    def _extract_all(self, soup: BeautifulSoup, url: str) -> str:
        """Extract all content types.

        Args:
            soup: BeautifulSoup object.
            url: Source URL.

        Returns:
            Combined text, links, and tables.
        """
        parts = [
            self._extract_text(soup, url),
            "\n\n---\n\n" + self._extract_links(soup, url),
        ]

        tables = self._extract_tables(soup)
        if "No tables" not in tables:
            parts.append("\n\n---\n\n" + tables)

        return "\n".join(parts)
