from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.document import Document


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        document_id: str,
        title: str,
        original_name: str,
        stored_name: str,
        mime_type: str,
        extension: str,
        size: int,
        status: str,
        checksum: str,
        storage_path: str,
        created_at: datetime,
        updated_at: datetime,
    ) -> Document:
        document = Document(
            document_id=document_id,
            title=title,
            original_name=original_name,
            stored_name=stored_name,
            mime_type=mime_type,
            extension=extension,
            size=size,
            status=status,
            checksum=checksum,
            storage_path=storage_path,
            created_at=created_at,
            updated_at=updated_at,
            file_name=original_name,
            content_type=mime_type,
        )
        self.session.add(document)
        self.session.commit()
        self.session.refresh(document)
        return document

    def get_by_id(self, document_id: int) -> Optional[Document]:
        return self.session.query(Document).filter(Document.id == document_id).first()

    def get_by_document_id(self, document_id: str) -> Optional[Document]:
        return self.session.query(Document).filter(Document.document_id == document_id).first()

    def get_by_checksum(self, checksum: str) -> Optional[Document]:
        return self.session.query(Document).filter(Document.checksum == checksum).first()

    def list_all(self) -> list[Document]:
        return self.session.query(Document).order_by(Document.created_at.desc()).all()

    def delete(self, document: Document) -> None:
        self.session.delete(document)
        self.session.commit()
