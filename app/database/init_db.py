import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text

from app.database.base import Base
from app.database.session import engine
from app.models.document import Document


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    migrate_documents_table_for_phase_2()


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
