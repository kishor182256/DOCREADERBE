import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import SessionLocal
from app.schemas.document import (
    BatchDocumentUploadItemResponse,
    BatchDocumentUploadResponse,
    DocumentResponse,
    DocumentUploadResponse,
    OcrResultResponse,
    TextBlockResponse,
)
from app.services.document_service import DocumentService

router = APIRouter()


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_document(
    title: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> DocumentUploadResponse:
    service = DocumentService(db)
    payload = service.upload_document(title=title, file=file)
    return DocumentUploadResponse(**payload)


@router.post("/upload-batch", response_model=BatchDocumentUploadResponse, status_code=status.HTTP_207_MULTI_STATUS)
def upload_documents_batch(
    files: list[UploadFile] = File(...),
) -> BatchDocumentUploadResponse:
    upload_inputs: list[dict[str, object]] = []
    results: list[BatchDocumentUploadItemResponse] = []
    seen_hashes: dict[str, str] = {}

    for file in files:
        file_bytes = file.file.read()
        content_hash = hashlib.sha256(file_bytes).hexdigest()
        file_name = file.filename or "uploaded_file"
        if content_hash in seen_hashes:
            results.append(
                BatchDocumentUploadItemResponse(
                    filename=file_name,
                    success=False,
                    error=f"Duplicate file in this batch. Matches {seen_hashes[content_hash]}.",
                )
            )
            continue

        seen_hashes[content_hash] = file_name
        upload_inputs.append(
            {
                "title": file.filename.rsplit(".", 1)[0] if file.filename else None,
                "file_name": file_name,
                "content_type": file.content_type or "application/octet-stream",
                "file_bytes": file_bytes,
            }
        )

    if not upload_inputs:
        return BatchDocumentUploadResponse(
            total=len(results),
            succeeded=0,
            failed=len(results),
            results=results,
        )

    max_workers = max(1, min(settings.BATCH_UPLOAD_MAX_WORKERS, len(upload_inputs)))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_input = {
            executor.submit(_upload_single_batch_file, upload_input): upload_input
            for upload_input in upload_inputs
        }
        for future in as_completed(future_to_input):
            upload_input = future_to_input[future]
            file_name = str(upload_input["file_name"])
            try:
                document = DocumentUploadResponse(**future.result())
                results.append(BatchDocumentUploadItemResponse(filename=file_name, success=True, document=document))
            except HTTPException as exc:
                results.append(BatchDocumentUploadItemResponse(filename=file_name, success=False, error=str(exc.detail)))
            except Exception as exc:
                results.append(BatchDocumentUploadItemResponse(filename=file_name, success=False, error=str(exc)))

    return BatchDocumentUploadResponse(
        total=len(results),
        succeeded=sum(1 for result in results if result.success),
        failed=sum(1 for result in results if not result.success),
        results=results,
    )


def _upload_single_batch_file(upload_input: dict[str, object]) -> dict[str, object]:
    db = SessionLocal()
    try:
        service = DocumentService(db)
        return service.upload_document_bytes(
            title=upload_input["title"] if isinstance(upload_input["title"], str) else None,
            file_name=str(upload_input["file_name"]),
            content_type=str(upload_input["content_type"]),
            file_bytes=upload_input["file_bytes"] if isinstance(upload_input["file_bytes"], bytes) else b"",
        )
    finally:
        db.close()


@router.get("", response_model=list[DocumentResponse])
def list_documents(db: Session = Depends(get_db)) -> list[DocumentResponse]:
    service = DocumentService(db)
    return [DocumentResponse(**document) for document in service.list_documents()]


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str, db: Session = Depends(get_db)) -> DocumentResponse:
    service = DocumentService(db)
    return DocumentResponse(**service.get_document(document_id))


@router.get("/{document_id}/ocr-results", response_model=list[OcrResultResponse])
def list_ocr_results(document_id: str, db: Session = Depends(get_db)) -> list[OcrResultResponse]:
    service = DocumentService(db)
    return [OcrResultResponse(**result) for result in service.list_ocr_results(document_id)]


@router.get("/{document_id}/text-blocks", response_model=list[TextBlockResponse])
def list_text_blocks(document_id: str, db: Session = Depends(get_db)) -> list[TextBlockResponse]:
    service = DocumentService(db)
    return [TextBlockResponse(**text_block) for text_block in service.list_text_blocks(document_id)]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: str, db: Session = Depends(get_db)) -> Response:
    service = DocumentService(db)
    service.delete_document(document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
