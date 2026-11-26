"""v1/F-04 — render pages, parse attachments with AG-01 and index words."""

import copy
import io
import json
import logging
from pathlib import Path
from typing import Any

import pypdfium2
import pytest
from databricks.sdk.errors import DatabricksError, NotFound
from PIL import Image

from backend.config import Settings
from backend.errors import PayloadTooLarge, UpstreamUnavailable
from backend.models import Attachment, Element, Message, Page, Word
from backend.repositories.parse_repository import (
    PARSE_SQL,
    ParsedElement,
    ParsedPages,
    ParseRepository,
    parse_rows,
)
from backend.repositories.volume_repository import VolumeRepository
from backend.services.attachment_service import AttachmentService, render_pages
from backend.services.source_locator import (
    BBOX_EXPAND,
    Segment,
    build_segments,
    extract_words,
    locate_element,
    locate_message,
    render_segments,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
PDF_BYTES = (FIXTURES / "two_pages_text.pdf").read_bytes()
PARSE_ROWS = json.loads((FIXTURES / "parse_result_two_pages.json").read_text(encoding="utf-8"))
UPLOADS = "/Volumes/sandbox_others/sco_001_poc/uploads"


class FakeParsePages:
    """F-04 interface fake: ``parse_pages`` returns canned SQL rows run through ``parse_rows``."""

    def __init__(self, rows: list[dict[str, Any]] | None = None, error: Exception | None = None):
        self.rows = copy.deepcopy(PARSE_ROWS if rows is None else rows)
        self.error = error
        self.calls: list[str] = []

    def parse_pages(self, pages_folder: str) -> ParsedPages:
        self.calls.append(pages_folder)
        if self.error is not None:
            raise self.error
        return parse_rows(copy.deepcopy(self.rows))


def _png(width: int, height: int, mode: str = "RGB", fmt: str = "PNG") -> bytes:
    buf = io.BytesIO()
    Image.new(mode, (width, height), "white").save(buf, fmt)
    return buf.getvalue()


def _blank_pdf(pages: int) -> bytes:
    pdf = pypdfium2.PdfDocument.new()
    for _ in range(pages):
        pdf.new_page(595, 842)
    buf = io.BytesIO()
    pdf.save(buf)
    pdf.close()
    return buf.getvalue()


def _service(settings: Settings, volume: Any, parser: Any) -> AttachmentService:
    return AttachmentService(settings, volume_repository=volume, parse_repository=parser)


# --- acceptance criteria --------------------------------------------------------------------


def test_f04_ac1_ingest_pdf(settings, fake_volume_repository, fake_parse_repository, monkeypatch):
    # Configure the prescribed conftest fake with parse_result_two_pages.json (F-04 interface).
    calls: list[str] = []

    def parse_pages(pages_folder: str) -> ParsedPages:
        calls.append(pages_folder)
        return parse_rows(copy.deepcopy(PARSE_ROWS))

    monkeypatch.setattr(fake_parse_repository, "parse_pages", parse_pages, raising=False)
    parser = fake_parse_repository
    service = _service(settings, fake_volume_repository, parser)

    attachment = service.ingest("s1", "A1", "q.pdf", "application/pdf", PDF_BYTES)

    files = fake_volume_repository.files
    assert f"{UPLOADS}/s1/A1/original.pdf" in files
    assert files[f"{UPLOADS}/s1/A1/original.pdf"] == PDF_BYTES
    assert f"{UPLOADS}/s1/A1/pages/p001.png" in files
    assert f"{UPLOADS}/s1/A1/pages/p002.png" in files
    assert calls == [f"{UPLOADS}/s1/A1/pages/"]
    assert attachment.attachment_id == "A1"
    assert attachment.file_name == "q.pdf"
    assert attachment.size_bytes == len(PDF_BYTES)
    assert attachment.parse_status == "parsed"
    assert attachment.error is None
    assert len(attachment.pages) == 2
    first = attachment.pages[0]
    assert (first.page_no, first.width_px, first.height_px) == (1, 1240, 1754)
    assert first.image_path == f"{UPLOADS}/s1/A1/pages/p001.png"
    assert first.elements[0].element_id == "A1.p1.e1"
    assert first.elements[0].type == "text"
    assert first.elements[0].content == "Amount 7,000 KRW"
    assert first.elements[0].bbox == (0.0806, 0.114, 0.4194, 0.1368)
    second = attachment.pages[1]
    assert second.page_no == 2
    assert second.elements[0].element_id == "A1.p2.e1"
    assert second.elements[0].content == "Country of origin: DE"
    # words of the text layer are indexed per page
    assert [w.text for w in first.words] == ["Amount", "7,000", "KRW"]
    assert [w.text for w in second.words] == ["Country", "of", "origin:", "DE"]
    # stored page PNG is the one the boxes refer to
    stored = Image.open(io.BytesIO(files[f"{UPLOADS}/s1/A1/pages/p001.png"]))
    assert stored.format == "PNG"
    assert stored.size == (1240, 1754)


def test_f04_ac2_ingest_png(settings, fake_volume_repository):
    rows = [
        {
            "file_name": "p001.png",
            "parsed": {
                "document": {
                    "elements": [
                        {
                            "id": 0,
                            "type": "title",
                            "content": "Quotation",
                            "bbox": [{"coord": [0, 0, 800, 50], "page_id": 0}],
                        }
                    ]
                },
                "error_status": None,
            },
        }
    ]
    service = _service(settings, fake_volume_repository, FakeParsePages(rows))

    attachment = service.ingest("s1", "A2", "scan.png", "image/png", _png(800, 600))

    assert len(attachment.pages) == 1
    page = attachment.pages[0]
    assert page.width_px == 800
    assert page.height_px == 600
    assert page.elements[0].bbox == (0.0, 0.0, 1.0, 0.0833)
    assert page.elements[0].content == "Quotation"
    assert page.words == []
    assert f"{UPLOADS}/s1/A2/original.png" in fake_volume_repository.files
    assert f"{UPLOADS}/s1/A2/pages/p001.png" in fake_volume_repository.files


def test_f04_ac3_reject_type(settings, fake_volume_repository):
    parser = FakeParsePages()
    service = _service(settings, fake_volume_repository, parser)

    with pytest.raises(ValueError) as excinfo:
        service.ingest("s1", "A1", "parts.xls", "application/vnd.ms-excel", b"xls-bytes")

    assert str(excinfo.value) == "Only PDF, PNG and JPG files are supported"
    assert fake_volume_repository.files == {}
    assert parser.calls == []


def test_f04_ac4_segments_and_locate(golden_messages, golden_attachment):
    segments = build_segments(golden_messages, [golden_attachment])
    rendered = render_segments(segments)
    lines = rendered.split("\n")

    assert rendered.startswith("M1: Could you update PIR data")
    assert "A1 = BE25112601_RAIL-DIN 35MM X 7.5MM.pdf, 1 pages" in lines
    assert "A1.p1.e4: Country of origin: DE" in lines
    text = golden_messages[0].text
    first = text.index("7,000")
    assert locate_message(text, "7,000") == (first, first + 5)


# --- edge cases (§7) ------------------------------------------------------------------------


def test_f04_too_large_nothing_stored(settings, fake_volume_repository):
    service = _service(settings, fake_volume_repository, FakeParsePages())
    data = b"0" * (21 * 1024 * 1024)

    with pytest.raises(PayloadTooLarge) as excinfo:
        service.ingest("s1", "A1", "big.pdf", "application/pdf", data)

    assert str(excinfo.value) == "The file is larger than 20 MB"
    assert fake_volume_repository.files == {}


def test_f04_exactly_max_size_is_not_too_large(settings, fake_volume_repository):
    service = _service(settings, fake_volume_repository, FakeParsePages())
    png = _png(800, 600)
    data = png + b"\0" * (20 * 1024 * 1024 - len(png))  # trailing bytes after IEND are ignored

    attachment = service.ingest("s1", "A1", "q.png", "image/png", data)

    assert attachment.parse_status == "parsed"


def test_f04_too_many_pages_original_deleted(settings, fake_volume_repository):
    parser = FakeParsePages()
    service = _service(settings, fake_volume_repository, parser)
    fake_volume_repository.put(f"{UPLOADS}/s1/A10/original.pdf", b"other attachment")

    with pytest.raises(ValueError) as excinfo:
        service.ingest("s1", "A1", "long.pdf", "application/pdf", _blank_pdf(21))

    assert str(excinfo.value) == "An attachment may have at most 20 pages"
    assert fake_volume_repository.list(f"{UPLOADS}/s1/A1/") == []
    # the prefix is the attachment folder, not a string prefix of other attachment ids
    assert f"{UPLOADS}/s1/A10/original.pdf" in fake_volume_repository.files
    assert parser.calls == []


def test_f04_render_pages_page_limit():
    assert len(render_pages(_blank_pdf(20), "application/pdf")) == 20
    with pytest.raises(ValueError, match="An attachment may have at most 20 pages"):
        render_pages(_blank_pdf(21), "application/pdf")


def test_f04_original_stored_before_render(settings, monkeypatch):
    events: list[str] = []

    class RecordingVolume:
        def put(self, path, data):
            events.append(f"put {path.rsplit('/', 1)[-1]}")

        def get(self, path):
            raise FileNotFoundError(path)

        def list(self, prefix):
            return []

        def delete_prefix(self, prefix):
            events.append(f"delete {prefix}")

    service = _service(settings, RecordingVolume(), FakeParsePages())
    with pytest.raises(ValueError):
        service.ingest("s1", "A1", "long.pdf", "application/pdf", _blank_pdf(21))

    assert "put original.pdf" in events
    assert events[-1] == f"delete {UPLOADS}/s1/A1/"
    assert events.index("put original.pdf") < len(events) - 1


def test_f04_empty_file(settings, fake_volume_repository):
    service = _service(settings, fake_volume_repository, FakeParsePages())

    with pytest.raises(ValueError) as excinfo:
        service.ingest("s1", "A1", "q.pdf", "application/pdf", b"")

    assert str(excinfo.value) == "The file is empty"
    assert fake_volume_repository.files == {}


def test_f04_encrypted_pdf(settings, fake_volume_repository, monkeypatch):
    def locked(*args, **kwargs):
        raise pypdfium2.PdfiumError("Failed to load document (PDFium: Incorrect password error).")

    monkeypatch.setattr(pypdfium2, "PdfDocument", locked)
    service = _service(settings, fake_volume_repository, FakeParsePages())

    with pytest.raises(ValueError) as excinfo:
        service.ingest("s1", "A1", "locked.pdf", "application/pdf", PDF_BYTES)

    assert str(excinfo.value) == "The PDF is password protected"
    assert fake_volume_repository.list(f"{UPLOADS}/s1/A1/") == []


def test_f04_corrupt_pdf(settings, fake_volume_repository):
    service = _service(settings, fake_volume_repository, FakeParsePages())

    with pytest.raises(ValueError) as excinfo:
        service.ingest("s1", "A1", "broken.pdf", "application/pdf", b"not a pdf at all")

    assert str(excinfo.value) == "The PDF could not be opened"
    assert fake_volume_repository.list(f"{UPLOADS}/s1/A1/") == []


def test_f04_parse_failure_keeps_pages(settings, fake_volume_repository):
    parser = FakeParsePages(error=UpstreamUnavailable("warehouse down"))
    service = _service(settings, fake_volume_repository, parser)

    attachment = service.ingest("s1", "A1", "q.pdf", "application/pdf", PDF_BYTES)

    assert attachment.parse_status == "failed"
    assert attachment.error == "The attachment could not be read"
    assert [p.page_no for p in attachment.pages] == [1, 2]
    assert all(p.elements == [] for p in attachment.pages)
    assert f"{UPLOADS}/s1/A1/pages/p002.png" in fake_volume_repository.files


def test_f04_page_unreadable(settings, fake_volume_repository):
    rows = copy.deepcopy(PARSE_ROWS)
    rows[1]["parsed"]["error_status"] = [{"error_message": "could not parse", "page_id": 0}]
    service = _service(settings, fake_volume_repository, FakeParsePages(rows))

    attachment = service.ingest("s1", "A1", "q.pdf", "application/pdf", PDF_BYTES)

    assert attachment.parse_status == "parsed"
    assert attachment.error == "Page 2 could not be read"
    assert attachment.pages[0].elements[0].element_id == "A1.p1.e1"
    assert attachment.pages[1].elements == []


def test_f04_jpeg_upload_stored_as_jpg_and_png(settings, fake_volume_repository):
    rows = [{"file_name": "p001.png", "parsed": {"document": {"elements": []}}}]
    service = _service(settings, fake_volume_repository, FakeParsePages(rows))

    attachment = service.ingest("s1", "A3", "photo.jpg", "image/jpeg", _png(320, 200, fmt="JPEG"))

    assert f"{UPLOADS}/s1/A3/original.jpg" in fake_volume_repository.files
    page_png = fake_volume_repository.files[f"{UPLOADS}/s1/A3/pages/p001.png"]
    assert Image.open(io.BytesIO(page_png)).format == "PNG"
    assert (attachment.pages[0].width_px, attachment.pages[0].height_px) == (320, 200)
    assert attachment.parse_status == "parsed"


def test_f04_bbox_clamped_and_element_ids_in_page_order(settings, fake_volume_repository):
    rows = [
        {
            "file_name": "p001.png",
            "parsed": {
                "document": {
                    "elements": [
                        {
                            "id": 7,
                            "type": "text",
                            "content": "a",
                            "bbox": [{"coord": [-5, -1, 900, 700], "page_id": 0}],
                        },
                        {"id": 8, "type": "figure", "content": "no box"},
                        {
                            "id": 9,
                            "type": "text",
                            "content": "b",
                            "bbox": [{"coord": [400, 300, 800, 600], "page_id": 0}],
                        },
                    ]
                }
            },
        }
    ]
    service = _service(settings, fake_volume_repository, FakeParsePages(rows))

    attachment = service.ingest("s1", "A1", "x.png", "image/png", _png(800, 600))

    elements = attachment.pages[0].elements
    assert [e.element_id for e in elements] == ["A1.p1.e1", "A1.p1.e2"]
    assert elements[0].bbox == (0.0, 0.0, 1.0, 1.0)
    assert elements[1].bbox == (0.5, 0.5, 1.0, 1.0)


def test_f04_render_pages_pdf_size():
    pages = render_pages(PDF_BYTES, "application/pdf")
    assert [(w, h) for _, w, h in pages] == [(1240, 1754), (1240, 1754)]
    for png, w, h in pages:
        image = Image.open(io.BytesIO(png))
        assert image.format == "PNG"
        assert image.size == (w, h)


def test_f04_render_pages_image_rgba_converted():
    pages = render_pages(_png(10, 20, mode="RGBA"), "image/png")
    assert len(pages) == 1
    png, width, height = pages[0]
    assert (width, height) == (10, 20)
    assert Image.open(io.BytesIO(png)).mode == "RGB"


@pytest.fixture
def reset_third_party_log_levels():
    """Let every logger (pdfminer and pdfplumber included) emit DEBUG; restore levels after."""
    names = [
        name
        for name in list(logging.root.manager.loggerDict)
        if name.split(".")[0] in {"pdfminer", "pdfplumber", "PIL", "pypdfium2"}
    ] + ["pdfminer", "pdfplumber"]
    saved = {name: logging.getLogger(name).level for name in names}
    for name in names:
        logging.getLogger(name).setLevel(logging.NOTSET)
    yield
    for name, level in saved.items():
        logging.getLogger(name).setLevel(level)


def test_f04_no_message_text_or_content_logged(
    settings, fake_volume_repository, caplog, reset_third_party_log_levels
):
    caplog.set_level(logging.DEBUG)  # root logger: captures records of ALL loggers
    service = _service(settings, fake_volume_repository, FakeParsePages())

    attachment = service.ingest("s1", "A1", "q.pdf", "application/pdf", PDF_BYTES)

    assert attachment.pages[0].words  # words were extracted, so pdfminer actually ran
    logged = "\n".join(f"{r.name} {r.msg} {r.args!r} {r.getMessage()}" for r in caplog.records)
    assert "attachment=A1" in logged
    for secret in ("Amount", "7,000", "KRW", "Country of origin", "q.pdf"):
        assert secret not in logged, secret


DOC_LOGGER_NAMESPACES = ("pdfminer", "pdfplumber", "pypdfium2", "PIL")
MARKER = "SECRET-DOC-MARKER"


def _pdf_with_stream(stream: bytes) -> bytes:
    """Minimal one-page A4 PDF (Helvetica) whose page content stream is ``stream``."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"endstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out)


# Renderable PDF whose content makes pdfminer log a WARNING that quotes a document string
# ("Cannot set line width because b'SECRET-DOC-MARKER' is an invalid float value").
MARKER_PDF = _pdf_with_stream(
    b"(" + MARKER.encode() + b") w\nBT /F1 18 Tf 72 700 Td (Amount 7,000 KRW) Tj ET\n"
)


def _log_states() -> dict[str, tuple[int, bool, bool]]:
    return {
        name: (logger.level, logger.disabled, logger.propagate)
        for name, logger in logging.root.manager.loggerDict.items()
        if isinstance(logger, logging.Logger) and name.split(".")[0] in DOC_LOGGER_NAMESPACES
    }


_DEFAULT_LOG_STATE = (logging.NOTSET, False, True)


def _assert_restored(before: dict, after: dict) -> None:
    """Pre-existing loggers get their exact state back; loggers created meanwhile are default."""
    for name, state in after.items():
        assert state == before.get(name, _DEFAULT_LOG_STATE), name
    assert set(before) <= set(after)


def _logged(caplog) -> str:
    return "\n".join(f"{r.name} {r.msg} {r.args!r} {r.getMessage()}" for r in caplog.records)


@pytest.fixture
def restore_doc_loggers():
    """Restore level/disabled/propagate of every document-library logger after the test."""
    saved = _log_states()
    yield
    for name, (level, disabled, propagate) in saved.items():
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.disabled = disabled
        logger.propagate = propagate


def test_f04_explicit_debug_child_loggers_do_not_leak_content(
    settings, fake_volume_repository, caplog, restore_doc_loggers
):
    caplog.set_level(logging.DEBUG)  # root DEBUG: records of all loggers are captured
    for name in ("pdfminer", "pdfminer.psparser", "pdfminer.pdfinterp", "pdfminer.pdfpage"):
        logging.getLogger(name).setLevel(logging.DEBUG)
    for name in ("pdfplumber", "pdfplumber.page", "pypdfium2", "PIL", "PIL.PngImagePlugin"):
        logging.getLogger(name).setLevel(logging.DEBUG)
    service = _service(settings, fake_volume_repository, FakeParsePages())

    attachment = service.ingest("s1", "A1", "q.pdf", "application/pdf", PDF_BYTES)

    assert [w.text for w in attachment.pages[0].words] == ["Amount", "7,000", "KRW"]
    logged = _logged(caplog)
    assert "attachment=A1" in logged
    for secret in ("Amount", "7,000", "KRW", "Country of origin", "q.pdf"):
        assert secret not in logged, secret
    # the explicit configuration is restored after the call
    assert logging.getLogger("pdfminer.psparser").level == logging.DEBUG
    assert logging.getLogger("pdfplumber.page").level == logging.DEBUG


def test_f04_marker_pdf_warning_is_real_without_suppression(caplog, monkeypatch):
    """Proves the marker PDF really makes pdfminer log document content (control case)."""
    import contextlib

    from backend.services import source_locator

    monkeypatch.setattr(source_locator, "suppress_document_logs", contextlib.nullcontext)
    caplog.set_level(logging.INFO)
    assert render_pages(MARKER_PDF, "application/pdf")[0][1:] == (1240, 1754)

    words = source_locator.extract_words(MARKER_PDF, "application/pdf")

    assert [w.text for w in words[1]] == ["Amount", "7,000", "KRW"]
    assert any(
        r.name.startswith("pdfminer") and r.levelno == logging.WARNING and MARKER in r.getMessage()
        for r in caplog.records
    )


def test_f04_pdfminer_warning_with_document_string_not_logged(
    settings, fake_volume_repository, caplog
):
    caplog.set_level(logging.INFO)  # app logging at INFO
    service = _service(settings, fake_volume_repository, FakeParsePages())

    attachment = service.ingest("s1", "A1", "q.pdf", "application/pdf", MARKER_PDF)

    assert [w.text for w in attachment.pages[0].words] == ["Amount", "7,000", "KRW"]
    logged = _logged(caplog)
    assert "attachment=A1" in logged
    assert MARKER not in logged
    assert "Amount" not in logged


def test_f04_suppress_document_logs_restores_state_and_covers_new_children(
    caplog, restore_doc_loggers
):
    from backend.services.source_locator import suppress_document_logs

    caplog.set_level(logging.DEBUG)
    logging.getLogger("pdfminer.psparser").setLevel(logging.DEBUG)
    logging.getLogger("PIL").disabled = False
    before = _log_states()
    backend_logger = logging.getLogger("backend.services.attachment_service")

    with suppress_document_logs():
        child = logging.getLogger("pdfminer.created_during_call")  # lazily created child
        child.warning("child %s", MARKER)
        logging.getLogger("pdfminer.psparser").debug("psparser %s", MARKER)
        logging.getLogger("pdfplumber").error("plumber %s", MARKER)
        logging.getLogger("pypdfium2").critical("pdfium %s", MARKER)
        logging.getLogger("PIL.Image").warning("pil %s", MARKER)
        backend_logger.warning("own warning attachment=%s", "A9")

    assert MARKER not in _logged(caplog)
    assert "own warning attachment=A9" in caplog.text
    after = _log_states()
    assert "pdfminer.created_during_call" in after
    _assert_restored(before, after)
    for filterer in [logging.root, *logging.root.handlers]:
        assert not any(type(f).__name__ == "_DocumentLogFilter" for f in filterer.filters)
    caplog.clear()
    logging.getLogger("pdfminer.psparser").debug("after %s", "visible")
    assert "after visible" in caplog.text


def test_f04_suppress_document_logs_restores_on_error(restore_doc_loggers):
    from backend.services.source_locator import suppress_document_logs

    logging.getLogger("pdfminer.pdfinterp").setLevel(logging.DEBUG)
    before = _log_states()
    with pytest.raises(RuntimeError), suppress_document_logs():
        assert logging.getLogger("pdfminer.pdfinterp").disabled
        raise RuntimeError("boom")
    _assert_restored(before, _log_states())
    assert logging.getLogger("pdfminer.pdfinterp").level == logging.DEBUG


def test_f04_word_index_failure_still_logs_own_warning(
    settings, fake_volume_repository, caplog, monkeypatch
):
    from backend.services import attachment_service

    def broken(data, media_type):
        raise KeyError("x")

    monkeypatch.setattr(attachment_service, "extract_words", broken)
    caplog.set_level(logging.INFO)
    service = _service(settings, fake_volume_repository, FakeParsePages())

    service.ingest("s1", "A1", "q.pdf", "application/pdf", PDF_BYTES)

    assert "word index failed attachment=A1 error=KeyError" in caplog.text


# --- parse_rows / ParseRepository -----------------------------------------------------------


def test_f04_parse_rows_fixture():
    result = parse_rows(PARSE_ROWS)
    assert dict(result) == {
        "p001.png": [
            ParsedElement(id=0, type="text", content="Amount 7,000 KRW", coord=[100, 200, 520, 240])
        ],
        "p002.png": [
            ParsedElement(
                id=0, type="text", content="Country of origin: DE", coord=[100, 300, 560, 340]
            )
        ],
    }
    assert result.failed_pages == []


def test_f04_parse_rows_json_string_and_tuple_rows():
    rows = [(row["file_name"], json.dumps(row["parsed"])) for row in PARSE_ROWS]
    result = parse_rows(rows)
    assert result["p001.png"][0].content == "Amount 7,000 KRW"
    assert result["p002.png"][0].coord == [100, 300, 560, 340]


def test_f04_parse_rows_error_status_page():
    rows = copy.deepcopy(PARSE_ROWS)
    rows[1]["parsed"]["error_status"] = [{"error_message": "bad page"}]
    result = parse_rows(rows)
    assert result["p001.png"][0].id == 0
    assert result["p002.png"] == []
    assert result.failed_pages == ["p002.png"]


def test_f04_parse_rows_invalid_json_is_page_error_and_elements_without_bbox_skipped():
    rows = [
        {"file_name": "p001.png", "parsed": "{not json"},
        {
            "file_name": "p002.png",
            "parsed": {
                "document": {
                    "elements": [
                        {"id": 0, "type": "figure", "content": "logo"},
                        {"id": 1, "type": "text", "content": "x", "bbox": []},
                        {
                            "id": 2,
                            "type": "text",
                            "content": "y",
                            "bbox": [{"coord": [1, 2, 3, 4], "page_id": 0}],
                        },
                    ]
                },
                "error_status": None,
            },
        },
    ]
    result = parse_rows(rows)
    assert result["p001.png"] == []
    assert result.failed_pages == ["p001.png"]
    assert result["p002.png"] == [ParsedElement(id=2, type="text", content="y", coord=[1, 2, 3, 4])]


@pytest.mark.parametrize("status", [[], {}, "", [{"error_message": "bad"}], "FAILED"])
def test_f04_parse_rows_non_null_error_status_is_page_error(status):
    rows = copy.deepcopy(PARSE_ROWS)
    rows[0]["parsed"]["error_status"] = status
    result = parse_rows(rows)
    assert result["p001.png"] == []
    assert result.failed_pages == ["p001.png"]
    assert result["p002.png"][0].content == "Country of origin: DE"


def test_f04_parse_rows_null_or_absent_error_status_is_success():
    rows = copy.deepcopy(PARSE_ROWS)
    del rows[1]["parsed"]["error_status"]
    result = parse_rows(rows)  # rows[0] has error_status null
    assert result.failed_pages == []
    assert len(result["p001.png"]) == 1
    assert len(result["p002.png"]) == 1


class _FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self.description = [("file_name",), ("parsed",)]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.conn.executed.append((sql, params))
        if self.conn.error is not None:
            raise self.conn.error

    def fetchall(self):
        return [(row["file_name"], json.dumps(row["parsed"])) for row in PARSE_ROWS]


class _FakeConnection:
    def __init__(self, error=None):
        self.error = error
        self.executed: list[tuple[str, Any]] = []
        self.closed = False

    def cursor(self):
        return _FakeCursor(self)

    def close(self):
        self.closed = True


def test_f04_parse_repository_runs_one_query(settings):
    conn = _FakeConnection()
    repo = ParseRepository(settings, connect=lambda: conn)

    result = repo.parse_pages(f"{UPLOADS}/s1/A1/pages/")

    assert len(conn.executed) == 1
    sql, params = conn.executed[0]
    assert sql == PARSE_SQL
    assert ":pages_folder" in sql and "ai_parse_document(content)" in sql
    assert "SELECT *" not in sql.upper()
    assert params == {"pages_folder": f"{UPLOADS}/s1/A1/pages/"}
    assert conn.closed
    assert result["p001.png"][0].content == "Amount 7,000 KRW"


def test_f04_parse_repository_sql_error_is_upstream_unavailable(settings):
    conn = _FakeConnection(error=RuntimeError("[AI_FUNCTION_ERROR] boom"))
    repo = ParseRepository(settings, connect=lambda: conn)

    with pytest.raises(UpstreamUnavailable):
        repo.parse_pages(f"{UPLOADS}/s1/A1/pages/")
    assert conn.closed


def test_f04_parse_repository_connect_error_is_upstream_unavailable(settings):
    def broken():
        raise OSError("no route")

    with pytest.raises(UpstreamUnavailable):
        ParseRepository(settings, connect=broken).parse_pages(f"{UPLOADS}/s1/A1/pages/")


# --- VolumeRepository -----------------------------------------------------------------------


class _Entry:
    def __init__(self, path, is_directory):
        self.path = path
        self.is_directory = is_directory


class _Download:
    def __init__(self, data):
        self.contents = io.BytesIO(data)


class _FakeFilesApi:
    def __init__(self):
        self.files: dict[str, bytes] = {}
        self.fail = False

    def _check(self):
        if self.fail:
            raise DatabricksError("service unavailable")

    def upload(self, path, contents, overwrite=False):
        self._check()
        self.files[path] = contents.read()
        self.overwrite = overwrite

    def download(self, path):
        self._check()
        if path not in self.files:
            raise NotFound("not found")
        return _Download(self.files[path])

    def list_directory_contents(self, directory):
        self._check()
        directory = directory.rstrip("/")
        children = {}
        for path in self.files:
            if path.startswith(directory + "/"):
                rest = path[len(directory) + 1 :]
                head = rest.split("/", 1)[0]
                children[f"{directory}/{head}"] = "/" in rest
        if not children:
            raise NotFound(f"{directory} not found")
        return [_Entry(p + ("/" if d else ""), d) for p, d in children.items()]

    def delete(self, path):
        self._check()
        del self.files[path]


class _FakeClient:
    def __init__(self):
        self.files = _FakeFilesApi()


def test_f04_volume_repository_roundtrip():
    client = _FakeClient()
    repo = VolumeRepository(client=client)
    base = f"{UPLOADS}/s1/A1"

    repo.put(f"{base}/original.pdf", b"pdf")
    repo.put(f"{base}/pages/p001.png", b"p1")
    repo.put(f"{base}/pages/p002.png", b"p2")
    repo.put(f"{UPLOADS}/s1/A10/original.pdf", b"other")

    assert client.files.overwrite is True
    assert repo.get(f"{base}/pages/p002.png") == b"p2"
    assert repo.list(f"{base}/") == [
        f"{base}/original.pdf",
        f"{base}/pages/p001.png",
        f"{base}/pages/p002.png",
    ]
    repo.delete_prefix(f"{base}/")
    assert repo.list(f"{base}/") == []
    assert list(client.files.files) == [f"{UPLOADS}/s1/A10/original.pdf"]


def test_f04_volume_repository_delete_missing_prefix_is_noop():
    repo = VolumeRepository(client=_FakeClient())
    repo.delete_prefix(f"{UPLOADS}/nothing/here/")
    assert repo.list(f"{UPLOADS}/nothing/here/") == []


def test_f04_volume_repository_get_missing_is_upstream_unavailable():
    with pytest.raises(UpstreamUnavailable) as excinfo:
        VolumeRepository(client=_FakeClient()).get(f"{UPLOADS}/s1/A1/original.pdf")
    assert str(excinfo.value) == "Storage is unavailable; try again"


def test_f04_volume_repository_errors_are_upstream_unavailable():
    client = _FakeClient()
    client.files.fail = True
    repo = VolumeRepository(client=client)
    for call in (
        lambda: repo.put("/Volumes/x/y", b"1"),
        lambda: repo.get("/Volumes/x/y"),
        lambda: repo.list("/Volumes/x/"),
        lambda: repo.delete_prefix("/Volumes/x/"),
    ):
        with pytest.raises(UpstreamUnavailable) as excinfo:
            call()
        assert str(excinfo.value) == "Storage is unavailable; try again"


# --- source_locator -------------------------------------------------------------------------


def test_f04_extract_words_fractions():
    words = extract_words(PDF_BYTES, "application/pdf")
    assert sorted(words) == [1, 2]
    assert [w.text for w in words[2]] == ["Country", "of", "origin:", "DE"]
    for page_words in words.values():
        for word in page_words:
            x0, y0, x1, y1 = word.bbox
            assert 0.0 <= x0 < x1 <= 1.0
            assert 0.0 <= y0 < y1 <= 1.0
    # "Amount" starts at x = 72 pt on a 595 pt page
    assert words[1][0].bbox[0] == round(72 / 595, 4)


def test_f04_extract_words_images_and_no_text_layer():
    assert extract_words(_png(10, 10), "image/png") == {}
    assert extract_words(_png(10, 10, fmt="JPEG"), "image/jpeg") == {}
    assert extract_words(_blank_pdf(2), "application/pdf") == {}


def test_f04_locate_message_cases():
    assert locate_message("Amount 7,000 KRW", "7,000") == (7, 12)
    assert locate_message("abc", "xyz") is None
    assert locate_message("abc", "   ") is None
    text = "Country of\n   ORIGIN:\tDE"
    start, end = locate_message(text, "origin: de")
    assert text[start:end] == "ORIGIN:\tDE"
    start, end = locate_message("  lead   time  1 week", "LEAD TIME 1")
    assert (start, end) == (2, 16)


def _page_with_words() -> tuple[Page, Element]:
    element = Element(
        element_id="A1.p1.e1",
        type="text",
        content="Amount 7,000 KRW",
        bbox=(0.10, 0.10, 0.50, 0.15),
    )
    words = [
        Word(text="Amount", bbox=(0.11, 0.11, 0.20, 0.14)),
        Word(text="7,000", bbox=(0.21, 0.11, 0.30, 0.14)),
        Word(text="KRW", bbox=(0.31, 0.11, 0.40, 0.14)),
        Word(text="7,000", bbox=(0.21, 0.80, 0.30, 0.84)),  # same text outside the element
    ]
    page = Page(page_no=1, width_px=1240, height_px=1754, elements=[element], words=words)
    return page, element


def test_f04_locate_element_refines_to_words():
    page, element = _page_with_words()
    assert locate_element(page, element, "7,000") == (0.21, 0.11, 0.30, 0.14)
    assert locate_element(page, element, "7,000  krw") == (0.21, 0.11, 0.40, 0.14)


def test_f04_locate_element_falls_back_to_element_bbox():
    page, element = _page_with_words()
    assert locate_element(page, element, "7,000 EUR") == element.bbox
    assert locate_element(page, element, "") == element.bbox
    scanned = Page(page_no=1, width_px=1240, height_px=1754, elements=[element], words=[])
    assert locate_element(scanned, element, "7,000") == element.bbox


def test_f04_locate_element_uses_expansion_margin():
    assert BBOX_EXPAND == 0.01
    element = Element(element_id="A1.p1.e1", type="text", content="KRW", bbox=(0.2, 0.2, 0.3, 0.3))
    inside = Word(text="KRW", bbox=(0.195, 0.195, 0.305, 0.305))
    page = Page(page_no=1, width_px=10, height_px=10, elements=[element], words=[inside])
    assert locate_element(page, element, "KRW") == inside.bbox
    outside = Word(text="KRW", bbox=(0.18, 0.2, 0.3, 0.3))
    page = Page(page_no=1, width_px=10, height_px=10, elements=[element], words=[outside])
    assert locate_element(page, element, "KRW") == element.bbox


def test_f04_build_and_render_segments_order_and_newlines():
    messages = [
        Message(message_id="M1", role="user", text="first\nline"),
        Message(message_id="M2", role="user", text="second"),
    ]
    attachment = Attachment(
        attachment_id="A1",
        file_name="q.pdf",
        media_type="application/pdf",
        parse_status="parsed",
        pages=[
            Page(
                page_no=1,
                width_px=1,
                height_px=1,
                elements=[
                    Element(element_id="A1.p1.e1", type="text", content="a\nb", bbox=(0, 0, 1, 1)),
                    Element(element_id="A1.p1.e2", type="text", content="c", bbox=(0, 0, 1, 1)),
                ],
            ),
            Page(
                page_no=2,
                width_px=1,
                height_px=1,
                elements=[
                    Element(element_id="A1.p2.e1", type="text", content="d", bbox=(0, 0, 1, 1)),
                ],
            ),
        ],
    )
    segments = build_segments(messages, [attachment])

    assert [s.segment_id for s in segments] == ["M1", "M2", "A1.p1.e1", "A1.p1.e2", "A1.p2.e1"]
    first = segments[0]
    assert isinstance(first, Segment)
    assert (first.kind, first.content, first.message_id, first.attachment_id, first.page_no) == (
        "message",
        "first\nline",
        "M1",
        None,
        None,
    )
    assert (segments[3].kind, segments[3].attachment_id, segments[3].page_no) == (
        "element",
        "A1",
        1,
    )
    assert segments[4].page_no == 2
    assert render_segments(segments).split("\n") == [
        "M1: first line",
        "M2: second",
        "A1 = q.pdf, 2 pages",
        "A1.p1.e1: a b",
        "A1.p1.e2: c",
        "A1.p2.e1: d",
    ]
