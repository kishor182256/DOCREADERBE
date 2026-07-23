"""Database models package."""

from app.models.document import Document
from app.models.ocr_result import OcrResult

__all__ = ["Document", "OcrResult"]
