"""Convert an uploaded PDF to Markdown before any agent reads it."""

from __future__ import annotations

from pathlib import Path


class UnreadablePdf(ValueError):
    """The PDF could not be converted into readable Markdown."""


def pdf_to_markdown(path: Path) -> str:
    """Convert a PDF with MarkItDown. Agents must not receive the raw PDF."""
    try:
        from markitdown import MarkItDown
    except ImportError as exc:
        raise UnreadablePdf("MarkItDown is not installed.") from exc

    result = MarkItDown(enable_plugins=False).convert(str(path))
    text = getattr(result, "text_content", None) or ""
    if not str(text).strip():
        raise UnreadablePdf("The PDF did not produce readable Markdown.")
    return str(text)
