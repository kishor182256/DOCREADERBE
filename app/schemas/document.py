from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    id: int
    title: str
    file_name: str
    content_type: str
    storage_path: str


class DocumentUploadRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
