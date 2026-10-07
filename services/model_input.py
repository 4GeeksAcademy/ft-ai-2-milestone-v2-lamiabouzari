"""Shared checks for text that may be sent to a model.

These checks reject empty, oversized, or control-character payloads.
They do not strip words such as "ignore"; authorization stays the boundary
for prompt injection.
"""

from __future__ import annotations

MAX_MODEL_QUESTION_LENGTH = 2000


class ModelInputError(ValueError):
    """The payload is not safe to forward to a model call."""


def normalize_model_question(value: str) -> str:
    """Return stripped question text or raise ModelInputError."""
    if not isinstance(value, str):
        raise ModelInputError("Question must be text")
    text = value.strip()
    if not text:
        raise ModelInputError("Question must not be empty")
    if len(text) > MAX_MODEL_QUESTION_LENGTH:
        raise ModelInputError("Question is too long")
    if any(ord(character) < 32 and character not in "\n\t" for character in text):
        raise ModelInputError("Question contains invalid control characters")
    return text
