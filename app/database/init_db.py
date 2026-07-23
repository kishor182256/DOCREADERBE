import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text

from app.database.base import Base
from app.database.session import engine
from app.models.document import Document
from app.models.ocr_result import OcrResult


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    migrate_documents_table_for_phase_2()
    migrate_ocr_results_table_for_json_payload()


def migrate_documents_table_for_phase_2() -> None:
    if engine.url.get_backend_name() != "sqlite":
        return

    with engine.begin() as connection:
        existing_columns = {
            row[1] for row in connection.execute(text("PRAGMA table_info(documents)")).fetchall()
        }
        required_columns = {
            "document_id": "TEXT",
            "original_name": "TEXT",
            "stored_name": "TEXT",
            "mime_type": "TEXT",
            "extension": "TEXT",
            "size": "INTEGER",
            "status": "TEXT",
            "checksum": "TEXT",
            "document_type": "TEXT",
            "classification_confidence": "REAL",
            "classification_json": "TEXT",
            "extraction_confidence": "REAL",
            "structured_data_json": "TEXT",
            "created_at": "DATETIME",
            "updated_at": "DATETIME",
        }

        for column_name, column_type in required_columns.items():
            if column_name not in existing_columns:
                connection.execute(text(f"ALTER TABLE documents ADD COLUMN {column_name} {column_type}"))

        rows = connection.execute(
            text(
                """
                SELECT id, title, file_name, content_type, storage_path, document_id, checksum
                FROM documents
                WHERE document_id IS NULL
                   OR original_name IS NULL
                   OR stored_name IS NULL
                   OR mime_type IS NULL
                   OR extension IS NULL
                   OR size IS NULL
                   OR status IS NULL
                   OR checksum IS NULL
                   OR created_at IS NULL
                   OR updated_at IS NULL
                """
            )
        ).mappings().all()

        now = datetime.now(UTC).replace(microsecond=0).isoformat()
        for row in rows:
            file_name = row["file_name"] or "uploaded_document"
            storage_path = Path(row["storage_path"] or "")
            stored_path_exists = storage_path.exists()
            file_size = storage_path.stat().st_size if stored_path_exists else 0
            if stored_path_exists:
                checksum = hashlib.sha256(storage_path.read_bytes()).hexdigest()
            else:
                checksum = row["checksum"] or uuid4().hex + uuid4().hex

            connection.execute(
                text(
                    """
                    UPDATE documents
                    SET document_id = COALESCE(document_id, :document_id),
                        original_name = COALESCE(original_name, :original_name),
                        stored_name = COALESCE(stored_name, :stored_name),
                        mime_type = COALESCE(mime_type, :mime_type),
                        extension = COALESCE(extension, :extension),
                        size = COALESCE(size, :size),
                        status = COALESCE(status, :status),
                        checksum = COALESCE(checksum, :checksum),
                        created_at = COALESCE(created_at, :created_at),
                        updated_at = COALESCE(updated_at, :updated_at)
                    WHERE id = :id
                    """
                ),
                {
                    "id": row["id"],
                    "document_id": row["document_id"] or uuid4().hex,
                    "original_name": file_name,
                    "stored_name": storage_path.name or file_name,
                    "mime_type": row["content_type"] or "application/octet-stream",
                    "extension": Path(file_name).suffix.lstrip(".").lower(),
                    "size": file_size,
                    "status": "UPLOADED",
                    "checksum": checksum,
                    "created_at": now,
                    "updated_at": now,
                },
            )


def migrate_ocr_results_table_for_json_payload() -> None:
    if engine.url.get_backend_name() != "sqlite":
        return

    with engine.begin() as connection:
        table_exists = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'ocr_results'")
        ).fetchone()
        if table_exists is None:
            return

        existing_columns = {
            row[1] for row in connection.execute(text("PRAGMA table_info(ocr_results)")).fetchall()
        }
        if "result_json" not in existing_columns:
            connection.execute(text("ALTER TABLE ocr_results ADD COLUMN result_json TEXT"))

        rows = connection.execute(
            text(
                """
                SELECT id, document_id, page_number, text, confidence, processing_time, ocr_engine, created_at
                FROM ocr_results
                WHERE result_json IS NULL
                """
            )
        ).mappings().all()

        for row in rows:
            payload = {
                "document_id": row["document_id"],
                "page_number": row["page_number"],
                "text": row["text"],
                "confidence": row["confidence"],
                "processing_time": row["processing_time"],
                "ocr_engine": row["ocr_engine"],
                "created_at": row["created_at"],
                "words": [],
            }
            connection.execute(
                text("UPDATE ocr_results SET result_json = :result_json WHERE id = :id"),
                {"id": row["id"], "result_json": json.dumps(payload, ensure_ascii=False)},
            )
