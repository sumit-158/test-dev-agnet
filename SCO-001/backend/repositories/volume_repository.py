"""SRC-02 uploads volume over the Files API (``WorkspaceClient().files``)."""

import io
from typing import Any

from databricks.sdk.errors import DatabricksError, NotFound

from backend.errors import UpstreamUnavailable

STORAGE_UNAVAILABLE = "Storage is unavailable; try again"


class VolumeRepository:
    """put / get / list / delete_prefix on UC volume paths (``/Volumes/...``)."""

    def __init__(self, client: Any | None = None) -> None:
        self._client = client

    @property
    def _files(self) -> Any:
        if self._client is None:
            from databricks.sdk import WorkspaceClient

            self._client = WorkspaceClient()
        return self._client.files

    def put(self, path: str, data: bytes) -> None:
        try:
            self._files.upload(path, io.BytesIO(data), overwrite=True)
        except DatabricksError as exc:
            raise UpstreamUnavailable(STORAGE_UNAVAILABLE) from exc

    def get(self, path: str) -> bytes:
        try:
            return self._files.download(path).contents.read()
        except DatabricksError as exc:  # NotFound included
            raise UpstreamUnavailable(STORAGE_UNAVAILABLE) from exc

    def list(self, prefix: str) -> list[str]:
        """Every file path under the directory ``prefix``, recursively; [] when it does not exist."""
        result: list[str] = []
        pending = [prefix.rstrip("/")]
        try:
            while pending:
                directory = pending.pop()
                try:
                    entries = list(self._files.list_directory_contents(directory))
                except NotFound:
                    continue
                for entry in entries:
                    if entry.is_directory:
                        pending.append(entry.path.rstrip("/"))
                    else:
                        result.append(entry.path)
        except DatabricksError as exc:
            raise UpstreamUnavailable(STORAGE_UNAVAILABLE) from exc
        return sorted(result)

    def delete_prefix(self, prefix: str) -> None:
        """Delete every file under prefix; no error when empty."""
        for path in self.list(prefix):
            try:
                self._files.delete(path)
            except NotFound:
                continue
            except DatabricksError as exc:
                raise UpstreamUnavailable(STORAGE_UNAVAILABLE) from exc
