import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


def parse_json(value: str | None) -> dict[str, object]:
    if not value:
        return {}
    return json.loads(value)


def main() -> None:
    connection = sqlite3.connect("app.db")
    connection.row_factory = sqlite3.Row
    output_dir = Path("structured_outputs")
    output_dir.mkdir(parents=True, exist_ok=True)

    documents = connection.execute(
        """
        SELECT document_id, document_type, extraction_confidence, structured_data_json
        FROM documents
        WHERE document_id IS NOT NULL
        """
    ).fetchall()

    for document in documents:
        document_id = document["document_id"]
        existing_payload = parse_json(document["structured_data_json"])
        ocr_rows = connection.execute(
            """
            SELECT page_number, text, confidence, processing_time
            FROM ocr_results
            WHERE document_id = ?
            ORDER BY page_number
            """,
            (document_id,),
        ).fetchall()
        text_blocks = connection.execute(
            """
            SELECT page_number, text, confidence, x, y, width, height
            FROM ocr_text_blocks
            WHERE document_id = ?
            ORDER BY page_number, y, x
            """,
            (document_id,),
        ).fetchall()

        if not existing_payload and not ocr_rows and not text_blocks:
            continue

        block_counts: dict[int, int] = {}
        for block in text_blocks:
            page_number = int(block["page_number"])
            block_counts[page_number] = block_counts.get(page_number, 0) + 1

        output_path = output_dir / f"{document_id}.json"
        payload = {
            "document_id": document_id,
            "document_type": existing_payload.get("document_type") or document["document_type"] or "UNKNOWN",
            "confidence": existing_payload.get("confidence") or document["extraction_confidence"] or 0.0,
            "fields": existing_payload.get("fields") or {},
            "raw_text": "\n\n".join(row["text"] for row in ocr_rows if row["text"]),
            "pages": [
                {
                    "page_number": row["page_number"],
                    "text": row["text"],
                    "confidence": row["confidence"],
                    "processing_time": row["processing_time"],
                    "text_block_count": block_counts.get(int(row["page_number"]), 0),
                }
                for row in ocr_rows
            ],
            "text_blocks": [
                {
                    "page_number": block["page_number"],
                    "text": block["text"],
                    "confidence": block["confidence"],
                    "bounding_box": {
                        "x": block["x"],
                        "y": block["y"],
                        "width": block["width"],
                        "height": block["height"],
                    },
                }
                for block in text_blocks
            ],
            "warnings": existing_payload.get("warnings") or [],
            "errors": existing_payload.get("errors") or [],
            "extractor": existing_payload.get("extractor") or "none",
            "created_at": existing_payload.get("created_at") or datetime.now(UTC).isoformat(),
            "output_file": str(output_path),
        }

        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        connection.execute(
            "UPDATE documents SET structured_data_json = ?, updated_at = ? WHERE document_id = ?",
            (json.dumps(payload, ensure_ascii=False), datetime.now(UTC).isoformat(), document_id),
        )
        print(f"Regenerated {output_path}")

    connection.commit()
    connection.close()


if __name__ == "__main__":
    main()
