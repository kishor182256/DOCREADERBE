from __future__ import annotations

import re
from datetime import date
from typing import TYPE_CHECKING

from app.services.extraction.base_extractor import BaseExtractor
from app.services.extraction.models import ExtractionResult

if TYPE_CHECKING:
    from app.services.processing_context import ProcessingContext


class AadhaarExtractor(BaseExtractor):
    document_type = "AADHAAR_CARD"

    def extract(self, context: ProcessingContext) -> ExtractionResult:
        ocr_text = "\n".join(result.text for result in context.ocr_results)
        normalized_text = self._normalize_text(ocr_text)

        fields: dict[str, str] = {}
        warnings: list[str] = []
        errors: list[str] = []

        aadhaar_number = self._extract_aadhaar_number(normalized_text)
        if aadhaar_number:
            fields["aadhaar_number"] = aadhaar_number
        else:
            errors.append("Aadhaar number not detected.")

        dob = self._extract_dob(normalized_text)
        if dob:
            fields["dob"] = dob
        else:
            warnings.append("Date of birth not detected.")

        name = self._extract_name(ocr_text)
        if name:
            fields["name"] = name
        else:
            warnings.append("Name not detected.")

        address = self._extract_address(ocr_text)
        if address:
            fields["address"] = address
        else:
            warnings.append("Address not detected.")

        confidence = self._calculate_confidence(fields=fields, errors=errors, warnings=warnings)
        return ExtractionResult(
            document_type=self.document_type,
            fields=fields,
            confidence=confidence,
            warnings=warnings,
            errors=errors,
            extractor="aadhaar_rule_based_v1",
        )

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def _extract_aadhaar_number(self, text: str) -> str | None:
        match = re.search(r"\b([2-9]\d{3})\s?(\d{4})\s?(\d{4})\b", text)
        if match is None:
            return None
        return "".join(match.groups())

    def _extract_dob(self, text: str) -> str | None:
        match = re.search(r"(?:dob|date of birth)\s*[:\-]?\s*(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})", text, re.IGNORECASE)
        if match is None:
            return None

        day, month, year = (int(part) for part in match.groups())
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return None

    def _extract_name(self, text: str) -> str | None:
        ignored_fragments = (
            "government",
            "unique identification",
            "authority",
            "dob",
            "address",
            "aadhaar",
            "uidai",
            "scanned",
        )
        for raw_line in text.splitlines():
            line = re.sub(r"[^A-Za-z .]", " ", raw_line).strip()
            line = re.sub(r"\s+", " ", line)
            if len(line.split()) < 2:
                continue
            if any(fragment in line.lower() for fragment in ignored_fragments):
                continue
            return line
        return None

    def _extract_address(self, text: str) -> str | None:
        match = re.search(r"address\s*[:\-]?\s*(.+)", text, re.IGNORECASE | re.DOTALL)
        if match is None:
            return None

        address = re.split(r"(?:www\.|help@|uidai|scanned)", match.group(1), maxsplit=1, flags=re.IGNORECASE)[0]
        address = re.sub(r"\s+", " ", address).strip(" ,.;")
        return address or None

    def _calculate_confidence(self, *, fields: dict[str, str], errors: list[str], warnings: list[str]) -> float:
        weights = {
            "aadhaar_number": 0.45,
            "name": 0.25,
            "dob": 0.2,
            "address": 0.1,
        }
        confidence = sum(weight for field, weight in weights.items() if field in fields)
        confidence -= len(errors) * 0.15
        confidence -= len(warnings) * 0.03
        return round(max(min(confidence, 0.99), 0.0), 2)
