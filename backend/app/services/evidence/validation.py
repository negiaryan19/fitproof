import re
import unicodedata
from urllib.parse import unquote
from app.schemas.domain import Fact, FactDraft, Source


def compact(text: str) -> str:
    return (
        re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text).replace("–", "-").replace("‑", "-"))
        .strip()
        .casefold()
    )


def identity_key(text: str) -> str:
    return re.sub(r"[^a-z0-9/]", "", text.casefold())


def subject_present(subject: str, text: str) -> bool:
    text = compact(unquote(text)).replace("_", " ")
    subject = compact(subject)
    subject = re.sub(r"^(lenovo|kingston|dell|hp|asus|acer|crucial|micron|corsair|samsung)\s+", "", subject)
    pieces = re.split(r"[\s_-]+", subject)
    pattern = r"(?<![a-z0-9])" + r"[\s_-]*".join(re.escape(p) for p in pieces) + r"(?![a-z0-9])"
    return bool(re.search(pattern, text))


def normalize_value(field: str, value):
    if field == "memory_form_factor":
        token = re.sub(r"[^A-Z]", "", str(value).upper())
        return {"SODIMM": "SO-DIMM", "DIMM": "DIMM", "UDIMM": "DIMM"}.get(token, str(value).upper())
    if field == "memory_generation":
        return str(value).upper().replace(" ", "")
    if field == "memory_ecc":
        return (
            "non-ECC"
            if re.search(r"non[ -]?ecc", str(value), re.I)
            else "ECC"
            if str(value).upper() == "ECC"
            else str(value)
        )
    if field == "memory_buffering":
        return str(value).lower()
    return value


def value_supported(draft: FactDraft, excerpt: str) -> bool:
    field, value = draft.field, normalize_value(draft.field, draft.value)
    excerpt = compact(excerpt)
    if field == "identity":
        return subject_present(draft.subject, excerpt) and identity_key(str(value)) == identity_key(
            draft.subject
        )
    if field == "memory_generation":
        return bool(re.search(r"\b" + re.escape(str(value).lower()) + r"\b", excerpt))
    if field == "memory_form_factor":
        sodimm = bool(re.search(r"\bso[ -]?dimm\b", excerpt))
        dimm = bool(re.search(r"(?<!so-)(?<!so )\b(?:u?dimm)\b", excerpt))
        return (
            sodimm and not dimm if value == "SO-DIMM" else dimm and not sodimm if value == "DIMM" else False
        )
    if field == "memory_ecc":
        non = bool(re.search(r"non[ -]?ecc", excerpt))
        return non if value == "non-ECC" else bool(re.search(r"\becc\b", excerpt)) and not non
    if field == "memory_buffering":
        return (str(value) == "unbuffered" and "unbuffered" in excerpt) or (
            str(value) == "registered" and "registered" in excerpt and "unregistered" not in excerpt
        )
    if field in {
        "maximum_capacity_gb",
        "module_capacity_gb",
        "module_maximum_gb",
        "memory_voltage_v",
        "memory_speed_mts",
    }:
        if type(value) not in (int, float) or value <= 0:
            return False
        number = str(int(value)) if float(value).is_integer() else str(value)
        unit = (
            "g(?:b|bytes?)"
            if field.endswith("_gb")
            else "v(?:olts?)?"
            if field == "memory_voltage_v"
            else "(?:mt/s|mhz)"
        )
        literal = bool(re.search(r"(?<![\d.])" + re.escape(number) + r"\s*" + unit + r"\b", excerpt))
        if field in {"maximum_capacity_gb", "module_maximum_gb"}:
            literal = literal and bool(re.search(r"max(?:imum)?|up to|supports? up to", excerpt))
        return literal
    if field == "memory_slots":
        if type(value) is not int or not 0 <= value <= 8:
            return False
        words = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight"]
        return bool(
            re.search(
                r"\b(?:"
                + str(value)
                + "|"
                + words[value]
                + r")\b(?:[\s-]+\w+){0,5}[\s-]+(?:slots?|sockets?)\b",
                excerpt,
            )
        )
    if field == "memory_replaceable":
        return type(value) is bool and (
            value is False
            and bool(re.search(r"soldered|not (?:upgradeable|replaceable)", excerpt))
            or value is True
            and bool(re.search(r"replaceable|upgradeable|upgradable", excerpt))
            and "not " not in excerpt
        )
    if field == "documented_restrictions":
        return isinstance(value, str) and compact(value) in excerpt and len(value) > 8
    return False


def validate_fact(draft: FactDraft, source: Source, expected_subject: str, device: str) -> Fact:
    fact = Fact(**draft.model_dump(), source_id=source.id)

    def reject(reason):
        fact.validation_reason = reason
        return fact

    if source.fetch_status != "available" or source.source_type != "manufacturer":
        return reject("An available manufacturer document is required for specification checks.")
    if identity_key(draft.subject) != identity_key(expected_subject):
        return reject("The extracted subject does not match the requested exact identity.")
    span = compact(draft.evidence_span)
    if len(span) < 3 or span not in compact(source.text):
        return reject("The supporting excerpt was not found in the retrieved document.")
    if not subject_present(expected_subject, source.text + " " + source.url):
        return reject("The exact requested subject was not established in this source.")
    is_part = not identity_key(expected_subject) == identity_key(device)
    if (
        is_part
        and not subject_present(expected_subject, draft.evidence_span)
        and not subject_present(expected_subject, source.url)
    ):
        return reject("A multi-product source must bind the quoted specification to this exact part number.")
    if draft.field == "manufacturer_listed":
        mapping_page = "/memory/search/model/" in source.url and subject_present(device, source.url)
        explicit_mapping = subject_present(device, draft.evidence_span) and bool(
            re.search(r"compatible|supports|for", draft.evidence_span, re.I)
        )
        if (
            draft.value is not True
            or not draft.related_subject
            or identity_key(draft.related_subject) != identity_key(device)
            or not (mapping_page or explicit_mapping)
        ):
            return reject("No explicit exact-part to exact-device manufacturer relationship was established.")
    elif not value_supported(draft, draft.evidence_span):
        return reject("The quoted text does not support this normalized value.")
    fact.value = normalize_value(draft.field, draft.value)
    fact.status = "supported"
    fact.confidence = "high"
    fact.validation_reason = "Exact subject, source excerpt and normalized value validated."
    return fact
