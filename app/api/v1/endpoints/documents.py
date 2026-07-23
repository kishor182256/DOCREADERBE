from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.schemas.document import DocumentUploadRequest, DocumentUploadResponse
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
    title: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> DocumentUploadResponse:
    service = DocumentService(db)
    payload = service.upload_document(title=title, file=file)
    return DocumentUploadResponse(**payload)
