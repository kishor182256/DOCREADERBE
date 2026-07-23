import logging
import time
from pathlib import Path

from fastapi import HTTPException, status

from app.core.config import settings
from app.services.ocr.models import OCRResult, OCRWord
from app.services.ocr.ocr_service import OCRService
from app.services.preprocessing import PreprocessedPage


logger = logging.getLogger(__name__)


class TesseractOCRService(OCRService):
    def extract_text(self, pages: list[PreprocessedPage]) -> list[OCRResult]:
        try:
            import pytesseract
            from pytesseract import Output, TesseractError, TesseractNotFoundError
        except ImportError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OCR dependencies are not installed. Run pip install -r requirements.txt.",
            ) from exc

        if settings.TESSERACT_CMD:
            tesseract_path = Path(settings.TESSERACT_CMD)
            if not tesseract_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Tesseract executable was not found at configured path: {settings.TESSERACT_CMD}",
                )
            pytesseract.pytesseract.tesseract_cmd = str(tesseract_path)

        results: list[OCRResult] = []
        for page in pages:
            try:
                results.append(self._extract_page_text(page, pytesseract, Output))
            except TesseractNotFoundError as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Tesseract executable was not found. Install Tesseract OCR and ensure it is on PATH.",
                ) from exc
            except TesseractError as exc:
                logger.exception("Tesseract OCR failed document_id=%s page=%s", page.document_id, page.page_number)
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="OCR processing failed.") from exc

        return results

    def _extract_page_text(self, page: PreprocessedPage, pytesseract_module: object, output_format: object) -> OCRResult:
        start_time = time.perf_counter()
        ocr_data = pytesseract_module.image_to_data(page.image, output_type=output_format.DICT)
        processing_time = time.perf_counter() - start_time

        words = self._extract_words(ocr_data)
        text = " ".join(word.text for word in words)
        average_confidence = self._average_confidence(words)

        logger.info(
            "OCR completed document_id=%s page=%s confidence=%.2f processing_time=%.3fs",
            page.document_id,
            page.page_number,
            average_confidence,
            processing_time,
        )
        if text:
            logger.info("OCR extracted text document_id=%s page=%s text=%s", page.document_id, page.page_number, text)
        else:
            logger.info("OCR extracted no text document_id=%s page=%s", page.document_id, page.page_number)

        return OCRResult(
            document_id=page.document_id,
            page_number=page.page_number,
            text=text,
            confidence=average_confidence,
            processing_time=processing_time,
            words=words,
        )

    def _extract_words(self, ocr_data: dict[str, list[object]]) -> list[OCRWord]:
        words: list[OCRWord] = []
        raw_texts = ocr_data.get("text", [])
        raw_confidences = ocr_data.get("conf", [])

        for raw_text, raw_confidence in zip(raw_texts, raw_confidences):
            text = str(raw_text).strip()
            confidence = self._parse_confidence(raw_confidence)
            if not text or confidence < 0:
                continue
            words.append(OCRWord(text=text, confidence=confidence))

        return words

    def _parse_confidence(self, value: object) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return -1.0

    def _average_confidence(self, words: list[OCRWord]) -> float:
        if not words:
            return 0.0
        return sum(word.confidence for word in words) / len(words)
