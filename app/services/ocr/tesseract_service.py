import logging
import time
from pathlib import Path

from fastapi import HTTPException, status

from app.core.config import settings
from app.services.ocr.models import BoundingBox, OCRResult, OCRWord, TextBlock
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
        text_blocks = self._extract_text_blocks(ocr_data, page_number=page.page_number)
        text = "\n".join(block.text for block in text_blocks) if text_blocks else " ".join(word.text for word in words)
        average_confidence = self._average_confidence(text_blocks) if text_blocks else self._average_confidence(words)

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
            text_blocks=text_blocks,
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

    def _extract_text_blocks(self, ocr_data: dict[str, list[object]], *, page_number: int) -> list[TextBlock]:
        grouped_words: dict[tuple[int, int, int], list[dict[str, object]]] = {}
        raw_texts = ocr_data.get("text", [])
        raw_confidences = ocr_data.get("conf", [])
        raw_lefts = ocr_data.get("left", [])
        raw_tops = ocr_data.get("top", [])
        raw_widths = ocr_data.get("width", [])
        raw_heights = ocr_data.get("height", [])
        raw_blocks = ocr_data.get("block_num", [])
        raw_paragraphs = ocr_data.get("par_num", [])
        raw_lines = ocr_data.get("line_num", [])

        for index, raw_text in enumerate(raw_texts):
            text = str(raw_text).strip()
            confidence = self._parse_confidence(raw_confidences[index] if index < len(raw_confidences) else -1)
            if not text or confidence < 0:
                continue

            key = (
                self._parse_int(raw_blocks[index] if index < len(raw_blocks) else 0),
                self._parse_int(raw_paragraphs[index] if index < len(raw_paragraphs) else 0),
                self._parse_int(raw_lines[index] if index < len(raw_lines) else 0),
            )
            grouped_words.setdefault(key, []).append(
                {
                    "text": text,
                    "confidence": confidence,
                    "x": self._parse_int(raw_lefts[index] if index < len(raw_lefts) else 0),
                    "y": self._parse_int(raw_tops[index] if index < len(raw_tops) else 0),
                    "width": self._parse_int(raw_widths[index] if index < len(raw_widths) else 0),
                    "height": self._parse_int(raw_heights[index] if index < len(raw_heights) else 0),
                }
            )

        text_blocks: list[TextBlock] = []
        for _, words in sorted(grouped_words.items()):
            x_min = min(int(word["x"]) for word in words)
            y_min = min(int(word["y"]) for word in words)
            x_max = max(int(word["x"]) + int(word["width"]) for word in words)
            y_max = max(int(word["y"]) + int(word["height"]) for word in words)
            confidence = sum(float(word["confidence"]) for word in words) / len(words)
            text_blocks.append(
                TextBlock(
                    text=" ".join(str(word["text"]) for word in words),
                    bounding_box=BoundingBox(
                        x=x_min,
                        y=y_min,
                        width=x_max - x_min,
                        height=y_max - y_min,
                    ),
                    confidence=confidence,
                    page_number=page_number,
                )
            )

        return text_blocks

    def _parse_confidence(self, value: object) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return -1.0

    def _parse_int(self, value: object) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _average_confidence(self, items: list[OCRWord] | list[TextBlock]) -> float:
        if not items:
            return 0.0
        return sum(item.confidence for item in items) / len(items)
