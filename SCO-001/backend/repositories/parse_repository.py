"""AG-01 document parsing: ``ai_parse_document`` over a pages folder, one SQL query per attachment."""

import json
import logging
import time
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from pydantic import BaseModel

from backend.config import Settings
from backend.errors import UpstreamUnavailable

logger = logging.getLogger(__name__)

PARSE_SQL = """SELECT regexp_extract(path, '([^/]+)$', 1) AS file_name,
       to_json(ai_parse_document(content)) AS parsed
FROM read_files(:pages_folder, format => 'binaryFile')"""


class ParsedElement(BaseModel):
    """One ``document.elements[]`` entry; ``coord`` is ``[x0, y0, x1, y1]`` in PNG pixels."""

    id: int
    type: str
    content: str
    coord: list[float]


class ParsedPages(dict[str, list[ParsedElement]]):
    """``parse_pages`` result: file name (``p001.png``) -> elements.

    ``failed_pages`` lists the file names whose ``error_status`` was set (or whose output could not
    be read); those pages map to ``[]``.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.failed_pages: list[str] = []


def _row_values(row: Any) -> tuple[str, Any]:
    if isinstance(row, Mapping):
        return str(row["file_name"]), row["parsed"]
    return str(row[0]), row[1]


def _elements(document: Mapping[str, Any]) -> list[ParsedElement]:
    elements: list[ParsedElement] = []
    for raw in document.get("elements") or []:
        boxes = raw.get("bbox") or []
        coord = boxes[0].get("coord") if boxes and isinstance(boxes[0], Mapping) else None
        if not coord or len(coord) != 4:
            continue
        elements.append(
            ParsedElement(
                id=int(raw.get("id", len(elements))),
                type=str(raw.get("type") or "text"),
                content=str(raw.get("content") or ""),
                coord=[float(c) for c in coord],
            )
        )
    return elements


def parse_rows(rows: Iterable[Any]) -> ParsedPages:
    """Turn the SQL rows ``(file_name, parsed)`` into elements per page file name.

    ``parsed`` is the ``to_json(ai_parse_document(...))`` string (a decoded object is accepted too).
    A page whose ``error_status`` is present and not null (or with unreadable JSON) gets ``[]`` and is listed in
    ``failed_pages``. Elements without ``bbox`` are skipped.
    """
    result = ParsedPages()
    for row in rows:
        file_name, parsed = _row_values(row)
        try:
            payload = json.loads(parsed) if isinstance(parsed, str | bytes) else parsed
        except ValueError:
            payload = None
        # Contract: an error_status that is present and not null (even [] / {} / "") fails the page.
        if not isinstance(payload, Mapping) or payload.get("error_status") is not None:
            result[file_name] = []
            result.failed_pages.append(file_name)
            continue
        result[file_name] = _elements(payload.get("document") or {})
    ordered = ParsedPages((name, result[name]) for name in sorted(result))
    ordered.failed_pages = sorted(result.failed_pages)
    return ordered


class ParseRepository:
    """Runs AG-01 on the serverless SQL warehouse ``settings.WAREHOUSE_ID``."""

    def __init__(self, settings: Settings, connect: Callable[[], Any] | None = None) -> None:
        self._warehouse_id = settings.WAREHOUSE_ID
        self._connect = connect or self._default_connect

    def _default_connect(self) -> Any:
        # Lazy imports: unit tests never need a workspace. Host and credentials come from the SDK
        # Config (env / profile / app service principal); the token is never read or logged here.
        from databricks import sql as dbsql
        from databricks.sdk.core import Config

        config = Config()
        host = (config.host or "").removeprefix("https://").removeprefix("http://").rstrip("/")
        return dbsql.connect(
            server_hostname=host,
            http_path=f"/sql/1.0/warehouses/{self._warehouse_id}",
            credentials_provider=lambda: config.authenticate,
        )

    def parse_pages(self, pages_folder: str) -> ParsedPages:
        """Run the AG-01 SQL on the warehouse; key = file name p001.png.

        Raises UpstreamUnavailable on any connection or SQL error.
        """
        started = time.monotonic()
        connection = None
        try:
            connection = self._connect()
            with connection.cursor() as cursor:
                cursor.execute(PARSE_SQL, {"pages_folder": pages_folder})
                rows = cursor.fetchall() if cursor.description is not None else []
        except Exception as exc:
            logger.warning("ai_parse_document failed: %s", type(exc).__name__)
            raise UpstreamUnavailable("The document parser is unavailable; try again") from exc
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:  # noqa: BLE001 - closing must not hide the result
                    logger.debug("closing the warehouse connection failed")
        result = parse_rows(rows)
        logger.info(
            "ai_parse_document pages=%d failed_pages=%d elements=%d duration_ms=%d",
            len(result),
            len(result.failed_pages),
            sum(len(v) for v in result.values()),
            int((time.monotonic() - started) * 1000),
        )
        return result
