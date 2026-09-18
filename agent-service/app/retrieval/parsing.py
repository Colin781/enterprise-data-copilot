import re
from io import BytesIO
from pathlib import PurePath

from pypdf import PdfReader

from app.retrieval.errors import DocumentLimitError, DocumentParseError
from app.retrieval.models import DocumentSection, SourceType

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def parse_document(
    *,
    source_name: str,
    source_type: SourceType,
    payload: bytes,
    max_markdown_bytes: int = 2_000_000,
    max_pdf_bytes: int = 10_000_000,
    max_pdf_pages: int = 100,
) -> tuple[DocumentSection, ...]:
    if not payload:
        raise DocumentParseError()
    if source_type == "MARKDOWN":
        if len(payload) > max_markdown_bytes:
            raise DocumentLimitError()
        return _parse_markdown(source_name, payload)
    if source_type != "PDF":
        raise DocumentParseError()
    if len(payload) > max_pdf_bytes:
        raise DocumentLimitError()
    return _parse_pdf(source_name, payload, max_pdf_pages)


def _parse_markdown(source_name: str, payload: bytes) -> tuple[DocumentSection, ...]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise DocumentParseError() from error
    lines = text.splitlines()
    default_title = PurePath(source_name).stem or "Document"
    sections: list[DocumentSection] = []
    heading = default_title
    heading_line = 1
    body: list[str] = []

    def flush(end_line: int) -> None:
        content = "\n".join(body).strip()
        if not content:
            return
        sections.append(
            DocumentSection(
                section_key=_section_key(source_name, heading, len(sections)),
                title=heading,
                source_locator=f"lines={heading_line}-{max(heading_line, end_line)}",
                content=content,
            )
        )

    for line_number, line in enumerate(lines, start=1):
        match = _HEADING.match(line)
        if match:
            flush(line_number - 1)
            heading = match.group(2).strip()
            heading_line = line_number
            body = []
        else:
            body.append(line)
    flush(len(lines))
    if not sections:
        raise DocumentParseError()
    return tuple(sections)


def _parse_pdf(source_name: str, payload: bytes, max_pdf_pages: int) -> tuple[DocumentSection, ...]:
    try:
        reader = PdfReader(BytesIO(payload))
        if reader.is_encrypted:
            raise DocumentParseError()
        if len(reader.pages) > max_pdf_pages:
            raise DocumentLimitError()
        sections = []
        for page_number, page in enumerate(reader.pages, start=1):
            content = (page.extract_text() or "").strip()
            if content:
                sections.append(
                    DocumentSection(
                        section_key=f"{source_name}#page-{page_number}",
                        title=f"Page {page_number}",
                        source_locator=f"page={page_number}",
                        content=content,
                    )
                )
    except (DocumentLimitError, DocumentParseError):
        raise
    except Exception as error:
        raise DocumentParseError() from error
    if not sections:
        raise DocumentParseError()
    return tuple(sections)


def _section_key(source_name: str, heading: str, ordinal: int) -> str:
    slug = re.sub(r"[^\w\u4e00-\u9fff]+", "-", heading.lower()).strip("-")
    return f"{source_name}#{slug or f'section-{ordinal + 1}'}"


def chunk_sections(
    sections: tuple[DocumentSection, ...],
    *,
    max_characters: int = 1_200,
    overlap_characters: int = 120,
) -> tuple[tuple[DocumentSection, int], ...]:
    if max_characters < 1 or overlap_characters < 0 or overlap_characters >= max_characters:
        raise ValueError("chunk bounds are invalid")
    chunks: list[tuple[DocumentSection, int]] = []
    ordinal = 0
    for section in sections:
        start = 0
        while start < len(section.content):
            end = min(len(section.content), start + max_characters)
            if end < len(section.content):
                boundary = max(
                    section.content.rfind("\n", start, end),
                    section.content.rfind("。", start, end),
                    section.content.rfind(". ", start, end),
                )
                if boundary > start + max_characters // 2:
                    end = boundary + 1
            content = section.content[start:end].strip()
            if content:
                chunks.append((section.model_copy(update={"content": content}), ordinal))
                ordinal += 1
            if end >= len(section.content):
                break
            start = max(start + 1, end - overlap_characters)
    return tuple(chunks)
