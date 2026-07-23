from datetime import datetime

from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    document_id: str
    status: str
    filename: str
    size: int
    content_type: str
    checksum: str
    created_at: datetime


class DocumentResponse(DocumentUploadResponse):
    updated_at: datetime


class DocumentUploadRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
