from datetime import datetime

from typing import Any

from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    document_id: str
    status: str
    filename: str
    size: int
    content_type: str
    checksum: str
    document_type: str | None = None
    classification_confidence: float | None = None
    classification_json: dict[str, Any] | None = None
    extraction_confidence: float | None = None
    structured_data_json: dict[str, Any] | None = None
    created_at: datetime


class DocumentResponse(DocumentUploadResponse):
    updated_at: datetime


class BatchDocumentUploadItemResponse(BaseModel):
    filename: str
    success: bool
    document: DocumentUploadResponse | None = None
    error: str | None = None


class BatchDocumentUploadResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    results: list[BatchDocumentUploadItemResponse]


class OcrResultResponse(BaseModel):
    page_number: int
    text: str
    confidence: float
    processing_time: float
    ocr_engine: str
    result_json: dict[str, Any]
    created_at: datetime


class BoundingBoxResponse(BaseModel):
    x: int
    y: int
    width: int
    height: int


class TextBlockResponse(BaseModel):
    text: str
    bounding_box: BoundingBoxResponse
    confidence: float
    page_number: int


class DocumentUploadRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
