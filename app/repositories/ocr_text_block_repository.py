from datetime import datetime

from sqlalchemy.orm import Session

from app.models.ocr_text_block import OcrTextBlock
from app.services.ocr import OCRResult


class OcrTextBlockRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def replace_for_document(
        self,
        *,
        document_id: str,
        ocr_results: list[OCRResult],
        created_at: datetime,
    ) -> list[OcrTextBlock]:
        self.delete_by_document_id(document_id, commit=False)

        records = [
            OcrTextBlock(
                document_id=document_id,
                page_number=text_block.page_number,
                text=text_block.text,
                x=text_block.bounding_box.x,
                y=text_block.bounding_box.y,
                width=text_block.bounding_box.width,
                height=text_block.bounding_box.height,
                confidence=text_block.confidence,
                created_at=created_at,
            )
            for result in ocr_results
            for text_block in result.text_blocks
        ]

        self.session.add_all(records)
        self.session.commit()
        for record in records:
            self.session.refresh(record)

        return records

    def list_by_document_id(self, document_id: str) -> list[OcrTextBlock]:
        return (
            self.session.query(OcrTextBlock)
            .filter(OcrTextBlock.document_id == document_id)
            .order_by(OcrTextBlock.page_number.asc(), OcrTextBlock.y.asc(), OcrTextBlock.x.asc())
            .all()
        )

    def delete_by_document_id(self, document_id: str, *, commit: bool = True) -> None:
        self.session.query(OcrTextBlock).filter(OcrTextBlock.document_id == document_id).delete()
        if commit:
            self.session.commit()
