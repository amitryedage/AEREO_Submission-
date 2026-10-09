"""Recipient semantic validation, normalization, and duplicate detection."""

import re
from dataclasses import dataclass
from typing import Any

from email_validator import EmailNotValidError, validate_email

CONTROL_CHAR_REGEX = re.compile(r"[\x00-\x1f\x7f]")


def has_control_characters(text: str) -> bool:
    """Return True if the text contains ASCII control characters."""
    return bool(CONTROL_CHAR_REGEX.search(text))


def collapse_spaces(text: str) -> str:
    """Collapse consecutive internal whitespace runs into a single space."""
    return " ".join(text.split())


@dataclass
class ValidatedRecipient:
    """Represents the semantic validation output for a single recipient."""

    sequence: int
    raw_input: dict[str, Any]
    is_valid: bool
    name: str | None = None
    email: str | None = None
    reference_id: str | None = None
    achievement: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class RecipientValidator:
    """Validator performing per-recipient semantic validation and deduplication."""

    @classmethod
    def validate_single(
        cls,
        sequence: int,
        raw_item: Any,
        seen_emails: set[str],
    ) -> ValidatedRecipient:
        """Validate an individual recipient entry."""
        if not isinstance(raw_item, dict):
            raw_dict = {"_raw": raw_item} if raw_item is not None else {}
            return ValidatedRecipient(
                sequence=sequence,
                raw_input=raw_dict,
                is_valid=False,
                error_code="INVALID_NAME",
                error_message="recipient: must be a valid JSON object",
            )

        errors: list[tuple[str, str]] = []  # List of (error_code, message)

        # 1. Validate Name
        normalized_name: str | None = None
        raw_name = raw_item.get("name")
        if raw_name is None:
            errors.append(("MISSING_FIELD", "name: field required"))
        elif not isinstance(raw_name, str):
            errors.append(("INVALID_NAME", "name: must be a string"))
        else:
            trimmed_name = raw_name.strip()
            if not trimmed_name:
                errors.append(("INVALID_NAME", "name: must not be empty"))
            elif len(trimmed_name) > 100:
                errors.append(("INVALID_NAME", "name: must not exceed 100 characters"))
            elif has_control_characters(trimmed_name):
                errors.append(("INVALID_NAME", "name: control characters not allowed"))
            else:
                normalized_name = collapse_spaces(trimmed_name)

        # 2. Validate Email
        normalized_email: str | None = None
        raw_email = raw_item.get("email")
        if raw_email is None:
            errors.append(("MISSING_FIELD", "email: field required"))
        elif not isinstance(raw_email, str):
            errors.append(("INVALID_EMAIL", "email: must be a string"))
        else:
            trimmed_email = raw_email.strip()
            if not trimmed_email:
                errors.append(("INVALID_EMAIL", "email: must not be empty"))
            elif len(trimmed_email) > 254:
                errors.append(("INVALID_EMAIL", "email: must not exceed 254 characters"))
            else:
                try:
                    email_info = validate_email(trimmed_email, check_deliverability=False)
                    normalized_email = email_info.normalized.lower()
                except EmailNotValidError:
                    errors.append(("INVALID_EMAIL", "email: not a valid email address"))

        # 3. Check Duplicates (if email was valid)
        if normalized_email is not None:
            if normalized_email in seen_emails:
                errors.append(("DUPLICATE_RECIPIENT", "email: duplicate email in this request"))
            else:
                seen_emails.add(normalized_email)

        # 4. Validate Reference ID (optional)
        normalized_ref_id: str | None = None
        raw_ref_id = raw_item.get("reference_id")
        if raw_ref_id is not None:
            if not isinstance(raw_ref_id, str):
                errors.append(("FIELD_TOO_LONG", "reference_id: must be a string"))
            else:
                trimmed_ref = raw_ref_id.strip()
                if len(trimmed_ref) > 64:
                    errors.append(("FIELD_TOO_LONG", "reference_id: must not exceed 64 characters"))
                else:
                    normalized_ref_id = trimmed_ref if trimmed_ref else None

        # 5. Validate Achievement (optional)
        normalized_achievement: str | None = None
        raw_achievement = raw_item.get("achievement")
        if raw_achievement is not None:
            if not isinstance(raw_achievement, str):
                errors.append(("FIELD_TOO_LONG", "achievement: must be a string"))
            else:
                trimmed_ach = raw_achievement.strip()
                if len(trimmed_ach) > 100:
                    errors.append(("FIELD_TOO_LONG", "achievement: must not exceed 100 characters"))
                elif has_control_characters(trimmed_ach):
                    errors.append(("FIELD_TOO_LONG", "achievement: control characters not allowed"))
                else:
                    normalized_achievement = trimmed_ach if trimmed_ach else None

        if errors:
            first_code = errors[0][0]
            joined_message = "; ".join(msg for _, msg in errors)
            return ValidatedRecipient(
                sequence=sequence,
                raw_input=raw_item,
                is_valid=False,
                name=normalized_name,
                email=normalized_email,
                reference_id=normalized_ref_id,
                achievement=normalized_achievement,
                error_code=first_code,
                error_message=joined_message,
            )

        return ValidatedRecipient(
            sequence=sequence,
            raw_input=raw_item,
            is_valid=True,
            name=normalized_name,
            email=normalized_email,
            reference_id=normalized_ref_id,
            achievement=normalized_achievement,
        )

    @classmethod
    def validate_all(cls, recipients: list[Any]) -> list[ValidatedRecipient]:
        """Validate all recipient items, accumulating seen emails for duplicate tracking."""
        seen_emails: set[str] = set()
        results: list[ValidatedRecipient] = []
        for idx, item in enumerate(recipients):
            results.append(cls.validate_single(idx, item, seen_emails))
        return results
