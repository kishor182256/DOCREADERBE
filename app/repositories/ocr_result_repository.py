import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.ocr_result import OcrResult
from app.services.ocr import OCRResult


class OcrResultRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def replace_for_document(
        self,
        *,
        document_id: str,
        ocr_results: list[OCRResult],
        ocr_engine: str,
        created_at: datetime,
    ) -> list[OcrResult]:
        self.delete_by_document_id(document_id, commit=False)

        records = [
            OcrResult(
                document_id=document_id,
                page_number=result.page_number,
                text=result.text,
                confidence=result.confidence,
                processing_time=result.processing_time,
                ocr_engine=ocr_engine,
                result_json=self._to_result_json(result=result, ocr_engine=ocr_engine, created_at=created_at),
                created_at=created_at,
            )
            for result in ocr_results
        ]

        self.session.add_all(records)
        self.session.commit()
        for record in records:
            self.session.refresh(record)

        return records

    def list_by_document_id(self, document_id: str) -> list[OcrResult]:
        return (
            self.session.query(OcrResult)
            .filter(OcrResult.document_id == document_id)
            .order_by(OcrResult.page_number.asc())
            .all()
        )

    def delete_by_document_id(self, document_id: str, *, commit: bool = True) -> None:
        self.session.query(OcrResult).filter(OcrResult.document_id == document_id).delete()
        if commit:
            self.session.commit()

    def _to_result_json(self, *, result: OCRResult, ocr_engine: str, created_at: datetime) -> str:
        payload = {
            "document_id": result.document_id,
            "page_number": result.page_number,
            "text": result.text,
            "confidence": result.confidence,
            "processing_time": result.processing_time,
            "ocr_engine": ocr_engine,
            "created_at": created_at.isoformat(),
            "words": [
                {
                    "text": word.text,
                    "confidence": word.confidence,
                }
                for word in result.words
            ],
            "text_blocks": [
                {
                    "text": text_block.text,
                    "bounding_box": {
                        "x": text_block.bounding_box.x,
                        "y": text_block.bounding_box.y,
                        "width": text_block.bounding_box.width,
                        "height": text_block.bounding_box.height,
                    },
                    "confidence": text_block.confidence,
                    "page_number": text_block.page_number,
                }
                for text_block in result.text_blocks
            ],
        }
        return json.dumps(payload, ensure_ascii=False)
