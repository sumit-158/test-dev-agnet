"""Project constants (TSD §5.2). Values are copied literally from the TSD."""

PIR_FIELDS = [
    "supplier",
    "material",
    "vendor_material_no",
    "plant",
    "purchasing_org",
    "country_of_origin",
    "lead_time_days",
    "standard_qty",
    "amount",
    "currency",
    "pricing_unit",
    "unit_of_measure",
    "valid_from",
    "valid_to",
]

SL_FIELDS = [
    "material",
    "vendor_material_no",
    "plant",
    "supplier",
    "purchasing_org",
    "valid_from",
    "valid_to",
    "fixed_vendor",
]

# PRD §4 labels, literally (TSD §5.2).
FIELD_LABELS = {
    "supplier": "Supplier",
    "material": "Vendor Material No.",
    "vendor_material_no": "Material",
    "plant": "Plant",
    "purchasing_org": "Purchasing Org.",
    "country_of_origin": "C/R. of Origin",
    "lead_time_days": "Pl. Deliv. Time",
    "standard_qty": "Standard Qty",
    "amount": "Amount",
    "currency": "Cond. Currency",
    "pricing_unit": "Pricing Unit",
    "unit_of_measure": "Unit of Measure",
    "valid_from": "Valid-From Date",
    "valid_to": "Valid To Date",
    "fixed_vendor": "Fixed Vendor",
}

REQUEST_TYPES = [
    "create_pir",
    "update_pir",
    "create_sl",
    "update_sl",
    "create_pir_and_sl",
    "not_pir_sl",
]

REQUEST_TYPE_LABELS = {
    "create_pir": "Create PIR",
    "update_pir": "Update PIR",
    "create_sl": "Create SL",
    "update_sl": "Update SL",
    "create_pir_and_sl": "Create PIR and SL",
    "not_pir_sl": "Not a PIR/SL request",
}

MESSAGE_KINDS = ["request_content", "correction", "other"]

ALLOWED_PURCHASING_ORG = {"3000", "3300", "8000"}
ALLOWED_PRICING_UNIT = {"1", "10", "100", "1000"}
ALLOWED_UOM = {"EA", "PC", "M", "KG", "L", "BOX", "SET", "ROLL"}

LEAD_TIME_MIN_DAYS = 1
LEAD_TIME_MAX_DAYS = 365

ALLOWED_MEDIA_TYPES = {"application/pdf", "image/png", "image/jpeg"}

MAX_FILE_MB = 20
MAX_PAGES_PER_ATTACHMENT = 20
MAX_ATTACHMENTS_PER_SESSION = 10
MAX_MESSAGE_CHARS = 20000

RENDER_DPI = 150

SESSION_TTL_HOURS = 8

LLM_TIMEOUT_SECONDS = 60
LLM_SCHEMA_RETRIES = 1
LLM_RATE_LIMIT_RETRIES = 1
LLM_RATE_LIMIT_WAIT_SECONDS = 2

# Frontend polling interval (mirrored in the frontend).
POLL_INTERVAL_MS = 2000
