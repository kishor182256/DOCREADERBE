from dataclasses import dataclass, field


@dataclass(frozen=True)
class OCRWord:
    text: str
    confidence: float


@dataclass(frozen=True)
class OCRResult:
    document_id: str
    page_number: int
    text: str
    confidence: float
    processing_time: float
    words: list[OCRWord] = field(default_factory=list)
