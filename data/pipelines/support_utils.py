"""Pure text-parsing helpers for the support agent (no external I/O).

Kept separate from the MCP client layer and the retired incident_tool so
that the agent's incident-ID parsing never looks like direct Incident
Manager/backend access.
"""

from __future__ import annotations

import re

_UUID_PATTERN = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def extract_incident_id(text: str) -> str | None:
    """Pull the first UUID-looking token out of free-form text, if any."""
    match = _UUID_PATTERN.search(text)
    return match.group(0) if match else None
