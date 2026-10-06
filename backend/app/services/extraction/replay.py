import json
from pathlib import Path
from app.schemas.domain import Extraction, Source
from app.services.evidence.validation import identity_key

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


class ReplayExtractor:
    """Explicit recorded-source demo. No AI or SerpApi call is simulated as live."""

    async def extract(self, source: Source, subject: str, kind: str, device: str) -> Extraction:
        records = json.loads((FIXTURES / "replay_extractions.json").read_text())
        return Extraction(
            facts=[
                f for f in records.get(source.id, []) if identity_key(f["subject"]) == identity_key(subject)
            ]
        )

    async def followup(self, subject, missing, domain):
        return ""


def replay_sources() -> list[Source]:
    return [
        Source.model_validate_json((FIXTURES / (name + ".json")).read_text())
        for name in ("replay_device", "replay_good", "replay_bad")
    ]
