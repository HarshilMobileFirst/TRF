from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.core.auth import get_current_username
from app.schemas.trf import CorrectionPayload, TRFDocument, TRFListItem, ValidationResult
from app.services.trf_service import TRFService, get_trf_service

router = APIRouter(prefix="/trf", tags=["trf"])


@router.post("/upload", response_model=TRFDocument, status_code=status.HTTP_201_CREATED)
async def upload_trf(
    file: UploadFile = File(...),
    _: str = Depends(get_current_username),
    service: TRFService = Depends(get_trf_service),
) -> TRFDocument:
    return await service.upload_and_process(file)


@router.get("", response_model=list[TRFListItem])
def list_trfs(
    _: str = Depends(get_current_username),
    service: TRFService = Depends(get_trf_service),
) -> list[TRFListItem]:
    return service.list_documents()


@router.get("/{document_id}", response_model=TRFDocument)
def get_trf(
    document_id: str,
    _: str = Depends(get_current_username),
    service: TRFService = Depends(get_trf_service),
) -> TRFDocument:
    return service.get_document(document_id)


@router.get("/{document_id}/file")
def get_trf_file(
    document_id: str,
    _: str = Depends(get_current_username),
    service: TRFService = Depends(get_trf_service),
) -> FileResponse:
    document = service.get_document(document_id)
    file_path = service.get_uploaded_file_path(document_id, document.source_file_name)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Original file not found")
    media_type = _media_type_for(file_path)
    return FileResponse(path=file_path, media_type=media_type, filename=file_path.name)


@router.post("/{document_id}/validate", response_model=ValidationResult)
def validate_trf(
    document_id: str,
    _: str = Depends(get_current_username),
    service: TRFService = Depends(get_trf_service),
) -> ValidationResult:
    return service.revalidate(document_id)


@router.put("/{document_id}/correct", response_model=TRFDocument)
def correct_trf(
    document_id: str,
    payload: CorrectionPayload,
    _: str = Depends(get_current_username),
    service: TRFService = Depends(get_trf_service),
) -> TRFDocument:
    return service.correct_document(document_id, payload)


@router.post("/{document_id}/approve", response_model=TRFDocument)
def approve_trf(
    document_id: str,
    _: str = Depends(get_current_username),
    service: TRFService = Depends(get_trf_service),
) -> TRFDocument:
    return service.approve_document(document_id)


def _media_type_for(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return "application/pdf"
    if suffix == ".png":
        return "image/png"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    return "application/octet-stream"
