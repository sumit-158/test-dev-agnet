"""Attachment ingest: validate, store, render pages, parse with AG-01, index words (v1/F-04)."""

import io
import logging
import time
from typing import Any, Protocol

from backend.config import Settings
from backend.constants import (
    ALLOWED_MEDIA_TYPES,
    MAX_FILE_MB,
    MAX_PAGES_PER_ATTACHMENT,
    RENDER_DPI,
)
from backend.errors import PayloadTooLarge, UpstreamUnavailable
from backend.models import Attachment, Element, Page
from backend.services import source_locator
from backend.services.source_locator import extract_words, fraction_bbox

logger = logging.getLogger(__name__)

EXTENSIONS = {"application/pdf": "pdf", "image/png": "png", "image/jpeg": "jpg"}

UNSUPPORTED_TYPE = "Only PDF, PNG and JPG files are supported"
EMPTY_FILE = "The file is empty"
TOO_LARGE = f"The file is larger than {MAX_FILE_MB} MB"
TOO_MANY_PAGES = f"An attachment may have at most {MAX_PAGES_PER_ATTACHMENT} pages"
PASSWORD_PROTECTED = "The PDF is password protected"
PDF_UNREADABLE = "The PDF could not be opened"
IMAGE_UNREADABLE = "The image could not be opened"
PARSE_FAILED = "The attachment could not be read"


class VolumeStore(Protocol):
    def put(self, path: str, data: bytes) -> None: ...
    def get(self, path: str) -> bytes: ...
    def list(self, prefix: str) -> list[str]: ...
    def delete_prefix(self, prefix: str) -> None: ...


class PageParser(Protocol):
    def parse_pages(self, pages_folder: str) -> Any: ...


def _render_pdf(data: bytes, dpi: int) -> list[tuple[bytes, int, int]]:
    import pypdfium2

    try:
        pdf = pypdfium2.PdfDocument(data)
    except pypdfium2.PdfiumError as exc:
        message = PASSWORD_PROTECTED if "password" in str(exc).lower() else PDF_UNREADABLE
        raise ValueError(message) from exc
    try:
        if len(pdf) > MAX_PAGES_PER_ATTACHMENT:
            raise ValueError(TOO_MANY_PAGES)
        scale = dpi / 72
        pages: list[tuple[bytes, int, int]] = []
        for index in range(len(pdf)):
            page = pdf[index]
            try:
                width_pt, height_pt = page.get_size()
                image = page.render(scale=scale).to_pil()
            finally:
                page.close()
            # pdfium rounds the bitmap size up; crop the partial last row/column so the PNG is
            # round(points * dpi / 72) at the exact scale (595 x 842 pt at 150 dpi -> 1240 x 1754).
            target = (max(1, round(width_pt * scale)), max(1, round(height_pt * scale)))
            if image.size != target:
                image = image.crop(
                    (0, 0, min(target[0], image.width), min(target[1], image.height))
                )
            pages.append(_png_tuple(image))
        return pages
    finally:
        pdf.close()


def _png_tuple(image: Any) -> tuple[bytes, int, int]:
    buf = io.BytesIO()
    image.save(buf, "PNG")
    width_px, height_px = image.size
    return buf.getvalue(), width_px, height_px


def render_pages(
    data: bytes, media_type: str, dpi: int = RENDER_DPI
) -> list[tuple[bytes, int, int]]:
    """PDF -> one PNG per page via pypdfium2 at dpi; PNG/JPG -> the image re-encoded as PNG.

    Returns (png_bytes, width_px, height_px) per page. Raises ValueError for more than
    MAX_PAGES_PER_ATTACHMENT pages or an unreadable / password-protected file.
    """
    with source_locator.suppress_document_logs():  # no document content in library logs
        if media_type == "application/pdf":
            return _render_pdf(data, dpi)
        from PIL import Image, UnidentifiedImageError

        try:
            with Image.open(io.BytesIO(data)) as image:
                rgb = image.convert("RGB")
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError(IMAGE_UNREADABLE) from exc
        return [_png_tuple(rgb)]


class AttachmentService:
    def __init__(
        self, settings: Settings, volume_repository: VolumeStore, parse_repository: PageParser
    ) -> None:
        self._uploads = settings.VOLUME_UPLOADS.rstrip("/")
        self._volume = volume_repository
        self._parser = parse_repository

    def _folder(self, session_id: str, attachment_id: str) -> str:
        return f"{self._uploads}/{session_id}/{attachment_id}/"

    def ingest(
        self, session_id: str, attachment_id: str, file_name: str, media_type: str, data: bytes
    ) -> Attachment:
        """Validate type and size, store original, render pages, parse with AG-01, index words.

        Raises ValueError (type, empty, page count, unreadable file), PayloadTooLarge (size).
        """
        started = time.monotonic()
        if media_type not in ALLOWED_MEDIA_TYPES:
            raise ValueError(UNSUPPORTED_TYPE)
        if len(data) == 0:
            raise ValueError(EMPTY_FILE)
        if len(data) > MAX_FILE_MB * 1024 * 1024:
            raise PayloadTooLarge(TOO_LARGE)

        folder = self._folder(session_id, attachment_id)
        # Clear a previous upload under the same id so stale pages are never parsed.
        self._volume.delete_prefix(folder)
        self._volume.put(f"{folder}original.{EXTENSIONS[media_type]}", data)
        try:
            rendered = render_pages(data, media_type)
        except ValueError:
            self._volume.delete_prefix(folder)
            raise

        pages: list[Page] = []
        for page_no, (png, width_px, height_px) in enumerate(rendered, start=1):
            image_path = f"{folder}pages/p{page_no:03d}.png"
            self._volume.put(image_path, png)
            pages.append(
                Page(page_no=page_no, image_path=image_path, width_px=width_px, height_px=height_px)
            )

        attachment = Attachment(
            attachment_id=attachment_id,
            file_name=file_name,
            media_type=media_type,
            size_bytes=len(data),
            pages=pages,
        )
        self._parse(attachment, f"{folder}pages/")
        if media_type == "application/pdf":
            self._index_words(attachment, data)
        logger.info(
            "attachment ingested session=%s attachment=%s pages=%d elements=%d status=%s "
            "duration_ms=%d",
            session_id,
            attachment_id,
            len(pages),
            sum(len(p.elements) for p in pages),
            attachment.parse_status,
            int((time.monotonic() - started) * 1000),
        )
        return attachment

    def _parse(self, attachment: Attachment, pages_folder: str) -> None:
        try:
            parsed = self._parser.parse_pages(pages_folder)
        except UpstreamUnavailable:
            logger.warning("AG-01 parse failed attachment=%s", attachment.attachment_id)
            attachment.parse_status = "failed"
            attachment.error = PARSE_FAILED
            return
        failed = set(getattr(parsed, "failed_pages", []) or [])
        errors: list[str] = []
        for page in attachment.pages:
            file_name = f"p{page.page_no:03d}.png"
            if file_name in failed:
                errors.append(f"Page {page.page_no} could not be read")
                continue
            page.elements = [
                Element(
                    element_id=f"{attachment.attachment_id}.p{page.page_no}.e{index + 1}",
                    type=parsed_element.type,
                    content=parsed_element.content,
                    bbox=fraction_bbox(*parsed_element.coord, page.width_px, page.height_px),
                )
                for index, parsed_element in enumerate(parsed.get(file_name, []))
            ]
        attachment.parse_status = "parsed"
        attachment.error = "; ".join(errors) or None

    def _index_words(self, attachment: Attachment, data: bytes) -> None:
        try:
            words = extract_words(data, attachment.media_type)
        except Exception as exc:  # noqa: BLE001 - words only refine boxes; elements still work
            logger.warning(
                "word index failed attachment=%s error=%s",
                attachment.attachment_id,
                type(exc).__name__,
            )
            return
        for page in attachment.pages:
            page.words = words.get(page.page_no, [])
