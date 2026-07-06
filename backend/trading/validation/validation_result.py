"""
TODOBA Validation Result

Represents the outcome of a validation process.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationResult:
    """
    Validation outcome.

    passed:
        True if validation succeeded.

    errors:
        List of validation errors.
    """

    passed: bool
    errors: list[str]