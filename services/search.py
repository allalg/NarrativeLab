from __future__ import annotations
import os
import logging
from typing import List, Dict, Any, Optional
from models.schemas import Source

logger = logging.getLogger(__name__)

class SearchService:
    """
    Search service supporting Tavily (Basic Search, 1 credit/query)
    and DuckDuckGo (unlimited/free) with automatic fallback.
    """

    def __init__(self, tavily_api_key: Optional[str] = None):
        self.tavily_api_key = tavily_api_key or os.getenv("TAVILY_API_KEY")
        self._tavily_client = None
        if self.tavily_api_key:
            try:
                from tavily import TavilyClient
                self._tavily_client = TavilyClient(api_key=self.tavily_api_key)
            except Exception as e:
                logger.warning(f"Failed to initialize TavilyClient: {e}")

    def search_duckduckgo(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Search using DuckDuckGo (free, 0 credits used)."""
        results = []
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS

            with DDGS() as ddgs:
                ddg_gen = ddgs.text(query, max_results=max_results)
                for item in ddg_gen:
                    results.append({
                        "title": item.get("title", "Untitled"),
                        "url": item.get("href", item.get("url", "")),
                        "snippet": item.get("body", item.get("snippet", "")),
                        "publisher": item.get("publisher", ""),
                        "published_date": None
                    })
        except Exception as e:
            logger.error(f"DuckDuckGo search error for query '{query}': {e}")
        return results

    def search_tavily(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Search using Tavily Basic Search (1 credit per query)."""
        if not self._tavily_client:
            logger.info("Tavily client not available; falling back to DuckDuckGo.")
            return self.search_duckduckgo(query, max_results=max_results)

        try:
            # search_depth="basic" costs exactly 1 credit per query
            response = self._tavily_client.search(
                query=query,
                search_depth="basic",
                max_results=max_results,
                include_raw_content=False,
                include_answer=False
            )
            raw_results = response.get("results", [])
            results = []
            for item in raw_results:
                results.append({
                    "title": item.get("title", "Untitled"),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", ""),
                    "publisher": None,
                    "published_date": item.get("published_date")
                })
            return results
        except Exception as e:
            logger.warning(f"Tavily search failed ({e}); falling back to DuckDuckGo.")
            return self.search_duckduckgo(query, max_results=max_results)

    def search(
        self, 
        query: str, 
        provider: str = "hybrid", 
        max_results: int = 5,
        is_primary_topic_query: bool = False
    ) -> List[Source]:
        """
        Unified search interface.
        If provider is 'hybrid': uses Tavily basic (1 credit) ONLY for the primary query,
        and DuckDuckGo for secondary queries to conserve user credits.
        """
        provider_setting = os.getenv("SEARCH_PROVIDER", provider).lower()
        
        raw_results: List[Dict[str, Any]] = []
        if provider_setting == "tavily":
            raw_results = self.search_tavily(query, max_results=max_results)
        elif provider_setting == "duckduckgo":
            raw_results = self.search_duckduckgo(query, max_results=max_results)
        else: # hybrid
            if is_primary_topic_query and self._tavily_client:
                logger.info("Hybrid search: Using Tavily Basic (1 credit) for primary topic query.")
                raw_results = self.search_tavily(query, max_results=max_results)
            else:
                logger.info("Hybrid search: Using DuckDuckGo (0 credits) for query.")
                raw_results = self.search_duckduckgo(query, max_results=max_results)

        # Normalize into Source models with stable IDs
        sources: List[Source] = []
        for idx, item in enumerate(raw_results, start=1):
            source = Source(
                id=f"SRC_{idx:02d}",
                url=item.get("url", ""),
                title=item.get("title", f"Source {idx}"),
                publisher=item.get("publisher"),
                published_date=item.get("published_date"),
                snippet=item.get("snippet", "")
            )
            sources.append(source)
            
        return sources
