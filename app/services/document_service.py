from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.repositories.document_repository import DocumentRepository


class DocumentService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = DocumentRepository(session)

    def upload_document(self, *, title: str, file: UploadFile) -> dict[str, object]:
        upload_dir = Path("uploads")
        upload_dir.mkdir(exist_ok=True)

        file_name = file.filename or "uploaded_file"
        stored_name = f"{uuid4().hex}_{file_name}"
        storage_path = str(upload_dir / stored_name)

        with open(storage_path, "wb") as buffer:
            buffer.write(file.file.read())

        document = self.repository.create(
            title=title,
            file_name=file_name,
            content_type=file.content_type or "application/octet-stream",
            storage_path=storage_path,
        )

        return {
            "id": document.id,
            "title": document.title,
            "file_name": document.file_name,
            "content_type": document.content_type,
            "storage_path": document.storage_path,
        }
