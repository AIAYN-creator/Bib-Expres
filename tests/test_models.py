from bib_expres.models import Concept, DiscoveryMode, Paper


def test_paper_construction():
    paper = Paper(
        openalex_id="W123",
        doi="10.1000/xyz",
        title="Example paper",
        authors=["A. Author"],
        year=2020,
        venue="Journal of Examples",
        concepts=[Concept(name="Machine learning", score=0.9)],
        citation_count=42,
        generation=0,
        discovered_via=DiscoveryMode.ROOT,
    )
    assert paper.relevance_score is None
    assert paper.concepts[0].name == "Machine learning"
