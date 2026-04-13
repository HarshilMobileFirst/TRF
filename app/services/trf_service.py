import logging
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import Settings, get_settings
from app.ocr.base import OCRProvider
from app.ocr.openai_provider import OpenAIOCRProvider
from app.schemas.trf import (
    CorrectionPayload,
    TRFDocument,
    TRFListItem,
    ValidationResult,
)
from app.services.file_storage import ensure_storage_dirs, load_json, save_json, storage_dirs
from app.validators.trf_validator import TRFValidator
from app.extraction.mapper import RuleBasedTRFMapper

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}


class TRFService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.paths = storage_dirs(settings)
        ensure_storage_dirs(settings)
        self.ocr_provider = self._get_ocr_provider()
        self.mapper = RuleBasedTRFMapper()
        self.validator = TRFValidator(settings)

    async def upload_and_process(self, file: UploadFile) -> TRFDocument:
        extension = Path(file.filename or "").suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file type. Allowed: PDF, PNG, JPG, JPEG",
            )

        document_id = str(uuid.uuid4())
        source_name = file.filename or f"{document_id}{extension}"
        file_path = self.paths["uploads"] / f"{document_id}{extension}"
        content = await file.read()
        file_path.write_bytes(content)

        actual_provider = self.settings.ocr_provider.lower()
        actual_model = self._provider_model_name(actual_provider)
        extraction_note: str | None = None
        ocr_result = self.ocr_provider.extract_text(content, source_name)

        extracted_data, confidence = self.mapper.map_text(ocr_result.text, source_name, ocr_result.confidence)
        validation = self.validator.validate(document_id, extracted_data)
        document = TRFDocument(
            document_id=document_id,
            status="processed",
            source_file_name=source_name,
            extraction_provider=actual_provider,
            extraction_model=actual_model,
            extraction_note=extraction_note,
            extracted_data=extracted_data,
            confidence=confidence,
            validation=validation,
            ocr_text=ocr_result.text,
        )
        save_json(self.paths["processed"] / f"{document_id}.json", document)
        logger.info("Processed document %s", document_id)
        return document

    def list_documents(self) -> list[TRFListItem]:
        items: list[TRFListItem] = []
        for path in self._all_document_paths():
            document = load_json(path)
            items.append(
                TRFListItem(
                    document_id=document.document_id,
                    status=document.status,
                    source_file_name=document.source_file_name,
                    patient_name=document.extracted_data.patient_name,
                    patient_id=document.extracted_data.patient_id,
                    requisition_date=document.extracted_data.requisition_date,
                    validation_status=document.validation.status,
                    updated_at=document.updated_at,
                )
            )
        items.sort(key=lambda item: item.updated_at, reverse=True)
        return items

    def get_document(self, document_id: str) -> TRFDocument:
        path = self._find_document_path(document_id)
        if path is None:
            raise HTTPException(status_code=404, detail="Document not found")
        return load_json(path)

    def get_uploaded_file_path(self, document_id: str, source_file_name: str) -> Path:
        suffix = Path(source_file_name).suffix.lower()
        return self.paths["uploads"] / f"{document_id}{suffix}"

    def revalidate(self, document_id: str) -> ValidationResult:
        document = self.get_document(document_id)
        validation = self.validator.validate(document_id, document.extracted_data)
        document.validation = validation
        document.updated_at = datetime.utcnow()
        self._save_by_status(document)
        return validation

    def correct_document(self, document_id: str, payload: CorrectionPayload) -> TRFDocument:
        document = self.get_document(document_id)
        document.extracted_data = payload.extracted_data
        document.validation = self.validator.validate(document_id, document.extracted_data)
        document.status = "corrected"
        document.updated_at = datetime.utcnow()
        save_json(self.paths["corrected"] / f"{document_id}.json", document)
        logger.info("Saved corrected document %s", document_id)
        return document

    def approve_document(self, document_id: str) -> TRFDocument:
        document = self.get_document(document_id)
        document.validation = self.validator.validate(document_id, document.extracted_data)
        document.status = "approved"
        document.approved_at = datetime.utcnow()
        document.updated_at = datetime.utcnow()
        save_json(self.paths["approved"] / f"{document_id}.json", document)
        logger.info("Approved document %s", document_id)
        return document

    def _get_ocr_provider(self) -> OCRProvider:
        provider = self.settings.ocr_provider.lower()
        if provider != "openai":
            raise ValueError(f"Unsupported OCR_PROVIDER={provider!r}. Only 'openai' is supported.")
        return OpenAIOCRProvider(self.settings)

    def _provider_model_name(self, provider_name: str) -> str:
        if provider_name == "openai":
            return self.settings.openai_model
        return "unknown"

    def _all_document_paths(self) -> list[Path]:
        found: dict[str, Path] = {}
        for folder_name in ("processed", "corrected", "approved"):
            for path in sorted(self.paths[folder_name].glob("*.json")):
                found[path.stem] = path
        return list(found.values())

    def _find_document_path(self, document_id: str) -> Path | None:
        for folder_name in ("approved", "corrected", "processed"):
            path = self.paths[folder_name] / f"{document_id}.json"
            if path.exists():
                return path
        for path in self._all_document_paths():
            try:
                document = load_json(path)
            except Exception:
                continue
            if document.document_id == document_id:
                return path
        return None

    def _save_by_status(self, document: TRFDocument) -> None:
        target = self.paths["processed"]
        if document.status == "corrected":
            target = self.paths["corrected"]
        if document.status == "approved":
            target = self.paths["approved"]
        save_json(target / f"{document.document_id}.json", document)


def get_trf_service() -> TRFService:
    return TRFService(get_settings())
