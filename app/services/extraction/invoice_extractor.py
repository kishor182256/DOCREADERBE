from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from app.services.extraction.base_extractor import BaseExtractor
from app.services.extraction.models import ExtractionResult

if TYPE_CHECKING:
    from app.services.ocr import TextBlock
    from app.services.processing_context import ProcessingContext


class InvoiceExtractor(BaseExtractor):
    document_type = "INVOICE"
    amount_pattern = r"(?:rs\.?|inr|₹)?\s*((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?)"
    label_boundary_pattern = (
        r"\b(?:mrd\s*no|mrdno|patient\s*name|patientname|bill\s*no|billino|bill\s*date|billdate|bilidate|"
        r"invoice\s*no|invoice\s*number|invoice\s*date|receipt\s*no|receipt\s*date|doctor\s*name|doctorname|"
        r"consultant|company|store|visit|age\s*/?\s*sex|payment|deposit|net\s*receivable|grand\s*total)\b"
    )

    def extract(self, context: ProcessingContext) -> ExtractionResult:
        all_text_blocks = self._sorted_text_blocks(context)
        invoice_sections = self._invoice_sections(all_text_blocks)
        text_blocks = self._select_primary_invoice_section(invoice_sections, all_text_blocks)
        full_text = self._full_text(context, text_blocks)

        fields: dict[str, Any] = {}
        warnings: list[str] = []

        self._set_field(fields, "hospital_name", self._extract_hospital_name(text_blocks, full_text))
        self._set_field(fields, "patient_name", self._extract_labeled_value(text_blocks, ("patient name", "patientname", "name of patient", "name")))
        self._set_field(fields, "invoice_number", self._extract_invoice_number(text_blocks, full_text))
        self._set_field(fields, "invoice_date", self._extract_invoice_date(text_blocks, full_text))
        self._set_field(fields, "doctor_name", self._extract_labeled_value(text_blocks, ("doctor name", "doctorname", "doctor", "consultant", "consultant name")))
        self._set_field(fields, "total_amount", self._extract_total_amount(text_blocks, full_text))
        amount_summary = self._extract_amount_summary(text_blocks)
        if amount_summary:
            fields["amount_summary"] = amount_summary
        self._set_field(fields, "gst_number", self._extract_gst_number(full_text))

        items = self._extract_items(text_blocks)
        if items:
            fields["items"] = items

        invoices = self._extract_invoice_sections(invoice_sections)
        if invoices:
            fields["invoices"] = invoices

        for field_name in ("hospital_name", "patient_name", "invoice_number", "invoice_date", "total_amount"):
            if field_name not in fields:
                warnings.append(f"{field_name} not detected.")

        confidence = self._calculate_confidence(fields=fields, warnings=warnings)
        return ExtractionResult(
            document_type=self.document_type,
            fields=fields,
            confidence=confidence,
            warnings=warnings,
            errors=[],
            extractor="invoice_rule_based_v2",
        )

    def _sorted_text_blocks(self, context: ProcessingContext) -> list[TextBlock]:
        blocks = [
            text_block
            for result in context.ocr_results
            for text_block in result.text_blocks
            if text_block.text.strip()
        ]
        return sorted(blocks, key=lambda block: (block.page_number, block.bounding_box.y, block.bounding_box.x))

    def _full_text(self, context: ProcessingContext, text_blocks: list[TextBlock]) -> str:
        if text_blocks:
            return "\n".join(block.text for block in text_blocks)
        return "\n".join(result.text for result in context.ocr_results)

    def _invoice_sections(self, text_blocks: list[TextBlock]) -> list[list[TextBlock]]:
        sections: list[list[TextBlock]] = []
        pages = sorted({block.page_number for block in text_blocks})
        for page_number in pages:
            page_blocks = [block for block in text_blocks if block.page_number == page_number]
            page_text = " ".join(block.text.lower() for block in page_blocks)
            has_invoice_id = self._has_invoice_identifier(page_text)
            has_amount_signal = self._has_amount_signal(page_text)
            if has_invoice_id and has_amount_signal:
                sections.append(page_blocks)

        if sections:
            return sections

        for page_number in pages:
            page_blocks = [block for block in text_blocks if block.page_number == page_number]
            page_text = " ".join(block.text.lower() for block in page_blocks)
            if self._has_invoice_identifier(page_text):
                sections.append(page_blocks)
        return sections

    def _select_primary_invoice_section(self, invoice_sections: list[list[TextBlock]], text_blocks: list[TextBlock]) -> list[TextBlock]:
        if invoice_sections:
            return max(invoice_sections, key=self._invoice_section_score)
        return text_blocks

    def _invoice_section_score(self, text_blocks: list[TextBlock]) -> tuple[int, int, int, int]:
        text = " ".join(block.text.lower() for block in text_blocks)
        has_invoice_number = 1 if self._extract_invoice_number(text_blocks, text) else 0
        has_total = 1 if self._has_amount_signal(text) else 0
        has_gst = 1 if "gst" in text else 0
        return (has_invoice_number, has_total, has_gst, len(text_blocks))

    def _select_invoice_section(self, text_blocks: list[TextBlock]) -> list[TextBlock]:
        invoice_sections = self._invoice_sections(text_blocks)
        if invoice_sections:
            return self._select_primary_invoice_section(invoice_sections, text_blocks)
        pages = sorted({block.page_number for block in text_blocks})
        for page_number in pages:
            page_blocks = [block for block in text_blocks if block.page_number == page_number]
            page_text = " ".join(block.text.lower() for block in page_blocks)
            if self._has_invoice_identifier(page_text):
                return page_blocks

        return text_blocks

    def _has_invoice_identifier(self, text: str) -> bool:
        return any(
            signal in text
            for signal in ("bill no", "billino", "bilhno", "receipt na", "receipt no", "invoice no", "receipt na")
        )

    def _has_amount_signal(self, text: str) -> bool:
        return any(
            signal in text
            for signal in ("net receivable", "payment received", "grand total", "paid amount", "total amount", "cash", "sub total")
        )

    def _set_field(self, fields: dict[str, Any], field_name: str, value: Any) -> None:
        if value not in (None, "", []):
            fields[field_name] = value

    def _extract_labeled_value(self, text_blocks: list[TextBlock], labels: tuple[str, ...]) -> str | None:
        for index, block in enumerate(text_blocks):
            block_text = self._clean_value(block.text)
            normalized = block_text.lower()
            for label in labels:
                value = self._value_after_label(block_text, label)
                if value:
                    return value

                if label in normalized:
                    nearby_value = self._nearby_value(text_blocks, index)
                    if nearby_value:
                        return nearby_value
        return None

    def _value_after_label(self, text: str, label: str) -> str | None:
        label_pattern = r"\s*".join(re.escape(part) for part in label.split())
        pattern = rf"\b{label_pattern}\b\s*(?:no\.?|number)?\s*[:;=\-+_—]*\s*(.+)$"
        match = re.search(pattern, text, re.IGNORECASE)
        if match is None:
            return None

        value = self._truncate_at_next_label(match.group(1))
        value = self._clean_value(value)
        if not value or value.lower() == label:
            return None
        return value

    def _truncate_at_next_label(self, value: str) -> str:
        match = re.search(self.label_boundary_pattern, value, re.IGNORECASE)
        if match is None or match.start() == 0:
            return value
        return value[: match.start()]

    def _nearby_value(self, text_blocks: list[TextBlock], index: int) -> str | None:
        source = text_blocks[index]
        source_right = source.bounding_box.x + source.bounding_box.width

        candidates = [
            block
            for block in text_blocks
            if block.page_number == source.page_number
            and block.bounding_box.x >= source_right
            and abs(block.bounding_box.y - source.bounding_box.y) <= max(source.bounding_box.height, 12)
        ]
        if candidates:
            return self._clean_value(sorted(candidates, key=lambda block: block.bounding_box.x)[0].text)

        if index + 1 < len(text_blocks):
            next_block = text_blocks[index + 1]
            if next_block.page_number == source.page_number:
                return self._clean_value(next_block.text)
        return None

    def _extract_hospital_name(self, text_blocks: list[TextBlock], full_text: str) -> str | None:
        known_hospital_match = re.search(r"deenanath\s+mangeshkar\s+hospital", full_text, re.IGNORECASE)
        if known_hospital_match or re.search(r"\blmmf'?s\b|deenan[@a]h", full_text, re.IGNORECASE):
            return "Deenanath Mangeshkar Hospital"

        hospital_lines = [
            self._clean_value(block.text)
            for block in text_blocks
            if "hospital" in block.text.lower() or "medical" in block.text.lower()
        ]
        if hospital_lines:
            return min(hospital_lines, key=len)

        match = re.search(r"([A-Z][A-Za-z .&'-]*(?:Hospital|Medical)[A-Za-z .&'-]*)", full_text)
        return self._clean_value(match.group(1)) if match else None

    def _extract_invoice_number(self, text_blocks: list[TextBlock], full_text: str) -> str | None:
        separator = r"[:;=\-+_—\s]*"
        patterns = (
            r"\b(BNO\d+)\b",
            rf"\b(?:bill\s*no|billino|bilhno|bill\s*number|invoice\s*no|invoice\s*number|receipt\s*no|receipt\s*na)\s*{separator}(?:\d\s+)?([A-Z0-9]*\d{{4,}}[A-Z0-9\/-]*)",
        )
        for text in [block.text for block in text_blocks] + [full_text]:
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    value = self._clean_value(match.group(1))
                    if re.search(r"\d{4,}", value):
                        return value
        return None

    def _extract_invoice_date(self, text_blocks: list[TextBlock], full_text: str) -> str | None:
        patterns = (
            r"\b(?:bill\s*date|billdate|bilidate|invoice\s*date|receipt\s*date|date\s*&\s*time|date)\s*[:;=\-+_—]*\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4}(?:\s+\d{1,2}[: ]\d{2}\s*(?:am|pm)?)?)",
            r"\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})\b",
        )
        for text in [block.text for block in text_blocks] + [full_text]:
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return self._clean_value(match.group(1))
        return None

    def _extract_total_amount(self, text_blocks: list[TextBlock], full_text: str) -> str | None:
        preferred_labels = ("net receivable", "payment received", "paid amount", "cash", "amount payable")
        for label in preferred_labels:
            value = self._extract_labeled_value(text_blocks, (label,))
            amount = self._extract_amount(value or "")
            if amount and float(amount) > 0:
                return amount

        labels = ("grand total", "net amount", "total amount", "total")
        for label in labels:
            value = self._extract_labeled_value(text_blocks, (label,))
            amount = self._extract_amount(value or "")
            if amount and float(amount) > 0:
                return amount

        total_lines = [block.text for block in text_blocks if any(label in block.text.lower() for label in labels)]
        for line in total_lines:
            amount = self._extract_amount(line)
            if amount and float(amount) > 0:
                return amount

        amounts = [self._to_amount(match.group(1)) for match in re.finditer(self.amount_pattern, full_text, flags=re.IGNORECASE)]
        numeric_amounts = [amount for amount in amounts if amount is not None]
        if not numeric_amounts:
            return None
        return f"{max(numeric_amounts):.2f}"

    def _extract_amount_summary(self, text_blocks: list[TextBlock]) -> dict[str, str]:
        summary: dict[str, str] = {}
        label_map = {
            "cash": ("cash",),
            "grand_total": ("grand total",),
            "net_receivable": ("net receivable",),
            "payment_received": ("payment received",),
            "paid_amount": ("paid amount",),
            "deposit_adjusted": ("deposit adjusted",),
            "sub_total": ("sub total", "subtotal"),
            "discount": ("discount", "discount on mrp"),
            "cgst": ("cgst", "cgst amt"),
            "sgst": ("sgst", "sgst amt"),
            "taxable_amount": ("taxable", "taxable amount"),
        }
        for field_name, labels in label_map.items():
            for label in labels:
                value = self._extract_labeled_value(text_blocks, (label,))
                amount = self._extract_amount(value or "")
                if amount is None:
                    line = self._find_line_containing(text_blocks, label)
                    amount = self._extract_amount_for_summary_label(line or "", label)
                if amount is not None:
                    summary[field_name] = amount
                    break
        return summary

    def _extract_amount_for_summary_label(self, line: str, label: str) -> str | None:
        normalized = line.lower()
        if label == "cash" and not re.search(r"\bcash\s*[:=]\s*\d", normalized):
            return None

        amount = self._extract_amount(line)
        if amount is None:
            return None
        numeric_amount = self._to_amount(amount)
        if numeric_amount is None or numeric_amount > 1_000_000:
            return None
        return amount

    def _find_line_containing(self, text_blocks: list[TextBlock], label: str) -> str | None:
        normalized_label = label.lower()
        for block in text_blocks:
            if normalized_label in block.text.lower():
                return block.text
        return None

    def _extract_amount(self, text: str) -> str | None:
        matches = re.findall(self.amount_pattern, text, flags=re.IGNORECASE)
        amounts = [self._to_amount(match) for match in matches]
        numeric_amounts = [amount for amount in amounts if amount is not None]
        if not numeric_amounts:
            return None
        return f"{numeric_amounts[-1]:.2f}"

    def _to_amount(self, value: str) -> float | None:
        try:
            return float(value.replace(",", ""))
        except ValueError:
            return None

    def _extract_gst_number(self, full_text: str) -> str | None:
        match = re.search(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]\b", full_text.upper())
        return match.group(0) if match else None

    def _extract_items(self, text_blocks: list[TextBlock]) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        ignored_terms = (
            "total",
            "grand",
            "subtotal",
            "amount payable",
            "net receivable",
            "payment",
            "deposit",
            "cash",
            "bill no",
            "bill date",
            "invoice",
            "patient",
            "receipt date",
            "printed date",
            "gstin",
            "fdalic",
            "food lic",
            "schedule",
            "jurisdiction",
            "scanned",
            "address",
            "website",
            "company",
            "store",
            "doctor",
            "age/sex",
            "mrd",
            "manufacturer",
            "not known",
            "hsn",
            "hsncd",
            "exp date",
        )
        item_keywords = (
            "tab",
            "cap",
            "caps",
            "injection",
            "syrup",
            "xray",
            "test",
            "consultation",
            "charges",
            "radiology",
            "stool",
            "wheel",
            "suture",
        )

        seen: set[tuple[str, str]] = set()
        for block in text_blocks:
            item = self._extract_line_item(block.text, ignored_terms, item_keywords)
            if item is None:
                continue
            key = (item["description"].lower(), item["amount"])
            if key in seen:
                continue
            seen.add(key)
            items.append(item)

            if len(items) >= 20:
                break

        return items

    def _extract_invoice_sections(self, invoice_sections: list[list[TextBlock]]) -> list[dict[str, Any]]:
        invoices: list[dict[str, Any]] = []
        for section_blocks in invoice_sections:
            section_text = "\n".join(block.text for block in section_blocks)
            invoice: dict[str, Any] = {
                "page_number": section_blocks[0].page_number,
            }
            self._set_field(invoice, "hospital_name", self._extract_hospital_name(section_blocks, section_text))
            self._set_field(invoice, "patient_name", self._extract_labeled_value(section_blocks, ("patient name", "patientname", "name")))
            self._set_field(invoice, "invoice_number", self._extract_invoice_number(section_blocks, section_text))
            self._set_field(invoice, "invoice_date", self._extract_invoice_date(section_blocks, section_text))
            self._set_field(invoice, "doctor_name", self._extract_labeled_value(section_blocks, ("doctor name", "doctorname", "doctor", "consultant")))
            self._set_field(invoice, "total_amount", self._extract_total_amount(section_blocks, section_text))
            self._set_field(invoice, "gst_number", self._extract_gst_number(section_text))

            amount_summary = self._extract_amount_summary(section_blocks)
            if amount_summary:
                invoice["amount_summary"] = amount_summary

            items = self._extract_items(section_blocks)
            if items:
                invoice["items"] = items
            invoices.append(invoice)
        return invoices

    def _extract_line_item(
        self,
        raw_line: str,
        ignored_terms: tuple[str, ...],
        item_keywords: tuple[str, ...],
    ) -> dict[str, str] | None:
        line = self._clean_value(raw_line)
        normalized = line.lower()
        if any(term in normalized for term in ignored_terms):
            return None

        has_item_keyword = any(keyword in normalized for keyword in item_keywords)
        looks_like_numbered_item = re.match(r"^\d+\s+[_\-|]*\s*[A-Za-z]", line) is not None
        if not has_item_keyword and not looks_like_numbered_item:
            return None

        numeric_matches = list(re.finditer(r"\b\d+(?:,\d{3})*(?:\.\d{1,2})?\b", line))
        if not numeric_matches:
            return None

        amount_match = self._select_item_amount_match(numeric_matches)
        amount = self._to_amount(amount_match.group(0))
        if amount is None or amount <= 0 or amount > 100_000:
            return None

        description = self._item_description(line, amount_match)
        if len(description) < 3:
            return None

        item: dict[str, str] = {
            "description": description,
            "amount": f"{amount:.2f}",
        }

        quantity = self._extract_quantity(line, numeric_matches, amount_match)
        if quantity is not None:
            item["quantity"] = quantity

        rate = self._extract_rate(numeric_matches, amount_match)
        if rate is not None:
            item["rate"] = rate
        return item

    def _select_item_amount_match(self, numeric_matches: list[re.Match[str]]) -> re.Match[str]:
        decimal_matches = [match for match in numeric_matches if "." in match.group(0)]
        return decimal_matches[-1] if decimal_matches else numeric_matches[-1]

    def _item_description(self, line: str, amount_match: re.Match[str]) -> str:
        description = line[: amount_match.start()]
        description = re.sub(r"^\d+\s*", "", description)
        description = re.sub(r"\b(?:qty|rate|amount|total)\b", "", description, flags=re.IGNORECASE)
        description = re.sub(r"\s+\d+(?:,\d{3})*(?:\.\d{1,2})?\s*$", "", description)
        description = re.sub(r"\s+", " ", description)
        return description.strip(" _-:|,")

    def _extract_quantity(
        self,
        line: str,
        numeric_matches: list[re.Match[str]],
        amount_match: re.Match[str],
    ) -> str | None:
        quantity_match = re.search(r"\b(?:qty|quantity)\s*[:\-]?\s*(\d+(?:\.\d+)?)\b", line, re.IGNORECASE)
        if quantity_match:
            return quantity_match.group(1)

        amount_index = numeric_matches.index(amount_match)
        if amount_index >= 2:
            quantity_candidate = numeric_matches[amount_index - 2].group(0)
            value = self._to_amount(quantity_candidate)
            if value is not None and 0 < value <= 100:
                return quantity_candidate
        return None

    def _extract_rate(self, numeric_matches: list[re.Match[str]], amount_match: re.Match[str]) -> str | None:
        amount_index = numeric_matches.index(amount_match)
        if amount_index >= 1:
            rate = self._to_amount(numeric_matches[amount_index - 1].group(0))
            if rate is not None and rate > 0:
                return f"{rate:.2f}"
        return None

    def _clean_value(self, value: str) -> str:
        value = re.sub(r"\s+", " ", value).strip()
        return value.strip(" :,-|")

    def _calculate_confidence(self, *, fields: dict[str, Any], warnings: list[str]) -> float:
        weights = {
            "invoice_number": 0.2,
            "patient_name": 0.18,
            "invoice_date": 0.15,
            "hospital_name": 0.14,
            "total_amount": 0.2,
            "doctor_name": 0.05,
            "gst_number": 0.04,
            "items": 0.04,
        }
        confidence = sum(weight for field, weight in weights.items() if field in fields)
        confidence -= len(warnings) * 0.03
        return round(max(min(confidence, 0.99), 0.0), 2)
