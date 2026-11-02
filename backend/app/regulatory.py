import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass
from zipfile import BadZipFile, ZipFile

from docx import Document as WordDocument
from docx.opc.exceptions import PackageNotFoundError
from fastapi import HTTPException, UploadFile
import pymupdf

EMBEDDING_DIMENSIONS = 384
SUPPORTED_MIME_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
RULE_CUE = re.compile(
    r"\b(shall|must|required|minimum|maximum|at least|not less than|credits?|duration|semester|"
    r"qualification level|eligibility|mandatory|prohibited|may not)\b",
    re.IGNORECASE,
)
CLAUSE_CUE = re.compile(
    r"^\s*((?:clause|section|regulation|rule|article|chapter)\s+[\w.-]+|"
    r"(?:\d+(?:\.\d+)*|[A-Z]\.\d+)[.)]?)\s*[:\-—]?\s*",
    re.IGNORECASE,
)
WORD_CUE = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*", re.UNICODE)


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int | None
    text: str


@dataclass(frozen=True)
class ExtractedDocument:
    pages: list[ExtractedPage]
    page_count: int
    warnings: list[str]


async def read_upload(upload: UploadFile, maximum_bytes: int) -> bytes:
    content = await upload.read(maximum_bytes + 1)
    if len(content) > maximum_bytes:
        raise HTTPException(status_code=413, detail=f"File exceeds the {maximum_bytes // (1024 * 1024)} MB upload limit")
    if not content:
        raise HTTPException(status_code=422, detail="The uploaded document is empty")
    return content


def extract_document(filename: str, content: bytes) -> ExtractedDocument:
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in SUPPORTED_MIME_TYPES:
        raise HTTPException(status_code=415, detail="Only PDF and DOCX documents are supported")
    if suffix == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise HTTPException(status_code=422, detail="The uploaded file is not a valid PDF")
        try:
            pages: list[ExtractedPage] = []
            warnings: list[str] = []
            with pymupdf.Document(stream=content, filetype="pdf") as document:
                if document.is_encrypted:
                    raise HTTPException(status_code=422, detail="Encrypted PDFs are not supported")
                if document.page_count > 2000:
                    raise HTTPException(status_code=413, detail="PDFs are limited to 2,000 pages")
                for index, page in enumerate(document):
                    page_text = page.get_text("text").strip()
                    tables = []
                    try:
                        for table in page.find_tables().tables:
                            rows = [" | ".join(cell or "" for cell in row) for row in table.extract()]
                            tables.extend(row for row in rows if row.strip(" |"))
                    except (AttributeError, RuntimeError):
                        warnings.append(f"Table extraction was unavailable on PDF page {index + 1}.")
                    combined = "\n".join(part for part in (page_text, "\n".join(tables)) if part)
                    pages.append(ExtractedPage(index + 1, combined))
        except HTTPException:
            raise
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="The PDF could not be read") from exc
        if any(not p.text.strip() for p in pages):
            warnings.append("Some pages have no extractable text; scanned pages may require OCR.")
        if not any(page.text.strip() for page in pages):
            raise HTTPException(status_code=422, detail="The PDF contains no extractable text")
        return ExtractedDocument(pages=pages, page_count=len(pages), warnings=warnings)

    if not content.startswith(b"PK"):
        raise HTTPException(status_code=422, detail="The uploaded DOCX file is invalid")
    try:
        from io import BytesIO

        with ZipFile(BytesIO(content)) as archive:
            members = archive.infolist()
            expanded_size = sum(member.file_size for member in members)
            if len(members) > 10_000 or expanded_size > 100 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="DOCX archive exceeds document processing limits")
            if "[Content_Types].xml" not in archive.namelist() or "word/document.xml" not in archive.namelist():
                raise HTTPException(status_code=422, detail="The uploaded ZIP file is not a valid DOCX document")
        document = WordDocument(BytesIO(content))
    except (ValueError, KeyError, OSError, BadZipFile, PackageNotFoundError) as exc:
        raise HTTPException(status_code=422, detail="The DOCX document could not be read") from exc
    parts = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))
    text = "\n".join(parts)
    if not text:
        raise HTTPException(status_code=422, detail="The DOCX contains no extractable text")
    return ExtractedDocument(pages=[ExtractedPage(None, text)], page_count=0, warnings=["Page numbers are not available for DOCX files."])


def split_pages(pages: Iterable[ExtractedPage], chunk_size: int, overlap: int) -> list[tuple[int | None, str]]:
    chunks: list[tuple[int | None, str]] = []
    for page in pages:
        text = re.sub(r"\s+", " ", page.text).strip()
        if not text:
            continue
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            if end < len(text):
                boundary = text.rfind(" ", start, end)
                if boundary > start + chunk_size // 2:
                    end = boundary
            chunk = text[start:end].strip()
            if chunk:
                chunks.append((page.page_number, chunk))
            if end >= len(text):
                break
            start = max(start + 1, end - overlap)
    return chunks


def candidate_rules(pages: Iterable[ExtractedPage], limit: int = 200) -> list[tuple[str | None, int | None, str]]:
    candidates: list[tuple[str | None, int | None, str]] = []
    seen: set[str] = set()
    for page in pages:
        for raw_paragraph in re.split(r"(?<=[.!?])\s+|\n+", page.text):
            paragraph = re.sub(r"\s+", " ", raw_paragraph).strip(" \t-•")
            if len(paragraph) < 30 or not RULE_CUE.search(paragraph):
                continue
            key = paragraph.casefold()
            if key in seen:
                continue
            seen.add(key)
            clause_match = CLAUSE_CUE.match(paragraph)
            candidates.append((clause_match.group(1).rstrip(".):") if clause_match else None, page.page_number, paragraph))
            if len(candidates) >= limit:
                return candidates
    return candidates


def local_embedding(value: str) -> list[float]:
    """Privacy-preserving signed feature hashing for local lexical retrieval."""
    tokens = [match.group(0).casefold() for match in WORD_CUE.finditer(value)]
    features = tokens + [f"{left}_{right}" for left, right in zip(tokens, tokens[1:])]
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for feature in features:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        number = int.from_bytes(digest, "little")
        vector[number % EMBEDDING_DIMENSIONS] += 1.0 if number >> 63 else -1.0
    norm = sum(component * component for component in vector) ** 0.5
    return [component / norm for component in vector] if norm else vector


def cosine_similarity(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))
