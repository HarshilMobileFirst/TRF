import re
from datetime import datetime, timedelta
from pathlib import Path

from app.core.config import Settings
from app.schemas.trf import ExtractedData, ValidationResult
from app.services.file_storage import load_json, storage_dirs
from app.services.sample_catalog import SUPPORTED_SAMPLE_TYPES, TEST_CATALOG


class TRFValidator:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.paths = storage_dirs(settings)

    def validate(self, document_id: str, data: ExtractedData) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        self._validate_mandatory_fields(data, errors, warnings)
        self._validate_date(data, errors)
        self._validate_patient_id(data, errors)
        self._validate_phone(data, warnings)
        self._validate_sample_type(data, errors, warnings)
        self._validate_tests(data, errors, warnings)
        self._check_duplicate_requisition(document_id, data, warnings)

        status = "valid"
        if errors:
            status = "invalid"
        elif warnings:
            status = "review_required"
        return ValidationResult(status=status, errors=errors, warnings=warnings)

    @staticmethod
    def _validate_mandatory_fields(data: ExtractedData, errors: list[str], warnings: list[str]) -> None:
        mandatory_fields = {
            "patient_name": data.patient_name,
            "patient_id": data.patient_id,
            "doctor_name": data.doctor_name,
            "requisition_date": data.requisition_date,
            "sample_type": data.sample_type,
        }
        for field_name, value in mandatory_fields.items():
            if value is None:
                warnings.append(f"Mandatory field missing: {field_name}")

        for field_name, value in {
            "patient_name": data.patient_name,
            "doctor_name": data.doctor_name,
        }.items():
            if value is not None and not value.strip():
                errors.append(f"Blank value not allowed for {field_name}")

    @staticmethod
    def _validate_date(data: ExtractedData, errors: list[str]) -> None:
        if data.requisition_date is None:
            return
        if TRFValidator._parse_date(data.requisition_date) is None:
            errors.append("Invalid date format for requisition_date")

    @staticmethod
    def _validate_patient_id(data: ExtractedData, errors: list[str]) -> None:
        if data.patient_id is None:
            return
        if not re.fullmatch(r"[A-Za-z]{2,5}-?\d{3,10}", data.patient_id):
            errors.append("Invalid patient ID format")

    @staticmethod
    def _validate_phone(data: ExtractedData, warnings: list[str]) -> None:
        if data.contact_number is None:
            return
        digits = re.sub(r"\D", "", data.contact_number)
        if len(digits) not in {10, 12}:
            warnings.append("Invalid phone format")

    @staticmethod
    def _validate_sample_type(data: ExtractedData, errors: list[str], warnings: list[str]) -> None:
        if data.sample_type is None:
            return
        normalized = TRFValidator._normalize_sample_type(data.sample_type)
        if normalized is None or normalized not in SUPPORTED_SAMPLE_TYPES:
            errors.append("Unsupported sample type")
        elif normalized != data.sample_type.strip():
            warnings.append(f"Sample type normalized suggestion: {normalized}")

    @staticmethod
    def _validate_tests(data: ExtractedData, errors: list[str], warnings: list[str]) -> None:
        seen_codes: set[str] = set()
        sample_type = data.sample_type.strip().title() if data.sample_type else None

        for code in data.test_codes:
            upper_code = code.upper()
            if upper_code in seen_codes:
                warnings.append(f"Duplicate test entry detected for code {upper_code}")
                continue
            seen_codes.add(upper_code)

            catalog_entry = TEST_CATALOG.get(upper_code)
            if catalog_entry is None:
                errors.append(f"Invalid or unknown test code: {upper_code}")
                continue
            if sample_type and sample_type not in catalog_entry.sample_types:
                errors.append(
                    f"Mismatch between test and sample type: {upper_code} requires {', '.join(catalog_entry.sample_types)}"
                )

        if len(data.test_names) != len(data.test_codes):
            warnings.append("Mismatch between number of test names and test codes")

        for name, code in zip(data.test_names, data.test_codes):
            entry = TEST_CATALOG.get(code.upper())
            if entry and entry.name.lower() != name.strip().lower():
                errors.append(f"Mismatch between test name and test code: {name} / {code}")

    def _check_duplicate_requisition(
        self,
        document_id: str,
        data: ExtractedData,
        warnings: list[str],
    ) -> None:
        if not data.patient_id or not data.requisition_date:
            return

        current_date = self._parse_date(data.requisition_date)
        if current_date is None:
            return

        threshold = timedelta(days=self.settings.sample_duplicate_window_days)
        current_codes = sorted(code.upper() for code in data.test_codes)

        for candidate in self._existing_documents():
            if candidate.document_id == document_id:
                continue
            existing = candidate.extracted_data
            if existing.patient_id != data.patient_id:
                continue
            existing_date = self._parse_date(existing.requisition_date)
            if existing_date is None:
                continue
            if abs(existing_date - current_date) <= threshold:
                if sorted(code.upper() for code in existing.test_codes) == current_codes:
                    warnings.append(
                        f"Suspicious duplicate requisition found: {candidate.document_id}"
                    )
                    return

    def _existing_documents(self):
        for folder_name in ("processed", "corrected", "approved"):
            for path in Path(self.paths[folder_name]).glob("*.json"):
                yield load_json(path)

    @staticmethod
    def _parse_date(value: str | None) -> datetime | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None

        # Drop time portion if OCR returns "YYYY-MM-DD HH:MM" or ISO timestamp.
        cleaned = cleaned.split("T", 1)[0].split(" ", 1)[0]
        # Normalize separators to '-' for easier parsing.
        cleaned = cleaned.replace("/", "-").replace(".", "-")

        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m-%d-%Y"):
            try:
                return datetime.strptime(cleaned, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _normalize_sample_type(value: str) -> str | None:
        """
        Normalize OCR-derived sample type into one of supported canonical values.
        Handles common OCR noise like extra words: "Whole Blood", "Blood (EDTA)", etc.
        """
        cleaned = value.strip().lower()
        if not cleaned:
            return None

        # Remove non-letters to avoid issues like "Blood(EDTA)" or "URINE-ROUTINE".
        letters_only = re.sub(r"[^a-z\s]+", " ", cleaned)
        tokens = {token for token in letters_only.split() if token}

        if "blood" in tokens:
            return "Blood"
        if "urine" in tokens:
            return "Urine"
        if "serum" in tokens:
            return "Serum"
        if "plasma" in tokens:
            return "Plasma"
        if "swab" in tokens:
            return "Swab"

        # Fall back to simple title-case (keeps existing strict set membership).
        return value.strip().title()
