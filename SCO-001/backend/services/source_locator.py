"""Segments for the LLM, message offsets, element bbox and pdfplumber word refinement."""

import io
import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Literal

from pydantic import BaseModel

from backend.models import Attachment, BBox, Element, Message, Page, Word

BBOX_EXPAND = 0.01
BBOX_DECIMALS = 4

# Document libraries log document content: pdfminer at DEBUG (every token) and in WARNINGs that
# quote document-supplied operands; TSD §11.2 forbids logging document content at any level.
DOCUMENT_LOGGER_NAMESPACES = ("pdfminer", "pdfplumber", "pypdfium2", "PIL")
_SUPPRESSED_LEVEL = logging.CRITICAL + 1


def _is_document_logger(name: str) -> bool:
    return any(name == ns or name.startswith(f"{ns}.") for ns in DOCUMENT_LOGGER_NAMESPACES)


class _DocumentLogFilter(logging.Filter):
    """Drops records emitted by a document-library logger (parent or any child)."""

    def filter(self, record: logging.LogRecord) -> bool:
        return not _is_document_logger(record.name)


_suppress_lock = threading.Lock()
_suppress_depth = 0
_saved_logger_state: dict[str, tuple[int, bool]] = {}
_filtered_handlers: list[logging.Handler] = []
_document_filter = _DocumentLogFilter()


def _start_suppression() -> None:
    for namespace in DOCUMENT_LOGGER_NAMESPACES:
        logging.getLogger(namespace)  # make sure every parent exists, so children inherit from it
    loggers = [
        logger
        for name, logger in list(logging.Logger.manager.loggerDict.items())
        if isinstance(logger, logging.Logger) and _is_document_logger(name)
    ]
    handlers: list[logging.Handler] = list(logging.root.handlers)
    for logger in loggers:
        _saved_logger_state[logger.name] = (logger.level, logger.disabled)
        logger.setLevel(_SUPPRESSED_LEVEL)  # children created later (level NOTSET) inherit this
        logger.disabled = True  # also covers explicitly configured existing children
        handlers.extend(logger.handlers)
    for handler in dict.fromkeys(handlers):  # dedupe, keep order
        # Propagation reaches ancestor handlers without checking the ancestors' level/disabled,
        # so a record from a child configured or created during the call is dropped here.
        handler.addFilter(_document_filter)
        _filtered_handlers.append(handler)


def _stop_suppression() -> None:
    for handler in _filtered_handlers:
        handler.removeFilter(_document_filter)
    _filtered_handlers.clear()
    for name, (level, disabled) in _saved_logger_state.items():
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.disabled = disabled
    _saved_logger_state.clear()


@contextmanager
def suppress_document_logs() -> Iterator[None]:
    """Silence pdfminer / pdfplumber / pypdfium2 / PIL logging (any level) for the duration.

    For every existing logger in those namespaces: level CRITICAL + 1 and ``disabled = True``,
    and a name-based filter on the root handlers and on those loggers' own handlers (records of
    children created or reconfigured during the call still propagate to them). Saved level and
    ``disabled`` state are restored in ``finally``. Re-entrant and thread-safe: the first caller
    installs, the last caller restores. Own ``backend.*`` records are untouched.
    """
    global _suppress_depth
    with _suppress_lock:
        _suppress_depth += 1
        if _suppress_depth == 1:
            _start_suppression()
    try:
        yield
    finally:
        with _suppress_lock:
            _suppress_depth -= 1
            if _suppress_depth == 0:
                _stop_suppression()


class Segment(BaseModel):
    segment_id: str
    kind: Literal["message", "element"]
    content: str
    message_id: str | None = None
    attachment_id: str | None = None
    page_no: int | None = None
    # Attachment header data for render_segments ("A1 = <file_name>, <n> pages").
    file_name: str | None = None
    page_count: int | None = None


def _normalise(text: str) -> str:
    return " ".join(text.split()).casefold()


def fraction_bbox(x0: float, y0: float, x1: float, y1: float, width: float, height: float) -> BBox:
    """Pixel/point box -> fractions of width/height, clamped to [0, 1], rounded to 4 decimals."""

    def frac(value: float, size: float) -> float:
        return round(min(max(value / size, 0.0), 1.0), BBOX_DECIMALS)

    return (frac(x0, width), frac(y0, height), frac(x1, width), frac(y1, height))


def extract_words(data: bytes, media_type: str) -> dict[int, list[Word]]:
    """pdfplumber words per page_no with bbox as fractions of page width/height.

    {} for images or PDFs without text layer; pages with no words are omitted.
    """
    if media_type != "application/pdf":
        return {}
    result: dict[int, list[Word]] = {}
    with suppress_document_logs():
        import pdfplumber

        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page_no, page in enumerate(pdf.pages, start=1):
                raw = page.extract_words(keep_blank_chars=False, use_text_flow=True)
                words = [
                    Word(
                        text=w["text"],
                        bbox=fraction_bbox(
                            w["x0"], w["top"], w["x1"], w["bottom"], page.width, page.height
                        ),
                    )
                    for w in raw
                ]
                if words:
                    result[page_no] = words
    return result


def build_segments(messages: list[Message], attachments: list[Attachment]) -> list[Segment]:
    """Messages M1.. first, then attachment elements A1.p1.e1.. in element order."""
    segments = [
        Segment(segment_id=m.message_id, kind="message", content=m.text, message_id=m.message_id)
        for m in messages
    ]
    for attachment in attachments:
        for page in attachment.pages:
            for element in page.elements:
                segments.append(
                    Segment(
                        segment_id=element.element_id,
                        kind="element",
                        content=element.content,
                        attachment_id=attachment.attachment_id,
                        page_no=page.page_no,
                        file_name=attachment.file_name,
                        page_count=len(attachment.pages),
                    )
                )
    return segments


def _one_line(text: str) -> str:
    return text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")


def render_segments(segments: list[Segment]) -> str:
    """One line per segment; each attachment starts with 'A1 = <file_name>, <n> pages'."""
    lines: list[str] = []
    current_attachment: str | None = None
    for segment in segments:
        if segment.kind == "element" and segment.attachment_id != current_attachment:
            current_attachment = segment.attachment_id
            lines.append(
                f"{segment.attachment_id} = {segment.file_name}, {segment.page_count} pages"
            )
        lines.append(f"{segment.segment_id}: {_one_line(segment.content)}")
    return "\n".join(lines)


def locate_message(text: str, quote: str) -> tuple[int, int] | None:
    """Case-insensitive, whitespace-collapsed search; (start, end) offsets in text, else None."""
    needle = _normalise(quote)
    if not needle:
        return None
    chars: list[str] = []
    origin: list[int] = []  # original index of each normalised character
    pending_space = False
    for index, char in enumerate(text):
        if char.isspace():
            pending_space = bool(chars)
            continue
        if pending_space:
            chars.append(" ")
            origin.append(index - 1)
            pending_space = False
        for folded in char.casefold():
            chars.append(folded)
            origin.append(index)
    found = "".join(chars).find(needle)
    if found < 0:
        return None
    return origin[found], origin[found + len(needle) - 1] + 1


def _inside(inner: BBox, outer: BBox, margin: float) -> bool:
    return (
        inner[0] >= outer[0] - margin
        and inner[1] >= outer[1] - margin
        and inner[2] <= outer[2] + margin
        and inner[3] <= outer[3] + margin
    )


def locate_element(page: Page, element: Element, quote: str) -> BBox:
    """Union bbox of consecutive page words equal to quote inside element.bbox (+0.01); else bbox."""
    needle = _normalise(quote)
    if not needle:
        return element.bbox
    words = page.words
    for start in range(len(words)):
        joined = ""
        for end in range(start, len(words)):
            joined = _normalise(f"{joined} {words[end].text}")
            if joined == needle:
                run = words[start : end + 1]
                if all(_inside(w.bbox, element.bbox, BBOX_EXPAND) for w in run):
                    return (
                        min(w.bbox[0] for w in run),
                        min(w.bbox[1] for w in run),
                        max(w.bbox[2] for w in run),
                        max(w.bbox[3] for w in run),
                    )
                break
            if not needle.startswith(joined):
                break
    return element.bbox
