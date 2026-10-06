import pytest
from app.schemas.domain import RunInput, Offer, Fact
from app.services.compatibility.engine import evaluate

DEVICE = "Example Laptop X1"
PART = "TEST-16"


def facts():
    values = [
        (DEVICE, "identity", DEVICE),
        (DEVICE, "memory_generation", "DDR4"),
        (DEVICE, "memory_form_factor", "SO-DIMM"),
        (DEVICE, "maximum_capacity_gb", 32),
        (DEVICE, "memory_slots", 2),
        (PART, "identity", PART),
        (PART, "memory_generation", "DDR4"),
        (PART, "memory_form_factor", "SO-DIMM"),
        (PART, "module_capacity_gb", 16),
    ]
    return [
        Fact(
            subject=s,
            field=f,
            value=v,
            evidence_span="Reviewed synthetic rule fixture",
            source_id="test-source",
            status="supported",
        )
        for s, f, v in values
    ]


def run(fs=None, **changes):
    inputs = RunInput(device_model=DEVICE, installed_modules_gb=[8], free_slots=1, **changes)
    return evaluate(inputs, Offer(title=PART, part_number=PART), facts() if fs is None else fs)


def change(field, value, subject=PART):
    fs = facts()
    for f in fs:
        if f.field == field and f.subject == subject:
            f.value = value
    return fs


def test_matches_only_checked_specs():
    offer, checks = run()
    assert offer.result == "MATCHES_CHECKED_SPECIFICATIONS"
    assert any(c.status == "unknown" and not c.critical for c in checks)


@pytest.mark.parametrize(
    "field,value", [("memory_generation", "DDR5"), ("memory_form_factor", "DIMM"), ("module_capacity_gb", 32)]
)
async def test_conflicts(field, value):
    assert run(change(field, value))[0].result == "CONFLICT_FOUND"


def test_unknown_never_becomes_pass():
    fs = [f for f in facts() if f.field != "memory_form_factor"]
    assert run(fs)[0].result == "NEEDS_INFORMATION"


def test_missing_sku():
    assert (
        evaluate(
            RunInput(device_model=DEVICE, installed_modules_gb=[8], free_slots=1),
            Offer(title="Generic RAM"),
            facts(),
        )[0].result
        == "NEEDS_INFORMATION"
    )


def test_missing_configuration():
    result, _ = evaluate(RunInput(device_model=DEVICE), Offer(title=PART, part_number=PART), facts())
    assert result.result == "NEEDS_INFORMATION"


def test_no_free_slot():
    result, _ = evaluate(
        RunInput(device_model=DEVICE, installed_modules_gb=[8, 8], free_slots=0),
        Offer(title=PART, part_number=PART),
        facts(),
    )
    assert result.result == "CONFLICT_FOUND"


def test_disputed_authoritative_facts_are_unknown():
    fs = facts() + [
        Fact(
            subject=PART,
            field="memory_form_factor",
            value="DIMM",
            evidence_span="Conflicting fixture",
            source_id="different",
            status="supported",
        )
    ]
    assert run(fs)[0].result == "NEEDS_INFORMATION"


def test_unverified_fact_cannot_pass():
    fs = facts()
    for f in fs:
        if f.field == "identity" and f.subject == PART:
            f.status = "unverified"
    assert run(fs)[0].result == "NEEDS_INFORMATION"


def test_manufacturer_listing_never_overrides_configuration_unknown():
    fs = facts() + [
        Fact(
            subject=PART,
            field="manufacturer_listed",
            value=True,
            related_subject=DEVICE,
            evidence_span="Test explicit mapping",
            source_id="mapping",
            status="supported",
        )
    ]
    offer, _ = evaluate(RunInput(device_model=DEVICE), Offer(title=PART, part_number=PART), fs)
    assert offer.manufacturer_listed
    assert offer.result == "NEEDS_INFORMATION"


def test_faster_manufacturer_listed_module_not_rejected():
    fs = facts() + [
        Fact(
            subject=DEVICE,
            field="memory_speed_mts",
            value=2400,
            evidence_span="Test speed evidence",
            source_id="s",
            status="supported",
        ),
        Fact(
            subject=PART,
            field="memory_speed_mts",
            value=3200,
            evidence_span="Test speed evidence",
            source_id="s",
            status="supported",
        ),
        Fact(
            subject=PART,
            field="manufacturer_listed",
            value=True,
            related_subject=DEVICE,
            evidence_span="Test explicit mapping",
            source_id="s",
            status="supported",
        ),
    ]
    assert run(fs)[0].result == "MATCHES_CHECKED_SPECIFICATIONS"


def test_replacing_all_uses_new_total():
    result, checks = run(upgrade_action="replace_all")
    assert result.result == "MATCHES_CHECKED_SPECIFICATIONS"
    assert next(c for c in checks if c.check_type == "capacity").observed == 16
