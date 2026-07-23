import json
import logging
from pathlib import Path
from typing import Any

from app.core.config import settings


logger = logging.getLogger(__name__)


class StructuredOutputExportService:
    def output_path(self, document_id: str) -> Path:
        return Path(settings.STRUCTURED_OUTPUT_DIR) / f"{document_id}.json"

    def export(self, *, document_id: str, payload: dict[str, Any]) -> Path:
        output_dir = Path(settings.STRUCTURED_OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = self.output_path(document_id)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        logger.info("Structured JSON exported document_id=%s path=%s", document_id, output_path)
        return output_path

    def delete(self, document_id: str) -> None:
        output_path = self.output_path(document_id)
        if not output_path.exists():
            logger.warning("Structured JSON already missing document_id=%s path=%s", document_id, output_path)
            return

        try:
            output_path.unlink()
            logger.info("Structured JSON deleted document_id=%s path=%s", document_id, output_path)
        except OSError:
            logger.warning("Could not delete structured JSON document_id=%s path=%s", document_id, output_path)
