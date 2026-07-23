from dataclasses import dataclass, field


@dataclass(frozen=True)
class DocumentClassificationResult:
    document_type: str
    confidence: float
    matched_signals: list[str] = field(default_factory=list)
    all_scores: dict[str, float] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    raw_document_type: str | None = None
