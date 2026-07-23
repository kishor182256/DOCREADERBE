from app.services.extraction.aadhaar_extractor import AadhaarExtractor
from app.services.extraction.base_extractor import BaseExtractor
from app.services.extraction.null_extractor import NullExtractor


class ExtractorFactory:
    def __init__(self) -> None:
        self.extractors: dict[str, BaseExtractor] = {
            "AADHAAR_CARD": AadhaarExtractor(),
        }
        self.null_extractor = NullExtractor()

    def get(self, document_type: str | None) -> BaseExtractor:
        if document_type is None:
            return self.null_extractor
        return self.extractors.get(document_type, self.null_extractor)
