"""
Search tool for ResearchAgent.

Provides web search capabilities using DuckDuckGo or SerpAPI.
Includes result caching to avoid redundant queries.
"""

import hashlib
import json
from datetime import datetime
from typing import Any, Optional

import requests
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from backend.memory.storage import StorageManager
from backend.utils.config import settings
from backend.utils.logger import get_logger

logger = get_logger("search_tool")


class SearchInput(BaseModel):
    """Input schema for search tool."""
    query: str = Field(description="The search query to execute")
    num_results: int = Field(default=5, description="Number of results to return", ge=1, le=20)


class SearchTool(BaseTool):
    """Tool for performing web searches.

    Supports DuckDuckGo (default) and SerpAPI as search backends.
    Results are cached to avoid redundant queries within the configured TTL.
    """

    name: str = "web_search"
    description: str = (
        "Search the web for current information. Use this tool when you need to find "
        "recent data, news, statistics, or any information that requires up-to-date sources. "
        "Input should be a clear search query."
    )
    args_schema: type[BaseModel] = SearchInput

    def __init__(self, storage: Optional[StorageManager] = None):
        """Initialize search tool.

        Args:
            storage: Optional storage manager for caching results.
        """
        super().__init__()
        self._storage = storage
        self._cache_ttl = settings.cache_ttl

    def _get_cache_key(self, query: str) -> str:
        """Generate a cache key for a search query."""
        return hashlib.md5(query.lower().strip().encode()).hexdigest()

    async def _check_cache(self, query: str) -> Optional[list[dict]]:
        """Check if results are cached for this query."""
        if not self._storage:
            return None
        cache_key = self._get_cache_key(query)
        return await self._storage.get_cached_search(cache_key)

    async def _save_to_cache(self, query: str, results: list[dict]) -> None:
        """Cache search results."""
        if not self._storage:
            return
        cache_key = self._get_cache_key(query)
        await self._storage.cache_search(cache_key, query, results, self._cache_ttl)

    def _run(self, query: str, num_results: int = 5) -> str:
        """Synchronous search (delegates to async)."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, use a workaround
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self._arun(query, num_results))
                    return future.result()
            return asyncio.run(self._arun(query, num_results))
        except Exception as e:
            logger.error(f"Sync search error: {e}")
            return f"Search failed: {str(e)}"

    async def _arun(self, query: str, num_results: int = 5) -> str:
        """Perform an async web search.

        Args:
            query: Search query string.
            num_results: Number of results to return.

        Returns:
            Formatted search results string.
        """
        # Check cache first
        cached = await self._check_cache(query)
        if cached:
            logger.info(f"Cache hit for query: {query[:50]}...")
            return self._format_results(cached, from_cache=True)

        logger.info(f"Searching: {query}")

        try:
            if settings.search_engine == "serpapi" and settings.serpapi_key:
                results = await self._search_serpapi(query, num_results)
            else:
                results = await self._search_duckduckgo(query, num_results)

            # Cache results
            await self._save_to_cache(query, results)

            return self._format_results(results)

        except Exception as e:
            logger.error(f"Search failed for '{query}': {e}")
            return f"Search failed: {str(e)}. Please try a different query or check your network connection."

    async def _search_duckduckgo(self, query: str, num_results: int) -> list[dict]:
        """Search using DuckDuckGo.

        Args:
            query: Search query.
            num_results: Number of results.

        Returns:
            List of search result dictionaries.
        """
        from duckduckgo_search import DDGS

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=num_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                    "source": "duckduckgo",
                })
        return results

    async def _search_serpapi(self, query: str, num_results: int) -> list[dict]:
        """Search using SerpAPI (Google results).

        Args:
            query: Search query.
            num_results: Number of results.

        Returns:
            List of search result dictionaries.
        """
        params = {
            "q": query,
            "api_key": settings.serpapi_key,
            "engine": "google",
            "num": num_results,
        }
        resp = requests.get("https://serpapi.com/search", params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("organic_results", [])[:num_results]:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "source": "serpapi",
            })
        return results

    def _format_results(self, results: list[dict], from_cache: bool = False) -> str:
        """Format search results as a readable string.

        Args:
            results: List of search result dictionaries.
            from_cache: Whether results came from cache.

        Returns:
            Formatted string.
        """
        if not results:
            return "No search results found. Try a different query."

        header = "Search Results"
        if from_cache:
            header += " (cached)"
        header += ":\n\n"

        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append(
                f"{i}. **{r['title']}**\n"
                f"   URL: {r['url']}\n"
                f"   {r['snippet']}"
            )

        return header + "\n\n".join(formatted)
