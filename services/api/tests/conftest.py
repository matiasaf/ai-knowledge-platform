"""Shared fixtures. Every test runs against a throwaway data directory."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ai_knowledge_platform.config import Settings, get_settings
from ai_knowledge_platform.main import create_app

# Small enough to write in a test, large enough that the size limit is not the
# constraint under test.
MAX_UPLOAD_BYTES = 4096
MAX_PDF_PAGES = 2


def build_text_pdf(page_texts: list[str]) -> bytes:
    """Build a small valid PDF fixture without pulling a generator into production."""
    page_object_ids = [3 + index * 2 for index in range(len(page_texts))]
    font_object_id = 3 + len(page_texts) * 2
    children = " ".join(f"{object_id} 0 R" for object_id in page_object_ids)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{children}] /Count {len(page_texts)} >>".encode(),
    ]

    for page_object_id, text in zip(page_object_ids, page_texts, strict=True):
        content_object_id = page_object_id + 1
        escaped_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content = f"BT /F1 12 Tf 72 720 Td ({escaped_text}) Tj ET".encode() if text else b""
        objects.extend(
            [
                (
                    f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                    f"/Resources << /Font << /F1 {font_object_id} 0 R >> >> "
                    f"/Contents {content_object_id} 0 R >>"
                ).encode(),
                f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream",
            ]
        )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    output = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{object_number} 0 obj\n".encode())
        output.extend(body)
        output.extend(b"\nendobj\n")

    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode()
    )
    return bytes(output)


MINIMAL_PDF = (
    b"%PDF-1.7\n"
    b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n"
    b"trailer\n<< /Root 1 0 R >>\n"
    b"%%EOF\n"
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        max_upload_bytes=MAX_UPLOAD_BYTES,
        max_pdf_pages=MAX_PDF_PAGES,
    )


@pytest.fixture
def documents_dir(settings: Settings) -> Path:
    return settings.documents_dir


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as test_client:
        yield test_client
