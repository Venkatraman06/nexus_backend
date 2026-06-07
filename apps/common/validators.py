"""
Shared field validators used across serializers and views.
"""
import re

from rest_framework import serializers

COUNTRY_PHONE_RULES: dict[str, dict] = {
    "+91":  {"digits": 10, "pattern": re.compile(r"^[6-9]\d{9}$"), "name": "India"},
    "+1":   {"digits": 10, "pattern": re.compile(r"^\d{10}$"),     "name": "United States"},
    "+44":  {"digits": 10, "pattern": re.compile(r"^\d{10}$"),     "name": "United Kingdom"},
    "+971": {"digits": 9,  "pattern": re.compile(r"^\d{9}$"),      "name": "UAE"},
    "+65":  {"digits": 8,  "pattern": re.compile(r"^\d{8}$"),      "name": "Singapore"},
    "+61":  {"digits": 9,  "pattern": re.compile(r"^\d{9}$"),      "name": "Australia"},
}

DEFAULT_COUNTRY_CODE = "+91"


def _digits_only(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def parse_phone(value: str) -> tuple[str, str]:
    """Return (country_code, national_digits)."""
    if not value or not str(value).strip():
        return DEFAULT_COUNTRY_CODE, ""

    trimmed = str(value).strip()
    for code in sorted(COUNTRY_PHONE_RULES.keys(), key=len, reverse=True):
        if trimmed.startswith(code):
            return code, _digits_only(trimmed[len(code):])

    digits = _digits_only(trimmed)
    if len(digits) == 10:
        return DEFAULT_COUNTRY_CODE, digits
    return DEFAULT_COUNTRY_CODE, digits


def format_phone(country_code: str, national_digits: str) -> str:
    digits = _digits_only(national_digits)
    if not digits:
        return ""
    return f"{country_code} {digits}"


def validate_phone(value: str, field_label: str = "Phone number") -> str:
    """
    Validate and normalize a phone number.
    Returns canonical format '+91 9876543210' or empty string.
    Raises serializers.ValidationError on invalid input.
    """
    if value is None:
        return ""
    value = str(value).strip()
    if not value:
        return ""

    country_code, national = parse_phone(value)
    rule = COUNTRY_PHONE_RULES.get(country_code)
    if not rule:
        raise serializers.ValidationError(
            f"{field_label}: unsupported country code '{country_code}'."
        )

    if len(national) != rule["digits"]:
        raise serializers.ValidationError(
            f"{field_label} must be {rule['digits']} digits for {rule['name']} ({country_code})."
        )

    if not rule["pattern"].match(national):
        if country_code == "+91":
            raise serializers.ValidationError(
                f"{field_label} must be a valid 10-digit Indian mobile number."
            )
        raise serializers.ValidationError(
            f"{field_label} is not valid for {rule['name']} ({country_code})."
        )

    return format_phone(country_code, national)
