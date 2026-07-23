from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.extraction.base_extractor import BaseExtractor
from app.services.extraction.models import ExtractionResult

if TYPE_CHECKING:
    from app.services.processing_context import ProcessingContext


class NullExtractor(BaseExtractor):
    document_type = "UNKNOWN"

    def extract(self, context: ProcessingContext) -> ExtractionResult:
        document_type = context.document_type or "UNKNOWN"
        return ExtractionResult(
            document_type=document_type,
            fields={},
            confidence=0.0,
            warnings=[f"No extractor implemented for document type {document_type}."],
            extractor="none",
        )
