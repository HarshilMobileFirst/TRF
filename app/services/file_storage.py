import json
from pathlib import Path

from app.core.config import Settings
from app.schemas.trf import TRFDocument


def ensure_storage_dirs(settings: Settings) -> None:
    for path in storage_dirs(settings).values():
        path.mkdir(parents=True, exist_ok=True)


def storage_dirs(settings: Settings) -> dict[str, Path]:
    root = settings.storage_root
    return {
        "root": root,
        "uploads": root / settings.uploads_dir,
        "processed": root / settings.processed_dir,
        "corrected": root / settings.corrected_dir,
        "approved": root / settings.approved_dir,
    }


def save_json(path: Path, document: TRFDocument) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document.model_dump_json(indent=2), encoding="utf-8")


def load_json(path: Path) -> TRFDocument:
    return TRFDocument.model_validate(json.loads(path.read_text(encoding="utf-8")))
