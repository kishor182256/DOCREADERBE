from dataclasses import dataclass, field


@dataclass(frozen=True)
class BoundingBox:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class OCRWord:
    text: str
    confidence: float


@dataclass(frozen=True)
class TextBlock:
    text: str
    bounding_box: BoundingBox
    confidence: float
    page_number: int


@dataclass(frozen=True)
class OCRResult:
    document_id: str
    page_number: int
    text: str
    confidence: float
    processing_time: float
    words: list[OCRWord] = field(default_factory=list)
    text_blocks: list[TextBlock] = field(default_factory=list)
