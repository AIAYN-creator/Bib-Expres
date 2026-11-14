import pytest

from bib_expres.access import (
    INSTITUTION,
    NONE,
    OPEN,
    OPEN_BRONZE,
    UNKNOWN,
    AccessConfig,
    InvalidLibraryTemplate,
    access_status,
    annotate_access,
    format_publishers,
    is_openable_url,
    is_readable,
    library_link,
    parse_publishers,
    publisher_counts,
    validate_library_template,
)
from bib_expres.models import DiscoveryMode, Paper


def _paper(**overrides):
    defaults = dict(
        openalex_id="W1", doi="10.1/abc", title="T", authors=[], year=2020, venue=None,
        concepts=[], citation_count=0, generation=1, discovered_via=DiscoveryMode.REFERENCE,
    )
    defaults.update(overrides)
    return Paper(**defaults)


# -- plantilla de enlace -------------------------------------------------------


def test_validate_template_accepts_common_systems():
    for t in (
        "https://proxy.uni.edu/login?url=",
        "https://go.openathens.net/redirector/uni.edu?url=",
        "https://resolver.uni.edu/openurl?rft_id=info:doi/{doi}",
    ):
        assert validate_library_template(t) == t


@pytest.mark.parametrize(
    "bad",
    ["http://proxy.uni.edu/login?url=", "javascript:alert(1)", "https://", "https://a b.edu/", "ftp://x.edu/"],
)
def test_validate_template_rejects(bad):
    with pytest.raises(InvalidLibraryTemplate):
        validate_library_template(bad)


def test_validate_template_empty_means_unset():
    assert validate_library_template("  ") == ""


def test_library_link_prefix_mode_encodes_doi_url():
    url = library_link("https://proxy.uni.edu/login?url=", "10.1/abc")
    assert url == "https://proxy.uni.edu/login?url=https%3A%2F%2Fdoi.org%2F10.1%2Fabc"


def test_library_link_placeholders():
    assert library_link("https://r.uni.edu/?id=doi:{doi}", "10.1/abc") == "https://r.uni.edu/?id=doi:10.1/abc"
    assert library_link("https://r.uni.edu/?u={url}", "10.1/abc") == (
        "https://r.uni.edu/?u=https%3A%2F%2Fdoi.org%2F10.1%2Fabc"
    )


def test_library_link_hostile_doi_cannot_escape():
    url = library_link("https://r.uni.edu/?id={doi}", "10.1/x&evil=1#frag ")
    assert "&evil" not in url and "#" not in url and " " not in url


def test_library_link_needs_template_and_doi():
    assert library_link("", "10.1/abc") is None
    assert library_link("https://p.edu/login?url=", None) is None


def test_is_openable_url():
    assert is_openable_url("http://www.cell.com/a.pdf")
    assert is_openable_url("https://doi.org/10.1/x")
    assert not is_openable_url("javascript:alert(1)")
    assert not is_openable_url("file:///etc/passwd")
    assert not is_openable_url(None)


# -- estado de acceso ------------------------------------------------------------


def test_access_status_open_and_bronze():
    assert access_status(_paper(open_access=True, oa_status="gold"), set()) == OPEN
    assert access_status(_paper(open_access=True, oa_status="bronze"), set()) == OPEN_BRONZE


def test_access_status_matches_parent_publisher():
    cell = _paper(open_access=False, publisher_lineage=["Cell Press", "Elsevier BV"])
    assert access_status(cell, {"Elsevier BV"}) == INSTITUTION
    assert access_status(cell, {"Wiley"}) == NONE


def test_access_status_unknown_without_data():
    assert access_status(_paper(open_access=False, publisher_lineage=["Wiley"]), set()) == UNKNOWN
    assert access_status(_paper(open_access=False), {"Wiley"}) == UNKNOWN
    assert access_status(_paper(open_access=None), set()) == UNKNOWN


def test_is_readable():
    assert is_readable(OPEN) and is_readable(OPEN_BRONZE) and is_readable(INSTITUTION)
    assert not is_readable(NONE)
    assert is_readable(UNKNOWN) and not is_readable(UNKNOWN, include_unknown=False)


def test_annotate_access_prefers_open_version():
    oa = _paper(open_access=True, oa_url="https://repo.edu/a.pdf")
    closed = _paper(open_access=False, doi="10.1/closed")
    weird = _paper(open_access=True, oa_url="javascript:alert(1)", doi="10.1/w")
    annotate_access([oa, closed, weird], AccessConfig(library_template="https://p.edu/login?url="))
    assert oa.access_url == "https://repo.edu/a.pdf"
    assert closed.access_url.startswith("https://p.edu/login?url=")
    assert weird.access_url.startswith("https://p.edu/")  # el oa_url hostil se ignora


def test_publishers_roundtrip_with_commas():
    pubs = {"Springer Science+Business Media, LLC", "Elsevier BV"}
    assert parse_publishers(format_publishers(pubs)) == pubs
    assert parse_publishers(None) == set()


def test_publisher_counts_groups_by_parent():
    papers = [
        _paper(publisher_lineage=["Cell Press", "Elsevier BV"]),
        _paper(publisher_lineage=["Elsevier BV"]),
        _paper(publisher_lineage=["Wiley"]),
        _paper(publisher_lineage=[]),
    ]
    assert publisher_counts(papers) == [("Elsevier BV", 2), ("Wiley", 1)]
