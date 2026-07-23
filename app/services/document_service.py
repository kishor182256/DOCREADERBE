import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.repositories.document_repository import DocumentRepository
from app.core.config import settings


class DocumentService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = DocumentRepository(session)

    def _hash_bytes(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def _find_duplicate_document_id(self, content_hash: str) -> int | None:
        for document in self.repository.list_all():
            storage_path = Path(document.storage_path)
            if not storage_path.exists() or not storage_path.is_file():
                continue
            try:
                existing_hash = self._hash_bytes(storage_path.read_bytes())
            except OSError:
                continue
            if existing_hash == content_hash:
                return document.id
        return None

    def upload_document(self, *, title: str, file: UploadFile) -> dict[str, object]:
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_name = Path(file.filename or "uploaded_file").name
        file_bytes = file.file.read()
        content_hash = self._hash_bytes(file_bytes)

        duplicate_document_id = self._find_duplicate_document_id(content_hash)
        if duplicate_document_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Duplicate document detected. Existing document id: {duplicate_document_id}.",
            )

        stored_name = f"{uuid4().hex}_{file_name}"
        storage_path = str(upload_dir / stored_name)

        with open(storage_path, "wb") as buffer:
            buffer.write(file_bytes)

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
