import re

from django.conf import settings


def validate_password_strength(password: str) -> list[str]:
    """Return a list of validation error messages (empty = valid)."""
    errors = []
    min_len = getattr(settings, "PASSWORD_MIN_LENGTH", 8)

    if len(password) < min_len:
        errors.append(f"Password must be at least {min_len} characters long.")

    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter.")

    if not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter.")

    if not re.search(r"\d", password):
        errors.append("Password must contain at least one digit.")

    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?`~]", password):
        errors.append("Password must contain at least one special character.")

    return errors


def password_strength_score(password: str) -> dict:
    """Return strength metadata for UI display."""
    rules = {
        "min_length": len(password) >= getattr(settings, "PASSWORD_MIN_LENGTH", 8),
        "uppercase": bool(re.search(r"[A-Z]", password)),
        "lowercase": bool(re.search(r"[a-z]", password)),
        "digit": bool(re.search(r"\d", password)),
        "special": bool(re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?`~]", password)),
    }
    passed = sum(rules.values())
    if passed <= 2:
        level = "weak"
    elif passed <= 4:
        level = "medium"
    else:
        level = "strong"
    return {"level": level, "rules": rules, "valid": passed == 5}
