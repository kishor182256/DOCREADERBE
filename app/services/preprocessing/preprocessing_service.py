import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from fastapi import HTTPException, status

from app.models.document import Document


logger = logging.getLogger(__name__)

SourceType = Literal["pdf", "image"]


@dataclass(frozen=True)
class PreprocessedPage:
    document_id: str
    page_number: int
    source_type: SourceType
    image_format: str
    width: int
    height: int
    color_mode: str
    image: Any


class PreprocessingService:
    def preprocess(self, document: Document) -> list[PreprocessedPage]:
        file_path = Path(document.storage_path)
        if not file_path.exists() or not file_path.is_file():
            logger.error("Preprocessing failed because stored file is missing document_id=%s path=%s", document.document_id, file_path)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Stored document file was not found.")

        extension = document.extension.lower()
        logger.info("Preprocessing started document_id=%s extension=%s", document.document_id, extension)

        if extension == "pdf":
            pages = self._preprocess_pdf(document, file_path)
        else:
            pages = [self._preprocess_image(document, file_path)]

        logger.info("Preprocessing completed document_id=%s pages=%s", document.document_id, len(pages))
        return pages

    def _preprocess_pdf(self, document: Document, file_path: Path) -> list[PreprocessedPage]:
        try:
            import fitz
            from PIL import Image
        except ImportError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="PDF preprocessing dependencies are not installed. Run pip install -r requirements.txt.",
            ) from exc

        pages: list[PreprocessedPage] = []
        try:
            with fitz.open(file_path) as pdf_document:
                for page_index in range(pdf_document.page_count):
                    pdf_page = pdf_document.load_page(page_index)
                    pixmap = pdf_page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples).convert("RGB")
                    pages.append(
                        PreprocessedPage(
                            document_id=document.document_id,
                            page_number=page_index + 1,
                            source_type="pdf",
                            image_format="RGB",
                            width=image.width,
                            height=image.height,
                            color_mode=image.mode,
                            image=image,
                        )
                    )
        except Exception as exc:
            logger.exception("PDF preprocessing failed document_id=%s", document.document_id)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or unreadable PDF.") from exc

        if not pages:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PDF has no readable pages.")

        return pages

    def _preprocess_image(self, document: Document, file_path: Path) -> PreprocessedPage:
        try:
            from PIL import Image, UnidentifiedImageError
        except ImportError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Image preprocessing dependencies are not installed. Run pip install -r requirements.txt.",
            ) from exc

        try:
            with Image.open(file_path) as image_file:
                image = image_file.convert("RGB").copy()
        except (OSError, UnidentifiedImageError) as exc:
            logger.exception("Image preprocessing failed document_id=%s", document.document_id)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or unreadable image.") from exc

        return PreprocessedPage(
            document_id=document.document_id,
            page_number=1,
            source_type="image",
            image_format="RGB",
            width=image.width,
            height=image.height,
            color_mode=image.mode,
            image=image,
        )
