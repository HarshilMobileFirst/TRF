import base64
import io
import logging
from typing import Any

from app.core.config import Settings
from app.ocr.base import OCRProvider, OCRResult

logger = logging.getLogger(__name__)


class OpenAIOCRProvider(OCRProvider):
    """Use an OpenAI multimodal model to transcribe TRFs into canonical field-friendly text."""

    def __init__(self, settings: Settings):
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when OCR_PROVIDER=openai")
        self.settings = settings

    def extract_text(self, file_bytes: bytes, filename: str) -> OCRResult:
        client = self._build_client()
        response = client.responses.create(
            model=self.settings.openai_model,
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "You are a TRF document transcription engine. "
                                "Read the uploaded Test Requisition Form and convert it into a clean canonical transcription "
                                "using these exact labels when the values are present: "
                                "Patient Name:, Patient ID:, DOB:, Age:, Gender:, Doctor Name:, Hospital / Center:, "
                                "Requisition Date:, Sample Type:, Tests:, Test Codes:, Priority:, Contact Number:, Notes:. "
                                "Use one field per line. "
                                "Do not invent values. "
                                "If a field is not visible, omit that line. "
                                "Normalize obvious OCR noise only when you are confident."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": self._build_document_content(file_bytes, filename),
                },
            ],
            max_output_tokens=800,
        )
        output_text = (response.output_text or "").strip()
        if not output_text:
            raise ValueError("OpenAI returned empty OCR output")
        logger.info("OpenAI OCR completed for %s using model %s", filename, self.settings.openai_model)
        return OCRResult(text=output_text, confidence=0.93)

    def _build_client(self):
        from openai import OpenAI

        return OpenAI(api_key=self.settings.openai_api_key, timeout=self.settings.openai_timeout_seconds)

    def _build_document_content(self, file_bytes: bytes, filename: str) -> list[dict[str, Any]]:
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        content: list[dict[str, Any]] = [
            {
                "type": "input_text",
                "text": (
                    f"Transcribe this TRF file named {filename}. "
                    "Return the canonical field-labeled transcription only."
                ),
            }
        ]

        if extension == "pdf":
            uploaded_file = self._build_client().files.create(
                file=(filename, io.BytesIO(file_bytes), "application/pdf"),
                purpose="user_data",
            )
            content.append(
                {
                    "type": "input_file",
                    "file_id": uploaded_file.id,
                }
            )
            return content

        mime_type = "image/jpeg"
        if extension == "png":
            mime_type = "image/png"
        image_data_url = f"data:{mime_type};base64,{base64.b64encode(file_bytes).decode('utf-8')}"
        content.append(
            {
                "type": "input_image",
                "image_url": image_data_url,
                "detail": "high",
            }
        )
        return content
