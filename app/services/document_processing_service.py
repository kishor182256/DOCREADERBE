import logging
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.document import Document
from app.repositories.document_repository import DocumentRepository
from app.repositories.ocr_result_repository import OcrResultRepository
from app.services.classification import DocumentClassificationResult, DocumentClassificationService
from app.services.extraction import ExtractionResult, ExtractorFactory
from app.services.ocr import OCRResult, OCRService, TesseractOCRService
from app.services.preprocessing import PreprocessedPage, PreprocessingService
from app.services.processing_context import ProcessingContext


logger = logging.getLogger(__name__)
DOCUMENT_STATUS_OCR_COMPLETED = "OCR_COMPLETED"
DOCUMENT_STATUS_OCR_FAILED = "OCR_FAILED"
DOCUMENT_STATUS_CLASSIFIED = "CLASSIFIED"
DOCUMENT_STATUS_EXTRACTED = "EXTRACTED"
OCR_ENGINE_TESSERACT = "tesseract"


class DocumentProcessingService:
    def __init__(self, session: Session) -> None:
        self.repository = DocumentRepository(session)
        self.ocr_result_repository = OcrResultRepository(session)
        self.preprocessing_service = PreprocessingService()
        self.ocr_service: OCRService = TesseractOCRService()
        self.classification_service = DocumentClassificationService()
        self.extractor_factory = ExtractorFactory()

    def process(self, document_id: str) -> Document:
        logger.info("Document processing started document_id=%s", document_id)

        document = self.repository.get_by_document_id(document_id)
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

        try:
            context = ProcessingContext(document=document)
            context.pages = self._preprocess(context)
            logger.info("Document processing received preprocessed pages document_id=%s pages=%s", document.document_id, len(context.pages))

            context.ocr_results = self._extract_text(context)
            logger.info("Document processing received OCR results document_id=%s pages=%s", document.document_id, len(context.ocr_results))

            self._persist_ocr_results(context)
            context.document = self.repository.update_status(
                context.document,
                status=DOCUMENT_STATUS_OCR_COMPLETED,
                updated_at=datetime.now(UTC),
            )

            context.classification = self._classify_document(context)
            context.document_type = context.classification.document_type
            context.document = self._persist_classification(context)

            context.extraction_result = self._extract_structured_data(context)
            document = self._persist_structured_data(context)
        except HTTPException:
            self.repository.update_status(document, status=DOCUMENT_STATUS_OCR_FAILED, updated_at=datetime.now(UTC))
            raise

        logger.info("Document processing completed document_id=%s", document.document_id)
        return document

    def _preprocess(self, context: ProcessingContext) -> list[PreprocessedPage]:
        return self.preprocessing_service.preprocess(context.document)

    def _extract_text(self, context: ProcessingContext) -> list[OCRResult]:
        return self.ocr_service.extract_text(context.pages)

    def _persist_ocr_results(self, context: ProcessingContext) -> None:
        saved_results = self.ocr_result_repository.replace_for_document(
            document_id=context.document.document_id,
            ocr_results=context.ocr_results,
            ocr_engine=OCR_ENGINE_TESSERACT,
            created_at=datetime.now(UTC),
        )
        logger.info(
            "OCR results persisted document_id=%s rows=%s",
            context.document.document_id,
            len(saved_results),
        )

    def _classify_document(self, context: ProcessingContext) -> DocumentClassificationResult:
        classification = self.classification_service.classify(context)
        logger.info(
            "Document classified document_id=%s document_type=%s confidence=%.2f",
            context.document.document_id,
            classification.document_type,
            classification.confidence,
        )
        return classification

    def _persist_classification(self, context: ProcessingContext) -> Document:
        classification = context.classification
        if classification is None:
            return context.document

        return self.repository.update_classification(
            context.document,
            document_type=classification.document_type,
            confidence=classification.confidence,
            classification_json={
                "document_id": context.document.document_id,
                "document_type": classification.document_type,
                "confidence": classification.confidence,
                "matched_signals": classification.matched_signals,
                "all_scores": classification.all_scores,
                "reasons": classification.reasons,
                "raw_document_type": classification.raw_document_type,
                "classifier": "rule_based_v1",
                "unknown_threshold": 0.4,
                "created_at": datetime.now(UTC).isoformat(),
            },
            status=DOCUMENT_STATUS_CLASSIFIED,
            updated_at=datetime.now(UTC),
        )

    def _extract_structured_data(self, context: ProcessingContext) -> ExtractionResult:
        extractor = self.extractor_factory.get(context.document_type)
        result = extractor.extract(context)
        logger.info(
            "Structured extraction completed document_id=%s document_type=%s confidence=%.2f extractor=%s fields=%s warnings=%s errors=%s",
            context.document.document_id,
            result.document_type,
            result.confidence,
            result.extractor,
            len(result.fields),
            len(result.warnings),
            len(result.errors),
        )
        return result

    def _persist_structured_data(self, context: ProcessingContext) -> Document:
        extraction = context.extraction_result
        if extraction is None:
            return context.document

        return self.repository.update_structured_data(
            context.document,
            extraction_confidence=extraction.confidence,
            structured_data_json={
                "document_id": context.document.document_id,
                "document_type": extraction.document_type,
                "confidence": extraction.confidence,
                "fields": extraction.fields,
                "warnings": extraction.warnings,
                "errors": extraction.errors,
                "extractor": extraction.extractor,
                "created_at": datetime.now(UTC).isoformat(),
            },
            status=DOCUMENT_STATUS_EXTRACTED,
            updated_at=datetime.now(UTC),
        )
