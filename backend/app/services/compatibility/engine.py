from dataclasses import dataclass
from app.schemas.domain import Check, Fact, Offer, RunInput
from app.services.evidence.validation import identity_key


@dataclass
class Evidence:
    facts: list[Fact]

    @property
    def disputed(self):
        return len({str(f.value) for f in self.facts}) > 1

    @property
    def value(self):
        return self.facts[0].value if self.facts and not self.disputed else None


def find(facts: list[Fact], subject: str, field: str) -> Evidence:
    return Evidence(
        [
            f
            for f in facts
            if f.status == "supported"
            and identity_key(f.subject) == identity_key(subject)
            and f.field == field
        ]
    )


@dataclass
class Context:
    input: RunInput
    offer: Offer
    facts: list[Fact]

    def device(self, field):
        return find(self.facts, self.input.device_model, field)

    def part(self, field):
        return find(self.facts, self.offer.part_number or "", field)

    def check(
        self, name, label, status, explanation, required=None, observed=None, evidence=(), critical=True
    ):
        records = [fact for group in evidence for fact in group.facts]
        return Check(
            offer_id=self.offer.id,
            check_type=name,
            label=label,
            status=status,
            critical=critical,
            explanation=explanation,
            required=required,
            observed=observed,
            source_ids=list(dict.fromkeys(f.source_id for f in records)),
            fact_ids=list(dict.fromkeys(f.id for f in records)),
        )


def check_identity(c: Context, device: bool) -> Check:
    evidence = c.device("identity") if device else c.part("identity")
    name = "device_identity" if device else "part_identity"
    label = "Exact laptop" if device else "Exact part"
    subject = c.input.device_model if device else c.offer.part_number
    if not subject or evidence.value is None:
        return c.check(
            name, label, "unknown", "Exact identity needs manufacturer evidence.", subject, None, (evidence,)
        )
    return c.check(
        name,
        label,
        "pass",
        "The exact identity is present in a manufacturer source.",
        subject,
        evidence.value,
        (evidence,),
    )


def compare(c: Context, field: str, label: str, conditional=False) -> Check:
    required, observed = c.device(field), c.part(field)
    critical = not conditional or bool(required.facts)
    if required.value is None or observed.value is None:
        message = (
            "Manufacturer sources disagree on this field."
            if required.disputed or observed.disputed
            else "A documented requirement or exact-part specification is missing."
        )
        return c.check(
            field, label, "unknown", message, required.value, observed.value, (required, observed), critical
        )
    passed = required.value == observed.value
    return c.check(
        field,
        label,
        "pass" if passed else "conflict",
        "The documented specifications match."
        if passed
        else "The documented requirement and part specification do not match.",
        required.value,
        observed.value,
        (required, observed),
        critical,
    )


def check_memory_generation(c):
    return compare(c, "memory_generation", "DDR generation")


def check_form_factor(c):
    return compare(c, "memory_form_factor", "Form factor")


def check_ecc(c):
    return compare(c, "memory_ecc", "ECC requirement", True)


def check_voltage(c):
    return compare(c, "memory_voltage_v", "Voltage requirement", True)


def check_buffering(c):
    return compare(c, "memory_buffering", "Buffering", True)


def check_capacity(c: Context):
    maximum, module = c.device("maximum_capacity_gb"), c.part("module_capacity_gb")
    limit = c.device("module_maximum_gb")
    evidence = (maximum, module, limit)
    if maximum.value is None or module.value is None or limit.disputed:
        return c.check(
            "capacity",
            "Capacity",
            "unknown",
            "Documented system maximum or module capacity is unresolved.",
            maximum.value,
            module.value,
            evidence,
        )
    if limit.value is not None and module.value > limit.value:
        return c.check(
            "capacity",
            "Capacity",
            "conflict",
            "The module exceeds an explicitly documented per-module limit.",
            limit.value,
            module.value,
            evidence,
        )
    if c.input.upgrade_action == "add_module" and c.input.installed_modules_gb is None:
        return c.check(
            "capacity",
            "Capacity",
            "unknown",
            "Confirm the installed modules before calculating the new total.",
            maximum.value,
            None,
            evidence,
        )
    current = sum(c.input.installed_modules_gb or []) if c.input.upgrade_action == "add_module" else 0
    total = current + module.value
    if total > maximum.value:
        return c.check(
            "capacity",
            "Capacity",
            "conflict",
            f"{current} + {module.value} = {total} GB exceeds the documented {maximum.value} GB system limit.",
            maximum.value,
            total,
            evidence,
        )
    return c.check(
        "capacity",
        "Capacity",
        "pass",
        f"{current} + {module.value} = {total} GB is within the documented {maximum.value} GB system limit. Installed capacities are user-provided.",
        maximum.value,
        total,
        evidence,
    )


def check_slots(c: Context):
    slots, replaceable = c.device("memory_slots"), c.device("memory_replaceable")
    ev = (slots, replaceable)
    if replaceable.value is False and slots.value in (None, 0):
        return c.check(
            "slots",
            "Slot availability",
            "conflict",
            "The retrieved documentation describes memory that cannot be replaced.",
            None,
            None,
            ev,
        )
    if slots.value is None:
        return c.check(
            "slots",
            "Slot availability",
            "unknown",
            "The documented socket count is missing or disputed.",
            None,
            c.input.free_slots,
            ev,
        )
    if slots.value < 1:
        return c.check(
            "slots", "Slot availability", "conflict", "No memory socket is documented.", slots.value, 1, ev
        )
    if c.input.upgrade_action == "replace_all":
        return c.check(
            "slots",
            "Slot availability",
            "pass",
            "You selected replacement of all existing modules with one module; a socket is documented.",
            slots.value,
            1,
            ev,
        )
    if c.input.free_slots is None or c.input.installed_modules_gb is None:
        return c.check(
            "slots",
            "Slot availability",
            "unknown",
            "Confirm installed modules and free slots. The model alone cannot establish the current configuration.",
            slots.value,
            c.input.free_slots,
            ev,
        )
    if len(c.input.installed_modules_gb) + c.input.free_slots != slots.value:
        return c.check(
            "slots",
            "Slot availability",
            "unknown",
            "The reported installed modules and free slots do not agree with the documented socket count; clarify the configuration.",
            slots.value,
            len(c.input.installed_modules_gb) + c.input.free_slots,
            ev,
        )
    if c.input.free_slots == 0:
        return c.check(
            "slots",
            "Slot availability",
            "conflict",
            "No free slot was reported for adding another module. Consider a replacement investigation.",
            ">= 1 free slot",
            0,
            ev,
        )
    return c.check(
        "slots",
        "Slot availability",
        "pass",
        "A free slot was confirmed by you and the configuration agrees with the documented socket count.",
        ">= 1 free slot",
        c.input.free_slots,
        ev,
    )


def check_speed(c: Context):
    required, observed = c.device("memory_speed_mts"), c.part("memory_speed_mts")
    listed = c.part("manufacturer_listed")
    if required.disputed or observed.disputed:
        return c.check(
            "speed",
            "Speed / profile",
            "unknown",
            "Sources disagree about memory speed.",
            required.value,
            observed.value,
            (required, observed),
        )
    if required.value is None or observed.value is None:
        return c.check(
            "speed",
            "Speed / profile",
            "unknown",
            "A speed/profile check was not established.",
            required.value,
            observed.value,
            (required, observed),
            bool(required.facts),
        )
    if required.value == observed.value or listed.value is True:
        return c.check(
            "speed",
            "Speed / profile",
            "pass",
            "This exact part is manufacturer-listed for the model; a higher advertised rate alone is not a conflict. Actual operating speed is not promised."
            if listed.value is True
            else "The documented headline memory rates match; no overclocking profile is assumed.",
            required.value,
            observed.value,
            (required, observed, listed),
        )
    return c.check(
        "speed",
        "Speed / profile",
        "unknown",
        "Different headline rates need supported profile/downclock evidence; speed alone is not an incompatibility verdict.",
        required.value,
        observed.value,
        (required, observed),
    )


def check_documented_restrictions(c: Context):
    restrictions = c.device("documented_restrictions")
    return c.check(
        "restrictions",
        "Other restrictions",
        "unknown",
        "An additional documented restriction needs manual review: " + str(restrictions.value)
        if restrictions.facts
        else "No additional restriction was established in the retrieved evidence; this is not proof that none exist.",
        restrictions.value,
        None,
        (restrictions,),
        bool(restrictions.facts),
    )


def evaluate(inputs: RunInput, offer: Offer, facts: list[Fact]) -> tuple[Offer, list[Check]]:
    c = Context(inputs, offer, facts)
    checks = [
        check_identity(c, True),
        check_identity(c, False),
        check_memory_generation(c),
        check_form_factor(c),
        check_capacity(c),
        check_slots(c),
        check_ecc(c),
        check_voltage(c),
        check_buffering(c),
        check_speed(c),
        check_documented_restrictions(c),
    ]
    critical = [check for check in checks if check.critical]
    listed = [
        f
        for f in c.part("manufacturer_listed").facts
        if f.value is True
        and f.related_subject
        and identity_key(f.related_subject) == identity_key(inputs.device_model)
    ]
    result = (
        "CONFLICT_FOUND"
        if any(x.status == "conflict" for x in critical)
        else "NEEDS_INFORMATION"
        if any(x.status == "unknown" for x in critical)
        else "MATCHES_CHECKED_SPECIFICATIONS"
    )
    offer = offer.model_copy(
        update={
            "result": result,
            "manufacturer_listed": bool(listed),
            "identity_status": "resolved" if checks[1].status == "pass" else "unresolved",
        }
    )
    return offer, checks
