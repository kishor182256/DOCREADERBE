from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.services.classification.models import DocumentClassificationResult

if TYPE_CHECKING:
    from app.services.processing_context import ProcessingContext


UNKNOWN_CONFIDENCE_THRESHOLD = 0.4


class DocumentClassificationService:
    def classify(self, context: ProcessingContext) -> DocumentClassificationResult:
        ocr_text = self._normalize_text(" ".join(result.text for result in context.ocr_results))
        candidates = [
            self._score_aadhaar(ocr_text),
            self._score_pan(ocr_text),
            self._score_discharge_summary(ocr_text),
            self._score_prescription(ocr_text),
            self._score_invoice(ocr_text),
        ]
        all_scores = {candidate.document_type: candidate.confidence for candidate in candidates}
        best_candidate = max(candidates, key=lambda candidate: candidate.confidence)

        if best_candidate.confidence < UNKNOWN_CONFIDENCE_THRESHOLD:
            return DocumentClassificationResult(
                document_type="UNKNOWN",
                confidence=round(best_candidate.confidence, 2),
                matched_signals=best_candidate.matched_signals,
                all_scores=all_scores | {"UNKNOWN": round(1 - best_candidate.confidence, 2)},
                reasons=[
                    f"Best candidate {best_candidate.document_type} was below threshold {UNKNOWN_CONFIDENCE_THRESHOLD}.",
                    *best_candidate.reasons,
                ],
                raw_document_type=best_candidate.document_type,
            )

        return DocumentClassificationResult(
            document_type=best_candidate.document_type,
            confidence=best_candidate.confidence,
            matched_signals=best_candidate.matched_signals,
            all_scores=all_scores,
            reasons=best_candidate.reasons,
            raw_document_type=best_candidate.document_type,
        )

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip().lower()

    def _score_aadhaar(self, text: str) -> DocumentClassificationResult:
        signals = self._matched_signals(
            text,
            {
                "unique identification authority": 0.35,
                "uidai": 0.25,
                "aadhaar": 0.25,
                "enrollment": 0.1,
                "dob": 0.05,
            },
        )
        if re.search(r"\b\d{4}\s?\d{4}\s?\d{4}\b", text):
            signals.append(("12-digit identity number", 0.25))
        return self._result("AADHAAR_CARD", signals, max_score=1.0)

    def _score_pan(self, text: str) -> DocumentClassificationResult:
        signals = self._matched_signals(
            text,
            {
                "income tax department": 0.35,
                "permanent account number": 0.35,
                "govt. of india": 0.1,
                "government of india": 0.1,
                "pan": 0.1,
            },
        )
        if re.search(r"\b[a-z]{5}\d{4}[a-z]\b", text):
            signals.append(("pan number pattern", 0.35))
        return self._result("PAN_CARD", signals, max_score=1.0)

    def _score_discharge_summary(self, text: str) -> DocumentClassificationResult:
        signals = self._matched_signals(
            text,
            {
                "discharge summary": 0.4,
                "advice on discharge": 0.2,
                "diagnosis": 0.15,
                "consultant": 0.1,
                "admission": 0.08,
                "discharge": 0.08,
                "doa": 0.08,
                "dod": 0.08,
                "medicine": 0.05,
                "tablet": 0.05,
            },
        )
        return self._result("DISCHARGE_SUMMARY", signals, max_score=0.9)

    def _score_prescription(self, text: str) -> DocumentClassificationResult:
        signals = self._matched_signals(
            text,
            {
                "rx": 0.35,
                "prescription": 0.3,
                "tablet": 0.15,
                "capsule": 0.15,
                "dose": 0.1,
                "follow up": 0.1,
                "doctor": 0.05,
                "hospital": 0.03,
            },
        )
        return self._result("PRESCRIPTION", signals, max_score=0.85)

    def _score_invoice(self, text: str) -> DocumentClassificationResult:
        signals = self._matched_signals(
            text,
            {
                "invoice": 0.35,
                "tax invoice": 0.35,
                "gst": 0.2,
                "amount": 0.1,
                "total": 0.1,
                "tax": 0.08,
                "bill": 0.08,
            },
        )
        return self._result("INVOICE", signals, max_score=0.95)

    def _matched_signals(self, text: str, signals: dict[str, float]) -> list[tuple[str, float]]:
        return [(signal, weight) for signal, weight in signals.items() if signal in text]

    def _result(self, document_type: str, signals: list[tuple[str, float]], *, max_score: float) -> DocumentClassificationResult:
        raw_score = sum(weight for _, weight in signals)
        confidence = min(raw_score / max_score, 0.99) if max_score else 0.0
        matched_signals = [signal for signal, _ in signals]
        return DocumentClassificationResult(
            document_type=document_type,
            confidence=round(confidence, 2),
            matched_signals=matched_signals,
            reasons=[
                f"Matched signal '{signal}' with weight {weight:.2f}."
                for signal, weight in signals
            ],
        )
