"""Visit ID value object."""
from __future__ import annotations

import random
import re
from datetime import datetime


class VisitId:
    """Visit IDs in ``CONSULT-YYYYMMDD-XXX`` format."""

    _pattern = re.compile(r"^CONSULT-\d{8}-\d{3}$")

    @staticmethod
    def generate(now: datetime | None = None) -> str:
        current = now or datetime.now()
        date_part = current.strftime("%Y%m%d")
        serial = random.randint(1, 999)
        return f"CONSULT-{date_part}-{serial:03d}"

    @staticmethod
    def validate(value: str) -> str:
        normalized = str(value or "").strip()
        if not VisitId._pattern.fullmatch(normalized):
            raise ValueError("visit_id must match format CONSULT-YYYYMMDD-XXX")
        return normalized
"""Visit id module."""
# TODO: Implement this module.
