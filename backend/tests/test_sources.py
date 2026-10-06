from app.services.evidence.sources import extract_text, manufacturer_for, normalize_url, source_from_result
from app.services.errors import ServiceError
import pytest


def test_source_normalization_preserves_variant_url():
    source = source_from_result(
        {"link": "https://psref.lenovo.com/ThinkPad_T480s.pdf#page=1", "title": "T480s"}
    )
    assert source.source_type == "manufacturer"
    assert source.url.endswith("T480s.pdf")
    assert manufacturer_for("https://lenovo.com.attacker.example/spec") is None


def test_source_rejects_credentials_and_nonweb():
    for url in ("file:///etc/passwd", "https://user:password@lenovo.com/", "http://lenovo.com:9999/"):
        with pytest.raises(ServiceError):
            normalize_url(url)


def test_html_extraction_removes_script_and_nav():
    text = extract_text(
        b"<nav>ignore</nav><h1>Exact model</h1><script>attack</script><p>DDR4 SO-DIMM</p>", "text/html"
    )
    assert text == "Exact model DDR4 SO-DIMM"


def test_search_snippet_is_not_document_evidence():
    source = source_from_result({"link": "https://example.com/", "snippet": "32GB"})
    assert source.text == ""
    assert source.source_type == "search_result"
