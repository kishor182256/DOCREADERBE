from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.models.document import Document

if TYPE_CHECKING:
    from app.services.classification.models import DocumentClassificationResult
    from app.services.extraction.models import ExtractionResult
    from app.services.ocr import OCRResult
    from app.services.preprocessing import PreprocessedPage


@dataclass
class ProcessingContext:
    document: Document
    pages: list[PreprocessedPage] = field(default_factory=list)
    ocr_results: list[OCRResult] = field(default_factory=list)
    classification: DocumentClassificationResult | None = None
    extraction_result: ExtractionResult | None = None
    document_type: str | None = None
    entities: list[dict[str, Any]] = field(default_factory=list)
    chunks: list[str] = field(default_factory=list)
    embeddings: list[Any] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
