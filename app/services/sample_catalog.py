from dataclasses import dataclass


@dataclass(frozen=True)
class TestCatalogEntry:
    code: str
    name: str
    sample_types: tuple[str, ...]


TEST_CATALOG: dict[str, TestCatalogEntry] = {
    "CBC001": TestCatalogEntry(code="CBC001", name="Complete Blood Count", sample_types=("Blood",)),
    "THY002": TestCatalogEntry(code="THY002", name="Thyroid Panel", sample_types=("Blood",)),
    "LFT003": TestCatalogEntry(code="LFT003", name="Liver Function Test", sample_types=("Blood",)),
    "URI004": TestCatalogEntry(code="URI004", name="Urine Routine", sample_types=("Urine",)),
    "HBA005": TestCatalogEntry(code="HBA005", name="HbA1c", sample_types=("Blood",)),
}

SUPPORTED_SAMPLE_TYPES = {"Blood", "Urine", "Serum", "Plasma", "Swab"}
