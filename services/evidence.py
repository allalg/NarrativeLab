from __future__ import annotations
from typing import List, Dict, Any, Optional
from models.schemas import Source, EvidenceDossier

class EvidenceService:
    """Handles source deduplication, ranking, and evidence dossier formatting."""

    @staticmethod
    def deduplicate_sources(sources: List[Source]) -> List[Source]:
        """Deduplicate sources by canonical URL and title."""
        seen_urls = set()
        seen_titles = set()
        unique_sources: List[Source] = []
        
        for s in sources:
            clean_url = s.url.strip().lower().rstrip("/")
            clean_title = s.title.strip().lower()
            
            if clean_url and clean_url in seen_urls:
                continue
            if clean_title and clean_title in seen_titles:
                continue
                
            if clean_url:
                seen_urls.add(clean_url)
            if clean_title:
                seen_titles.add(clean_title)
                
            unique_sources.append(s)
            
        # Re-index with stable sequential IDs
        reindexed: List[Source] = []
        for idx, s in enumerate(unique_sources, start=1):
            reindexed.append(
                Source(
                    id=f"SRC_{idx:02d}",
                    url=s.url,
                    title=s.title,
                    publisher=s.publisher,
                    published_date=s.published_date,
                    snippet=s.snippet
                )
            )
        return reindexed

    @staticmethod
    def format_sources_for_context(sources: List[Source]) -> str:
        """Format sources into a compact, structured text block for LLM prompts."""
        if not sources:
            return "No verified sources retrieved."

        lines = []
        for s in sources:
            pub_info = f" ({s.publisher})" if s.publisher else ""
            date_info = f" [{s.published_date}]" if s.published_date else ""
            lines.append(f"[{s.id}] {s.title}{pub_info}{date_info}\nURL: {s.url}\nSummary: {s.snippet}\n")
        return "\n".join(lines)

    @staticmethod
    def validate_citations(cited_ids: List[str], valid_sources: List[Source]) -> Dict[str, Any]:
        """Check if cited source IDs exist in the evidence dossier."""
        valid_id_set = {s.id for s in valid_sources}
        valid_citations = [cid for cid in cited_ids if cid in valid_id_set]
        invalid_citations = [cid for cid in cited_ids if cid not in valid_id_set]
        return {
            "valid": valid_citations,
            "invalid": invalid_citations,
            "is_all_valid": len(invalid_citations) == 0
        }
