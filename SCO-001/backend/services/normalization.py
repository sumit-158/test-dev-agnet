"""Level-0 normalisation rules N-01..N-15 (v1/F-07, TSD §7).

Pure logic: no I/O, no model calls, no logging (values, quotes and message text are never logged,
TSD §11.2). Every rule function returns the normalised value (``None`` = no value) or raises
``RuleViolation`` with the issue text; ``normalize`` turns that into a ``Candidate`` copy.
No defaults are ever filled in (PRD D-1).
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation

from backend.constants import (
    ALLOWED_PRICING_UNIT,
    ALLOWED_PURCHASING_ORG,
    ALLOWED_UOM,
    LEAD_TIME_MAX_DAYS,
    LEAD_TIME_MIN_DAYS,
    PIR_FIELDS,
    SL_FIELDS,
)
from backend.models import Candidate, Message

SIGNATURE_LINES = 8
UOM_SYNONYMS = {
    "PCS": "PC",
    "EACH": "EA",
    "PIECE": "PC",
    "PIECES": "PC",
    "METER": "M",
    "METRE": "M",
    "KGS": "KG",
}
CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "¥": "JPY", "₩": "KRW"}

ISSUE_EMPTY = "Empty value"
ISSUE_PERSONAL_DATA = "Personal data is not extracted"
ISSUE_SIGNATURE = "Taken from a signature"
ISSUE_PART_NUMBER = "Not a part number pattern"
ISSUE_DESCRIPTION = "Description equals the part number"
ISSUE_PLANT = "Not a plant code"
ISSUE_COUNTRY = "Not a country code"
ISSUE_LEAD_TIME = "Not a lead time"
ISSUE_LEAD_TIME_RANGE = (
    f"Lead time must be between {LEAD_TIME_MIN_DAYS} and {LEAD_TIME_MAX_DAYS} days"
)
ISSUE_STANDARD_QTY = "Standard quantity must be a whole number of at least 1"
ISSUE_AMOUNT = "Not an amount"
ISSUE_AMOUNT_NEGATIVE = "Amount must be positive"
ISSUE_CURRENCY = "Not a currency code"
ISSUE_PRICING_UNIT = "Not an allowed pricing unit"
ISSUE_UOM = "Not an allowed unit of measure"
ISSUE_DATE = "Not a date"
ISSUE_AMBIGUOUS_DATE = "Ambiguous date order"
ISSUE_FIXED_VENDOR = "No fixed or sole source wording"

PHONE_PATTERN = re.compile(r"(?:\d[\s\-.]?){7,}")
# Dashed N-02 part numbers; these and N-13 dates are not phone numbers (see _contains_phone).
_DASHED_PART_NUMBER = re.compile(r"\d{4}-\d{3}-\d{2}|\d{4}-\d{5}")
_PART_NUMBER = re.compile(r"\d{4}-\d{3}-\d{2}|\d{4}-\d{5}|\d{7,10}")
# Phone check only. Human-approved deviation from contract §6 (recorded for the Planner): dates
# keep "Not a date"; N-13 accepts real dates only, so no phone number passes a date field.
_N15_EXEMPT_FIELDS = {"material", "amount", "standard_qty", "valid_from", "valid_to"}
_DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%Y.%m.%d")
_SLASH_FORMATS = ("%d/%m/%Y", "%m/%d/%Y")
_NAMED_MONTH_FORMATS = ("%d %B %Y", "%B %d, %Y")


class RuleViolation(ValueError):
    """A candidate fails a rule; ``str(error)`` is the issue shown to the steward."""


@dataclass
class NormalizationContext:
    signature_lines: dict[str, set[str]] = field(default_factory=dict)


# --------------------------------------------------------------------------- rule functions


def n01_supplier(raw: str) -> str | None:
    """N-01: a 5-digit code as is; otherwise the supplier name as written, trimmed."""
    value = raw.strip()
    if re.fullmatch(r"\d{5}", value):
        return value
    return value or None


def n02_material(raw: str) -> str | None:
    value = raw.strip()
    if not _PART_NUMBER.fullmatch(value):
        raise RuleViolation(ISSUE_PART_NUMBER)
    return value


def n03_vendor_material_no(raw: str) -> str | None:
    value = " ".join(raw.split())
    if _PART_NUMBER.fullmatch(value):
        raise RuleViolation(ISSUE_DESCRIPTION)
    return value or None


def n04_plant(raw: str) -> str | None:
    value = raw.strip()
    if not re.fullmatch(r"\d{4}", value):
        raise RuleViolation(ISSUE_PLANT)
    return value


def n05_purchasing_org(raw: str) -> str | None:
    digits = re.sub(r"\D", "", raw)
    if digits not in ALLOWED_PURCHASING_ORG or raw.strip() != digits:
        raise RuleViolation(f'"{raw.strip()}" is not a purchasing organisation (3000, 3300, 8000)')
    return digits


def n06_country_of_origin(raw: str) -> str | None:
    """N-06 format check; the signature-block drop is applied in ``build_result``."""
    value = raw.strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", value):
        raise RuleViolation(ISSUE_COUNTRY)
    return value


def _lead_time(raw: str) -> tuple[str, str | None]:
    """(days, computation); computation is set when weeks were converted."""
    value = raw.strip()
    weeks = re.fullmatch(r"(\d+)\s*(weeks?|wks?|w)", value, re.IGNORECASE)
    if weeks:
        days, computation = int(weeks[1]) * 7, f"{weeks[1]} weeks × 7"
    else:
        plain = re.fullmatch(r"(\d+)\s*(days?|d)?", value, re.IGNORECASE)
        if not plain:
            raise RuleViolation(ISSUE_LEAD_TIME)
        days, computation = int(plain[1]), None
    if not LEAD_TIME_MIN_DAYS <= days <= LEAD_TIME_MAX_DAYS:
        raise RuleViolation(ISSUE_LEAD_TIME_RANGE)
    return str(days), computation


def n07_lead_time_days(raw: str) -> str | None:
    return _lead_time(raw)[0]


def n08_standard_qty(raw: str) -> str | None:
    try:
        number = Decimal(raw.strip())
    except InvalidOperation:
        raise RuleViolation(ISSUE_STANDARD_QTY) from None
    if not number.is_finite() or number != number.to_integral_value() or number < 1:
        raise RuleViolation(ISSUE_STANDARD_QTY)
    return str(int(number))


def _drop_group_separators(value: str, sep: str) -> str:
    """Only one kind of separator: thousands when every group has 3 digits, else decimal."""
    if re.fullmatch(rf"\d{{1,3}}(?:{re.escape(sep)}\d{{3}})+", value):
        return value.replace(sep, "")
    return value.replace(sep, ".")


def n09_amount(raw: str) -> str | None:
    value = re.sub(r"[^\d.,\-]", "", raw)
    negative = value.startswith("-")
    value = value.lstrip("-")
    if "," in value and "." in value:
        decimal_sep = "," if value.rfind(",") > value.rfind(".") else "."
        other = "." if decimal_sep == "," else ","
        value = value.replace(other, "").replace(decimal_sep, ".")
    elif "," in value:
        value = _drop_group_separators(value, ",")
    elif "." in value:
        value = _drop_group_separators(value, ".")
    if not re.fullmatch(r"\d+(?:\.\d+)?|\.\d+", value):
        raise RuleViolation(ISSUE_AMOUNT)
    number = Decimal(value)
    if negative and number != 0:
        raise RuleViolation(ISSUE_AMOUNT_NEGATIVE)
    return format(number, "f")


def n10_currency(raw: str) -> str | None:
    value = raw.strip()
    if value in CURRENCY_SYMBOLS:
        return CURRENCY_SYMBOLS[value]
    if not re.fullmatch(r"[A-Za-z]{3}", value):
        raise RuleViolation(ISSUE_CURRENCY)
    return value.upper()


def n11_pricing_unit(raw: str) -> str | None:
    value = raw.strip()
    if value not in ALLOWED_PRICING_UNIT:
        raise RuleViolation(ISSUE_PRICING_UNIT)
    return value


def n12_unit_of_measure(raw: str) -> str | None:
    value = raw.strip().upper()
    value = UOM_SYNONYMS.get(value, value)
    if value not in ALLOWED_UOM:
        raise RuleViolation(ISSUE_UOM)
    return value


def _parse(value: str, fmt: str) -> datetime | None:
    try:
        return datetime.strptime(value, fmt)
    except ValueError:
        return None


def _iso(day: datetime) -> str:
    """Zero-padded ISO date (strftime drops the leading zeros of years below 1000 on Linux)."""
    return f"{day.year:04d}-{day.month:02d}-{day.day:02d}"


def n13_date(raw: str) -> str | None:
    """N-13 for valid_from and valid_to: output ISO YYYY-MM-DD."""
    value = raw.strip()
    for fmt in _DATE_FORMATS:
        parsed = _parse(value, fmt)
        if parsed:
            return _iso(parsed)
    slash = [d for d in (_parse(value, fmt) for fmt in _SLASH_FORMATS) if d is not None]
    if slash:
        if len(slash) == 1 and slash[0].day > 12:
            return _iso(slash[0])
        raise RuleViolation(ISSUE_AMBIGUOUS_DATE)
    for fmt in _NAMED_MONTH_FORMATS:
        parsed = _parse(value, fmt)
        if parsed:
            return _iso(parsed)
    raise RuleViolation(ISSUE_DATE)


def n14_fixed_vendor(raw: str) -> str | None:
    """N-14: X when the text says fixed / sole (source); otherwise empty (None)."""
    if re.search(r"\b(?:fixed|sole)\b", raw, re.IGNORECASE):
        return "X"
    return None


def _is_date(value: str) -> bool:
    try:
        n13_date(value)
    except RuleViolation:
        return False
    return True


# Human-approved deviation from contract §6 (recorded for the Planner): the exact N-15 regex is
# applied per tab-separated cell and ignores matches that are dashed part numbers (N-02) or valid
# dates (N-13); the same check detects signature blocks (N-06). Known limit: a phone number
# written like a part number (1234-567-89) or a date (2025-11-26) is not caught.
def _contains_phone(text: str) -> bool:
    """The N-15 phone pattern, per tab-separated cell, ignoring part numbers and dates.

    Without the exceptions the pattern matches every dashed part number (``1038-967-34``) and
    ISO date (``2025-11-26``), and tab-separated table rows chain into one long digit run.
    """
    for cell in text.split("\t"):
        for match in PHONE_PATTERN.finditer(cell):
            token = match.group().strip(" -.")
            if _DASHED_PART_NUMBER.fullmatch(token) or _is_date(token):
                continue
            return True
    return False


def n15_personal_data(
    raw: str, field: str, context: NormalizationContext, message_id: str | None = None
) -> bool:
    """N-15: True when the value contains '@', a phone pattern or a signature-block line."""
    if "@" in raw:
        return True
    exempt = field in _N15_EXEMPT_FIELDS or (
        field == "supplier" and re.fullmatch(r"\d{5}", raw.strip()) is not None
    )
    if not exempt and _contains_phone(raw):
        return True
    if message_id is not None:
        return raw.strip() in context.signature_lines.get(message_id, set())
    return False


# --------------------------------------------------------------------------- signature block


def signature_block(text: str) -> tuple[int, list[str]] | None:
    """(start offset, lines) of the last 8 lines when any contains '@' or a phone pattern.

    Trailing whitespace of the message is ignored so a final blank line does not count.
    """
    lines = text.rstrip().splitlines(keepends=True)
    last = lines[-SIGNATURE_LINES:]
    if not any("@" in line or _contains_phone(line) for line in last):
        return None
    start = sum(len(line) for line in lines[: len(lines) - len(last)])
    return start, last


def signature_lines(messages: list[Message]) -> dict[str, set[str]]:
    """Per message: the last 8 lines (trimmed, non-empty) when any is a signature line."""
    result: dict[str, set[str]] = {}
    for message in messages:
        block = signature_block(message.text)
        lines = block[1] if block else []
        result[message.message_id] = {line.strip() for line in lines if line.strip()}
    return result


# --------------------------------------------------------------------------- dispatcher

_RULES = {
    "supplier": n01_supplier,
    "material": n02_material,
    "vendor_material_no": n03_vendor_material_no,
    "plant": n04_plant,
    "purchasing_org": n05_purchasing_org,
    "country_of_origin": n06_country_of_origin,
    "lead_time_days": n07_lead_time_days,
    "standard_qty": n08_standard_qty,
    "amount": n09_amount,
    "currency": n10_currency,
    "pricing_unit": n11_pricing_unit,
    "unit_of_measure": n12_unit_of_measure,
    "valid_from": n13_date,
    "valid_to": n13_date,
    "fixed_vendor": n14_fixed_vendor,
}
_KNOWN_FIELDS = set(PIR_FIELDS) | set(SL_FIELDS)


def _rejected(candidate: Candidate, issue: str) -> Candidate:
    return candidate.model_copy(deep=True, update={"value_normalised": None, "issue": issue})


def normalize(field: str, candidate: Candidate, context: NormalizationContext) -> Candidate:
    """Return a copy with value_normalised set, or issue set when rejected (N-01..N-15).

    context.signature_lines: set[str] of signature-block lines per message_id.
    """
    if field not in _KNOWN_FIELDS:
        raise ValueError(f"Unknown field {field}")
    raw = candidate.value_raw
    if n15_personal_data(raw, field, context, candidate.source.message_id):
        return _rejected(candidate, ISSUE_PERSONAL_DATA)
    update: dict[str, object] = {"issue": None}
    try:
        if field == "fixed_vendor":
            value = n14_fixed_vendor(raw) or n14_fixed_vendor(candidate.source.text)
            if value is None:
                raise RuleViolation(ISSUE_FIXED_VENDOR)
        elif field == "lead_time_days":
            value, computation = _lead_time(raw)
            # N-07: weeks are computed; bare numbers and days are always literal days.
            if computation is None:
                update |= {"derivation": "literal", "computation": None}
            else:
                update |= {"derivation": "computed", "computation": computation}
        elif field == "currency" and raw.strip() in CURRENCY_SYMBOLS:
            value = n10_currency(raw)
            update |= {"derivation": "computed", "computation": f"symbol {raw.strip()}"}
        else:
            value = _RULES[field](raw)
            if value is None:
                raise RuleViolation(ISSUE_EMPTY)
    except RuleViolation as error:
        return _rejected(candidate, str(error))
    update["value_normalised"] = value
    return candidate.model_copy(deep=True, update=update)
