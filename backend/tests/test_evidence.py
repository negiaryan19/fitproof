import pytest
from app.schemas.domain import Source, FactDraft
from app.services.evidence.validation import validate_fact, subject_present


def validate(value, span, text=None, field="memory_form_factor"):
    source = Source(
        url="https://psref.lenovo.com/ThinkPad_T480.pdf",
        title="T480",
        publisher="Lenovo",
        source_type="manufacturer",
        text=text or span,
    )
    fact = FactDraft(subject="Lenovo ThinkPad T480", field=field, value=value, evidence_span=span)
    return validate_fact(fact, source, "Lenovo ThinkPad T480", "Lenovo ThinkPad T480")


def test_supported_fact():
    assert validate("SODIMM", "two DDR4 SO-DIMM sockets").status == "supported"


def test_wrong_value_in_real_quote_is_rejected():
    assert validate("DIMM", "two DDR4 SO-DIMM sockets").status == "unverified"


def test_invented_quote_is_rejected():
    assert validate("SO-DIMM", "SO-DIMM memory", "Only DDR5").status == "unverified"


def test_model_suffix_is_not_collapsed():
    assert not subject_present("Lenovo ThinkPad T480", "ThinkPad T480s")
    assert subject_present("Lenovo ThinkPad T480", "ThinkPad_T480")


@pytest.mark.parametrize(
    "field,value,span",
    [
        ("maximum_capacity_gb", 32, "32GB max / 2400MHz DDR4"),
        ("memory_slots", 2, "two DDR4 SO-DIMM sockets"),
        ("memory_generation", "DDR4", "2400MHz DDR4"),
    ],
)
def test_typed_values(field, value, span):
    assert validate(value, span, field=field).status == "supported"


def test_number_cannot_be_invented_from_quote():
    assert validate(64, "32GB max", field="maximum_capacity_gb").status == "unverified"


def test_part_fact_cannot_borrow_neighbor_specs():
    source = Source(
        url="https://www.kingston.com/en/memory/search/model/97858/lenovo-thinkpad-t480",
        title="T480",
        publisher="Kingston",
        source_type="manufacturer",
        text="KCP432SD8/16 16GB DDR4. Another part SO-DIMM.",
    )
    fact = FactDraft(
        subject="KCP432SD8/16",
        field="memory_form_factor",
        value="SO-DIMM",
        evidence_span="Another part SO-DIMM.",
    )
    assert validate_fact(fact, source, "KCP432SD8/16", "Lenovo ThinkPad T480").status == "unverified"


def test_retailer_quote_cannot_drive_pass():
    source = Source(
        url="https://shop.example/model",
        title="Model A",
        publisher="Shop",
        source_type="retailer",
        text="Model A DDR4",
    )
    fact = FactDraft(subject="Model A", field="memory_generation", value="DDR4", evidence_span="Model A DDR4")
    assert validate_fact(fact, source, "Model A", "Model A").status == "unverified"
