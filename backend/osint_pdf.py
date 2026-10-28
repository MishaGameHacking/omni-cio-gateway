"""Isolated PDF text worker. Input is bytes, never executable instructions or URLs."""
from __future__ import annotations

import io
import json
from pathlib import Path
import sys


def limits() -> None:
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (384 * 1024**2, 384 * 1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    resource.setrlimit(resource.RLIMIT_FSIZE, (2 * 1024**2, 2 * 1024**2))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))


def extract(raw: bytes) -> dict:
    vendor = Path(__file__).with_name("_osint_vendor")
    if vendor.is_dir():
        sys.path.insert(0, str(vendor))
    from pypdf import PdfReader
    if not raw.startswith(b"%PDF-") or len(raw) > 12 * 1024**2:
        raise ValueError("osint_pdf_invalid")
    reader = PdfReader(io.BytesIO(raw), strict=False)
    if reader.is_encrypted:
        raise ValueError("osint_pdf_encrypted")
    pages, remaining = [], 240_000
    count = len(reader.pages)
    truncated = False
    for index in range(min(80, count)):
        text = reader.pages[index].extract_text(extraction_mode="layout") or ""
        part = text[:min(12000, remaining)]
        truncated = truncated or len(part) < len(text)
        pages.append({"page": index + 1, "text": part})
        remaining -= len(part)
        if remaining <= 0:
            break
    return {"pages": pages, "page_count": count,
            "truncated": truncated or count > len(pages) or remaining <= 0,
            "needs_ocr": sum(len(page["text"].strip()) for page in pages) < 100}


def main() -> None:
    limits()
    try:
        result = extract(sys.stdin.buffer.read(12 * 1024**2 + 1))
    except Exception as error:
        code = str(error) if str(error) in {"osint_pdf_invalid", "osint_pdf_encrypted"} else "osint_pdf_parse_failed"
        result = {"error": code}
    sys.stdout.write(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
