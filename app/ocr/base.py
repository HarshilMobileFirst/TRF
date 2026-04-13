from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class OCRResult:
    text: str
    confidence: float


class OCRProvider(ABC):
    @abstractmethod
    def extract_text(self, file_bytes: bytes, filename: str) -> OCRResult:
        raise NotImplementedError
