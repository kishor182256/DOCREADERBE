from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.schemas.document import DocumentResponse, DocumentUploadResponse
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


@router.get("", response_model=list[DocumentResponse])
def list_documents(db: Session = Depends(get_db)) -> list[DocumentResponse]:
    service = DocumentService(db)
    return [DocumentResponse(**document) for document in service.list_documents()]


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str, db: Session = Depends(get_db)) -> DocumentResponse:
    service = DocumentService(db)
    return DocumentResponse(**service.get_document(document_id))


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: str, db: Session = Depends(get_db)) -> Response:
    service = DocumentService(db)
    service.delete_document(document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
