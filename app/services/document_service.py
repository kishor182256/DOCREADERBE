import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document
from app.repositories.document_repository import DocumentRepository
from app.repositories.ocr_result_repository import OcrResultRepository
from app.services.document_processing_service import DocumentProcessingService


logger = logging.getLogger(__name__)


SUPPORTED_FILE_TYPES: dict[str, set[str]] = {
    ".pdf": {"application/pdf"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".tif": {"image/tiff"},
    ".tiff": {"image/tiff"},
    ".bmp": {"image/bmp", "image/x-ms-bmp"},
}

DOCUMENT_STATUS_UPLOADED = "UPLOADED"


class DocumentService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = DocumentRepository(session)
        self.ocr_result_repository = OcrResultRepository(session)

    def _hash_bytes(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def _validate_file(self, *, file_name: str, content_type: str, file_bytes: bytes) -> str:
        extension = Path(file_name).suffix.lower()
        if not file_bytes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file is not allowed.")

        if len(file_bytes) > settings.MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File is larger than 20 MB.")

        allowed_mime_types = SUPPORTED_FILE_TYPES.get(extension)
        if allowed_mime_types is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file extension.")

        if content_type not in allowed_mime_types:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file MIME type.")

        if not self._has_valid_magic_bytes(extension, file_bytes):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File content does not match the declared type.")

        return extension

    def _has_valid_magic_bytes(self, extension: str, file_bytes: bytes) -> bool:
        if extension == ".pdf":
            return file_bytes.startswith(b"%PDF")
        if extension == ".png":
            return file_bytes.startswith(b"\x89PNG\r\n\x1a\n")
        if extension in {".jpg", ".jpeg"}:
            return file_bytes.startswith(b"\xff\xd8\xff")
        if extension in {".tif", ".tiff"}:
            return file_bytes.startswith((b"II*\x00", b"MM\x00*"))
        if extension == ".bmp":
            return file_bytes.startswith(b"BM")
        return False

    def _dated_upload_dir(self, now: datetime) -> Path:
        return Path(settings.UPLOAD_DIR) / f"{now.year:04d}" / f"{now.month:02d}" / f"{now.day:02d}"

    def _to_upload_response(self, document: Document) -> dict[str, object]:
        return {
            "document_id": document.document_id,
            "status": document.status,
            "filename": document.original_name,
            "size": document.size,
            "content_type": document.mime_type,
            "checksum": document.checksum,
            "document_type": document.document_type,
            "classification_confidence": document.classification_confidence,
            "classification_json": json.loads(document.classification_json) if document.classification_json else None,
            "extraction_confidence": document.extraction_confidence,
            "structured_data_json": json.loads(document.structured_data_json) if document.structured_data_json else None,
            "created_at": document.created_at,
            "updated_at": document.updated_at,
        }

    def upload_document(self, *, title: str | None, file: UploadFile) -> dict[str, object]:
        logger.info("Upload started filename=%s content_type=%s", file.filename, file.content_type)

        file_name = Path(file.filename or "uploaded_file").name
        file_bytes = file.file.read()
        content_type = file.content_type or "application/octet-stream"
        extension = self._validate_file(file_name=file_name, content_type=content_type, file_bytes=file_bytes)
        content_hash = self._hash_bytes(file_bytes)

        duplicate_document = self.repository.get_by_checksum(content_hash)
        if duplicate_document is not None:
            duplicate_storage_path = Path(duplicate_document.storage_path)
            if not duplicate_storage_path.exists():
                logger.warning(
                    "Removing stale duplicate metadata document_id=%s missing_path=%s",
                    duplicate_document.document_id,
                    duplicate_storage_path,
                )
                self.ocr_result_repository.delete_by_document_id(duplicate_document.document_id)
                self.repository.delete(duplicate_document)
            else:
                logger.info("Upload rejected duplicate filename=%s document_id=%s", file_name, duplicate_document.document_id)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Already uploaded. Existing document id: {duplicate_document.document_id}.",
                )

        now = datetime.now(UTC)
        upload_dir = self._dated_upload_dir(now)
        upload_dir.mkdir(parents=True, exist_ok=True)

        public_document_id = uuid4().hex
        stored_name = f"{public_document_id}{extension}"
        storage_path = str(upload_dir / stored_name)

        try:
            with open(storage_path, "wb") as buffer:
                buffer.write(file_bytes)
        except OSError as exc:
            logger.exception("Upload failed while saving filename=%s", file_name)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Storage failure.") from exc

        document = self.repository.create(
            document_id=public_document_id,
            title=title or Path(file_name).stem,
            original_name=file_name,
            stored_name=stored_name,
            mime_type=content_type,
            extension=extension.lstrip("."),
            size=len(file_bytes),
            status=DOCUMENT_STATUS_UPLOADED,
            checksum=content_hash,
            storage_path=storage_path,
            created_at=now,
            updated_at=now,
        )
        logger.info("Upload completed document_id=%s filename=%s size=%s", document.document_id, document.original_name, document.size)

        processed_document = DocumentProcessingService(self.session).process(document.document_id)

        return self._to_upload_response(processed_document)

    def list_documents(self) -> list[dict[str, object]]:
        return [self._to_upload_response(document) for document in self.repository.list_all()]

    def get_document(self, document_id: str) -> dict[str, object]:
        document = self.repository.get_by_document_id(document_id)
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
        return self._to_upload_response(document)

    def list_ocr_results(self, document_id: str) -> list[dict[str, object]]:
        document = self.repository.get_by_document_id(document_id)
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

        return [
            {
                "page_number": result.page_number,
                "text": result.text,
                "confidence": result.confidence,
                "processing_time": result.processing_time,
                "ocr_engine": result.ocr_engine,
                "result_json": json.loads(result.result_json),
                "created_at": result.created_at,
            }
            for result in self.ocr_result_repository.list_by_document_id(document_id)
        ]

    def delete_document(self, document_id: str) -> None:
        document = self.repository.get_by_document_id(document_id)
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

        storage_path = Path(document.storage_path)
        self.ocr_result_repository.delete_by_document_id(document.document_id)
        self.repository.delete(document)
        if storage_path.exists():
            try:
                storage_path.unlink()
            except OSError:
                logger.warning("Could not delete stored file path=%s", storage_path)
        else:
            logger.warning("Stored file already missing during delete document_id=%s path=%s", document.document_id, storage_path)
