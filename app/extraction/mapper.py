import re
from datetime import date, datetime

from app.schemas.trf import ConfidenceScores, ExtractedData


class RuleBasedTRFMapper:
    FIELD_PATTERNS = {
        "patient_name": r"Patient Name\s*:\s*(.+)",
        "patient_id": r"Patient ID\s*:\s*([A-Za-z0-9\-\/]+)",
        "age": r"Age\s*:\s*(\d{1,3})",
        "gender": r"Gender\s*:\s*(Male|Female|Other)",
        "doctor_name": r"Doctor Name\s*:\s*(.+)",
        "hospital_or_center_name": r"(?:Hospital\s*/\s*Center|Hospital|Center)\s*:\s*(.+)",
        "requisition_date": r"Requisition Date\s*:\s*([0-9]{4}[\/\.-][0-9]{2}[\/\.-][0-9]{2}|[0-9]{2}[\/\.-][0-9]{2}[\/\.-][0-9]{4})",
        "sample_type": r"Sample Type\s*:\s*(.+)",
        "priority": r"Priority\s*:\s*(Routine|Urgent|Stat)",
        "contact_number": r"Contact Number\s*:\s*([\+0-9\-\s]{10,15})",
        "notes": r"Notes\s*:\s*(.+)",
    }

    def map_text(
        self,
        text: str,
        source_file_name: str,
        ocr_confidence: float,
    ) -> tuple[ExtractedData, ConfidenceScores]:
        data = ExtractedData(
            patient_name=self._match("patient_name", text),
            patient_id=self._match("patient_id", text),
            age=self._match_int("age", text),
            gender=self._match("gender", text),
            doctor_name=self._match("doctor_name", text),
            hospital_or_center_name=self._match("hospital_or_center_name", text),
            requisition_date=self._match("requisition_date", text),
            sample_type=self._match("sample_type", text),
            test_names=self._extract_list(text, r"Tests?\s*:\s*(.+)"),
            test_codes=self._extract_list(text, r"Test Codes?\s*:\s*(.+)"),
            priority=self._match("priority", text),
            contact_number=self._match("contact_number", text),
            notes=self._match("notes", text),
        )

        if data.age is None:
            dob = self._extract_dob(text)
            if dob is not None:
                age_at = self._extract_reference_date(data.requisition_date) or date.today()
                computed_age = self._compute_age(dob, age_at)
                if computed_age is not None:
                    data.age = computed_age

        confidence = ConfidenceScores(
            patient_name=self._score(data.patient_name, ocr_confidence),
            patient_id=self._score(data.patient_id, ocr_confidence),
            age=self._score(data.age, ocr_confidence),
            gender=self._score(data.gender, ocr_confidence),
            doctor_name=self._score(data.doctor_name, ocr_confidence),
            hospital_or_center_name=self._score(data.hospital_or_center_name, ocr_confidence),
            requisition_date=self._score(data.requisition_date, ocr_confidence),
            sample_type=self._score(data.sample_type, ocr_confidence),
            test_names=self._score(data.test_names, ocr_confidence),
            test_codes=self._score(data.test_codes, ocr_confidence),
            priority=self._score(data.priority, ocr_confidence),
            contact_number=self._score(data.contact_number, ocr_confidence),
            notes=self._score(data.notes, ocr_confidence),
            extraction_confidence=round(ocr_confidence, 2),
        )

        return data, confidence

    def _match(self, field: str, text: str) -> str | None:
        pattern = self.FIELD_PATTERNS[field]
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            return None
        return match.group(1).strip()

    def _match_int(self, field: str, text: str) -> int | None:
        value = self._match(field, text)
        return int(value) if value is not None else None

    @staticmethod
    def _extract_list(text: str, pattern: str) -> list[str]:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            return []
        raw = match.group(1)
        return [item.strip() for item in re.split(r",|;", raw) if item.strip()]

    @staticmethod
    def _score(value: object, base_confidence: float) -> float:
        if value is None or value == []:
            return 0.0
        return round(min(base_confidence + 0.08, 0.99), 2)

    @staticmethod
    def _extract_dob(text: str) -> date | None:
        match = re.search(r"(?:DOB|Date of Birth)\s*:\s*([0-9]{4}[\/\.-][0-9]{2}[\/\.-][0-9]{2}|[0-9]{2}[\/\.-][0-9]{2}[\/\.-][0-9]{4})", text, flags=re.IGNORECASE)
        if not match:
            return None
        return RuleBasedTRFMapper._parse_date(match.group(1))

    @staticmethod
    def _extract_reference_date(value: str | None) -> date | None:
        if value is None:
            return None
        parsed = RuleBasedTRFMapper._parse_date(value)
        return parsed

    @staticmethod
    def _parse_date(value: str) -> date | None:
        cleaned = value.strip()
        if not cleaned:
            return None
        cleaned = cleaned.split("T", 1)[0].split(" ", 1)[0]
        cleaned = cleaned.replace("/", "-").replace(".", "-")
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m-%d-%Y"):
            try:
                return datetime.strptime(cleaned, fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _compute_age(dob: date, on_date: date) -> int | None:
        if dob > on_date:
            return None
        years = on_date.year - dob.year
        if (on_date.month, on_date.day) < (dob.month, dob.day):
            years -= 1
        if years < 0 or years > 125:
            return None
        return years
