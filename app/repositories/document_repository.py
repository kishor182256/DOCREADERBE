from typing import Optional

from sqlalchemy.orm import Session

from app.models.document import Document


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, *, title: str, file_name: str, content_type: str, storage_path: str) -> Document:
        document = Document(
            title=title,
            file_name=file_name,
            content_type=content_type,
            storage_path=storage_path,
        )
        self.session.add(document)
        self.session.commit()
        self.session.refresh(document)
        return document

    def get_by_id(self, document_id: int) -> Optional[Document]:
        return self.session.query(Document).filter(Document.id == document_id).first()

    def list_all(self) -> list[Document]:
        return self.session.query(Document).all()
