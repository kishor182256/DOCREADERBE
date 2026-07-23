from abc import ABC, abstractmethod

from app.services.ocr.models import OCRResult
from app.services.preprocessing import PreprocessedPage


class OCRService(ABC):
    @abstractmethod
    def extract_text(self, pages: list[PreprocessedPage]) -> list[OCRResult]:
        raise NotImplementedError
