from __future__ import annotations
from models.schemas import Source
from services.evidence import EvidenceService

def test_evidence_deduplication():
    sources = [
        Source(id="SRC_99", url="https://reuters.com/article1", title="Article 1", snippet="Snippet 1"),
        Source(id="SRC_88", url="https://reuters.com/article1/", title="Article 1 Duplicate", snippet="Snippet 2"), # Duplicate URL
        Source(id="SRC_77", url="https://bbc.com/article2", title="Article 2", snippet="Snippet 3"),
    ]

    deduped = EvidenceService.deduplicate_sources(sources)
    assert len(deduped) == 2
    assert deduped[0].id == "SRC_01"
    assert deduped[1].id == "SRC_02"

def test_citation_validation():
    valid_sources = [
        Source(id="SRC_01", url="https://a.com", title="A", snippet="A"),
        Source(id="SRC_02", url="https://b.com", title="B", snippet="B"),
    ]

    res = EvidenceService.validate_citations(["SRC_01", "SRC_99"], valid_sources)
    assert res["valid"] == ["SRC_01"]
    assert res["invalid"] == ["SRC_99"]
    assert res["is_all_valid"] is False
