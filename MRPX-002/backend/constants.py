"""Project constants for MRPX-002 (TSD §4)."""

PAGE_SIZE_DEFAULT = 50
PAGE_SIZE_MAX = 200
SORT_COLUMNS = ("movable_qty", "shortage_qty", "stock_qty", "weeks_late")
SORT_DIRECTIONS = ("asc", "desc")
SORT_DEFAULT = "movable_qty"
SORT_DIR_DEFAULT = "desc"
CRITICALITY_VALUES = ("A", "B", "C", "NONE")
CRITICALITY_NONE = "NONE"
UNKNOWN_PLANT_NAME = "UNKNOWN PLANT"
PLANT_CODE_PATTERN = r"^[A-Z0-9]{1,4}$"
COUNTRY_PATTERN = r"^[A-Z]{2}$"
PRODUCT_FAMILY_PATTERN = r"^[A-Z0-9]{1,4}$"
MATERIAL_PATTERN = r"^[A-Za-z0-9._/-]{1,40}$"
ERROR_UNAVAILABLE = "The transfer candidates could not be loaded. Try again."
REQUIRED_ENV = (
    "CATALOG",
    "SCHEMA_GOLD",
    "VIEW_TRANSFER_CANDIDATES",
    "DATABRICKS_HOST",
    "DATABRICKS_WAREHOUSE_ID",
)
