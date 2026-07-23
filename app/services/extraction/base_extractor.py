from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from app.services.extraction.models import ExtractionResult

if TYPE_CHECKING:
    from app.services.processing_context import ProcessingContext


class BaseExtractor(ABC):
    document_type: str

    @abstractmethod
    def extract(self, context: ProcessingContext) -> ExtractionResult:
        raise NotImplementedError
