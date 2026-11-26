"""Project error types (TSD §11.2)."""


class ConflictError(Exception):
    """No result yet or state conflict; mapped to HTTP 409."""


class PayloadTooLarge(Exception):
    """Upload or message exceeds a size limit; mapped to HTTP 413."""


class UpstreamUnavailable(Exception):
    """A Databricks service (gateway, warehouse, volume) did not answer; mapped to HTTP 503."""
