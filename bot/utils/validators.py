"""Validation helpers used across the project."""

from __future__ import annotations

import re
from typing import Final

# Regex for a valid Telegram username
# Must start with @, be 5-32 characters long, and contain only letters, numbers, and underscores.
USERNAME_RE = re.compile(r"@[A-Za-z0-9_]{5,32}")

USERNAME_PATTERN: Final[re.Pattern[str]] = re.compile(r"^@?[A-Za-z0-9_]{5,32}$")

# Allowed characters in arithmetic expressions for amounts (digits, ops, parens, slash, whitespace)
EXPR_ALLOWED_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9\s+\-*/()]+$")

def is_valid_username(username: str) -> bool:
    """
    Checks if a string is a valid Telegram username.
    - Starts with @
    - 5-32 characters long
    - Contains only A-Z, a-z, 0-9, and underscores
    """
    if not isinstance(username, str):
        return False
    return bool(re.match(r"^@[a-zA-Z0-9_]{5,32}$", username))

def validate_amount(amount: float) -> bool:
    """
    Validates if the amount is a positive number.
    """
    return isinstance(amount, (int, float)) and amount > 0

def sanitize_input(text: str) -> str:
    """
    A basic sanitizer to remove potentially harmful characters.
    This is a placeholder and should be expanded based on security needs.
    For now, it removes characters that might be used in HTML injection.
    """
    if not isinstance(text, str):
        return ""
    return text.replace("<", "&lt;").replace(">", "&gt;")

def is_valid_contact_info(contact: str) -> bool:
    """
    Validates contact info.
    A simple check for now, can be expanded (e.g., for specific card/phone formats).
    - Must be a string
    - Should not be empty
    - Should not contain obvious malicious patterns (very basic check)
    """
    if not isinstance(contact, str) or not contact.strip():
        return False
    # Avoid things that look like HTML tags
    if "<" in contact or ">" in contact:
        return False
    return True

def validate_username(value: str) -> str:
    """Validate a Telegram username and return it without the @ prefix."""
    if not USERNAME_PATTERN.match(value):
        raise ValueError("Invalid Telegram username format.")
    return value.lstrip("@")

def validate_positive_int(value: int) -> int:
    """Ensure *value* is a positive integer (≥1)."""
    if value <= 0:
        raise ValueError("Value must be positive integer.")
    return value

def validate_amount_expression(expr: str) -> None:
    """Validate that arithmetic expression *expr* contains only safe characters."""
    if not EXPR_ALLOWED_PATTERN.match(expr):
        raise ValueError("Amount expression contains unsafe characters.")

def validate_contact_info(contact: str) -> bool:  # noqa: D401
    """Alias for *is_valid_contact_info* kept for legacy unit-tests."""
    return is_valid_contact_info(contact) 
