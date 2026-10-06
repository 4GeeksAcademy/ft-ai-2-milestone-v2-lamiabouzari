"""Persistent operational memory for the TrackFlow support agent.

This store is not the company knowledge base. RAG keeps reading
``trackflow_knowledge`` and never receives writes from this module.

SQLite fits TrackFlow because the support agent needs a durable, file-backed
record that survives a new conversation thread, supports one pending proposal,
and can delete or replace rows as carrier rules and temporary incident notes
go stale. The database is a single file with no extra service, and tests can
point it at a temporary path. MemorySaver remains the LangGraph checkpoint
store; it is not where approved facts live.
"""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from data.pipelines import guardrails

DEFAULT_MEMORY_PATH = Path(__file__).resolve().parents[2] / "data" / "agent_memory" / "support_memory.sqlite"

_NOT_MEMORABLE = re.compile(
    r"\bwhere is (?:package|parcel|shipment)\b"
    r"|\b(?:package|parcel)\s+[A-Z]{1,4}\d{3,}\b"
    r"|\btranslate\b"
    r"|^(?:great|thanks|thank you|ok|okay)[,.]?\s*(?:that(?:'s| is)\s+)?resolved[.!]?$",
    re.IGNORECASE,
)
_CARRIER_RULE = re.compile(
    r"\b(seur|dhl|ups|fedex|correos|usps|mrw|gls|local carrier)\b.{0,160}\b("
    r"no longer covers|does not cover|doesn't cover|use the .+ instead"
    r")\b",
    re.IGNORECASE | re.DOTALL,
)
_RECURRING = re.compile(
    r"\brecurring\b.{0,80}\b(delays?|incidents?)\b.{0,100}\b(caused by|because of)\b",
    re.IGNORECASE | re.DOTALL,
)
_PREFERENCE = re.compile(
    r"\b(?:the\s+)?(?P<client>[a-z][a-z0-9-]{2,})\s+client\b.{0,100}\bwants\b.{0,140}\b"
    r"(?:returns breakdown|monthly report|report)\b",
    re.IGNORECASE | re.DOTALL,
)
_STREET = re.compile(
    r"\b\d{1,6}\s+[A-Za-z0-9][A-Za-z0-9.'-]*(?:\s+[A-Za-z0-9][A-Za-z0-9.'-]*){0,4}\s+"
    r"(?:street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln|drive|dr|way|calle|avenida)\b",
    re.IGNORECASE,
)
_ADDRESS_CUE = re.compile(
    r"\b(?:lives at|resides at|home address|customer address|deliver to|ship to|located at)\b",
    re.IGNORECASE,
)
_B2C = re.compile(r"\b(?:end[- ]customer|b2c|consumer|recipient)\b", re.IGNORECASE)
_B2B = re.compile(r"\b(?:b2b|client|account)\b", re.IGNORECASE)
_WAREHOUSE = re.compile(
    r"\b(?:exact warehouse|warehouse (?:is )?located|internal route|warehouse route|"
    r"aisle\s+[A-Z0-9]+|dock\s+\d+)\b",
    re.IGNORECASE,
)
_PACKAGE_ID = re.compile(
    r"\b(?:package|parcel|tracking(?:\s+number)?)\s*#?\s*[A-Z]{1,4}\d{3,}\b",
    re.IGNORECASE,
)
_NEGOTIATION = re.compile(
    r"\b(?:negotiat\w*|contract negotiation|active contract|proposed (?:rate|discount|terms)|"
    r"commercial terms)\b",
    re.IGNORECASE,
)
_BARE_APPROVE = re.compile(r"^(?:yes|approve|approved)[.!?]?$", re.IGNORECASE)
_APPROVE_AND_MORE = re.compile(
    r"^(?:"
    r"i approve(?: saving(?: that)?(?: memory)?)?"
    r"|yes,?\s+(?:please\s+)?(?:save|store|remember)(?:\s+(?:that|it|this))?"
    r"|please\s+(?:save|store|remember)\s+(?:that|it|this)"
    r")[.!]?\s*(?P<rest>.*)$",
    re.IGNORECASE | re.DOTALL,
)
_BARE_REJECT = re.compile(r"^(?:no|nope|reject|rejected)[.!?]?$", re.IGNORECASE)
_REJECT_AND_MORE = re.compile(
    r"^(?:"
    r"i reject(?: that)?"
    r"|no,?\s+don'?t\s+(?:save|store|remember)(?:\s+(?:that|it|this))?"
    r"|don'?t\s+(?:save|store|remember)(?:\s+(?:that|it|this))?"
    r"|do not\s+(?:save|store|remember)(?:\s+(?:that|it|this))?"
    r")[.!]?\s*(?P<rest>.*)$",
    re.IGNORECASE | re.DOTALL,
)
_EDIT = re.compile(
    r"^(?:edit|change it to|save this instead|update the memory to)\s*[:\-]?\s*(?P<fact>\S.+)$",
    re.IGNORECASE | re.DOTALL,
)

_STORE: AgentMemoryStore | None = None


class MemoryWriteRejected(ValueError):
    """Raised when a fact is not allowed to enter persistent memory."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _country_of(text: str) -> str | None:
    if re.search(r"\b(zaragoza|spain|españa)\b", text, re.IGNORECASE):
        return "spain"
    if re.search(r"\b(los angeles|united states|usa|u\.s\.a?\.?)\b", text, re.IGNORECASE):
        return "united states"
    return None


def forbidden_reason(fact: str) -> str | None:
    """Return why a fact must not be stored, or None when it may be stored.

    Approval does not override this check. B2B and B2C physical locations are
    both rejected, along with one-off package incidents, open commercial
    negotiations, and instruction-shaped text.
    """
    _isolated, injected = guardrails.isolate_untrusted_text(fact)
    if injected:
        return "instruction_injection"
    if _NEGOTIATION.search(fact):
        return "commercial_negotiation"
    if _PACKAGE_ID.search(fact):
        return "single_package_incident"
    if _WAREHOUSE.search(fact):
        if _B2B.search(fact):
            return "b2b_location"
        return "warehouse_location"
    if _STREET.search(fact) or _ADDRESS_CUE.search(fact):
        if _B2B.search(fact) and not _B2C.search(fact):
            return "b2b_location"
        return "b2c_location"
    if guardrails.output_is_sensitive(fact):
        return "sensitive_disclosure"
    return None


def analyze_fact(text: str) -> dict[str, Any] | None:
    """Classify a memorable TrackFlow fact. Anything else returns None."""
    fact = " ".join(text.strip().split())
    if not fact or _NOT_MEMORABLE.search(fact) or forbidden_reason(fact):
        return None

    carrier_match = _CARRIER_RULE.search(fact)
    if carrier_match:
        carrier = carrier_match.group(1).lower()
        if carrier == "local carrier":
            carrier = "local"
        country = _country_of(fact)
        area = "rural" if re.search(r"\brural\b", fact, re.IGNORECASE) else "general"
        return {
            "fact": fact,
            "kind": "carrier_rule",
            "memory_key": f"carrier:{carrier}:{country or 'unspecified'}:{area}",
            "country": country,
            "carrier": carrier,
            "client": None,
            "ttl_days": None,
        }

    if _RECURRING.search(fact):
        country = _country_of(fact)
        cause = "port-strike" if re.search(r"\bport strike\b", fact, re.IGNORECASE) else "recurring"
        ttl_days = 7 if re.search(r"\bthis week\b", fact, re.IGNORECASE) else 14
        return {
            "fact": fact,
            "kind": "recurring_incident",
            "memory_key": f"incident:{country or 'unspecified'}:{cause}",
            "country": country,
            "carrier": None,
            "client": None,
            "ttl_days": ttl_days,
        }

    preference = _PREFERENCE.search(fact)
    if preference:
        client = preference.group("client").lower()
        return {
            "fact": fact,
            "kind": "client_preference",
            "memory_key": f"preference:{client}",
            "country": _country_of(fact),
            "carrier": None,
            "client": client,
            "ttl_days": None,
        }
    return None


def is_memorable_fact(text: str) -> bool:
    """True when the agent should offer to remember this operational update."""
    return analyze_fact(text) is not None


def allows_operational_update(text: str) -> bool:
    """TrackFlow carrier, incident, and report updates stay inside support scope."""
    return is_memorable_fact(text)


def build_proposal(question: str) -> dict[str, Any] | None:
    """Build one unsaved proposal from the user message."""
    parsed = analyze_fact(question)
    if parsed is None:
        return None
    return {"proposal_id": str(uuid4()), **parsed}


def _clean_rest(rest: str) -> str:
    cleaned = rest.strip()
    if cleaned in {"", ".", "!", "?"}:
        return ""
    return cleaned


def classify_confirmation(message: str) -> dict[str, str]:
    """Classify a reply to the single pending proposal.

    Whole-message decisions are explicit. Finding the letters y-e-s inside a
    longer sentence is not approval. Silence and topic changes are
    ``unclear``, which discards the proposal.
    """
    text = message.strip()
    if not text:
        return {"decision": "unclear", "fact": "", "remainder": ""}

    edited = _EDIT.search(text)
    if edited:
        return {"decision": "edit", "fact": " ".join(edited.group("fact").split()), "remainder": ""}

    if _BARE_REJECT.search(text):
        return {"decision": "reject", "fact": "", "remainder": ""}
    rejected = _REJECT_AND_MORE.search(text)
    if rejected:
        return {"decision": "reject", "fact": "", "remainder": _clean_rest(rejected.group("rest"))}

    if _BARE_APPROVE.search(text):
        return {"decision": "approve", "fact": "", "remainder": ""}
    approved = _APPROVE_AND_MORE.search(text)
    if approved:
        return {"decision": "approve", "fact": "", "remainder": _clean_rest(approved.group("rest"))}

    return {"decision": "unclear", "fact": "", "remainder": text}


def confirmation_answer(*, decision: str, fact: str, written: bool) -> str:
    """User-visible result of a resolved proposal. Blocked text is not echoed."""
    if written and decision == "approve":
        return (
            f'I saved this operational memory: "{fact}" '
            "Company knowledge documents were not changed."
        )
    if written and decision == "edit":
        return (
            f'I saved the edited operational memory: "{fact}" '
            "Company knowledge documents were not changed."
        )
    if decision == "blocked":
        return (
            "I did not save that. TrackFlow memory cannot keep sensitive locations, "
            "one-off package incidents, active contract negotiations, or instruction text."
        )
    return "I did not save that suggestion."


def memory_matches(question: str, memory: dict[str, Any]) -> bool:
    """Whether a stored fact is relevant to this support question."""
    kind = memory.get("kind")
    if kind not in {"carrier_rule", "recurring_incident", "client_preference"}:
        return False
    question_text = question.lower()
    country = memory.get("country")
    country_hit = False
    if country == "spain":
        country_hit = re.search(r"\b(zaragoza|spain)\b", question_text) is not None
    elif country == "united states":
        country_hit = re.search(r"\b(los angeles|united states|usa)\b", question_text) is not None

    if kind == "carrier_rule":
        carrier = str(memory.get("carrier") or "")
        carrier_hit = bool(carrier) and carrier in question_text
        topic_hit = re.search(r"\b(carrier|coverage|covers|rural)\b", question_text) is not None
        return bool(topic_hit and (country_hit or carrier_hit))
    if kind == "recurring_incident":
        topic_hit = re.search(r"\b(delay|delays|strike|port)\b", question_text) is not None
        return bool(topic_hit and country_hit)
    client = str(memory.get("client") or "")
    topic_hit = re.search(r"\b(report|returns|breakdown|volume)\b", question_text) is not None
    return bool(client and client in question_text and topic_hit)


def operational_context(question: str) -> str:
    """Return stored facts relevant to the question, as ordinary data."""
    try:
        memories = get_store().list()
    except Exception:
        return ""
    parts: list[str] = []
    for memory in memories:
        if not memory_matches(question, memory):
            continue
        text, injected = guardrails.isolate_untrusted_text(str(memory.get("fact") or ""))
        if injected or guardrails.output_is_sensitive(text):
            continue
        parts.append(text)
    return " ".join(parts)


class AgentMemoryStore:
    """SQLite backend with read, write, delete, and list."""

    def __init__(self, path: str | Path, *, clock: Callable[[], datetime] | None = None) -> None:
        self.path = Path(path)
        self._clock = clock or _now_utc
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _now(self) -> datetime:
        current = self._clock()
        if current.tzinfo is None:
            return current.replace(tzinfo=timezone.utc)
        return current

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    memory_key TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    fact TEXT NOT NULL,
                    normalized_fact TEXT NOT NULL,
                    country TEXT,
                    carrier TEXT,
                    client TEXT,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    proposal_id TEXT
                );
                CREATE TABLE IF NOT EXISTS pending (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    thread_id TEXT NOT NULL,
                    proposal_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    proposal_id TEXT NOT NULL,
                    proposed_fact TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    written INTEGER NOT NULL,
                    block_reason TEXT
                );
                """
            )

    def _expired(self, expires_at: str | None) -> bool:
        if not expires_at:
            return False
        expires = datetime.fromisoformat(expires_at)
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return expires <= self._now()

    def _row_to_memory(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "memory_key": row["memory_key"],
            "kind": row["kind"],
            "fact": row["fact"],
            "normalized_fact": row["normalized_fact"],
            "country": row["country"],
            "carrier": row["carrier"],
            "client": row["client"],
            "created_at": row["created_at"],
            "expires_at": row["expires_at"],
            "proposal_id": row["proposal_id"],
        }

    def consolidate(self) -> dict[str, int]:
        """Drop expired temporary notes and duplicate facts.

        Carrier rules share a key of carrier + country + area, so a newer rule
        replaces the older one at write time. Recurring incident context expires.
        Identical normalized facts collapse to the earliest row.
        """
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM memories ORDER BY created_at ASC, id ASC"
            ).fetchall()
        expired_ids = [row["id"] for row in rows if self._expired(row["expires_at"])]
        for memory_id in expired_ids:
            self.delete(memory_id)
        seen: set[str] = set()
        duplicate_ids: list[str] = []
        for row in rows:
            if row["id"] in expired_ids:
                continue
            normalized = row["normalized_fact"]
            if normalized in seen:
                duplicate_ids.append(row["id"])
            else:
                seen.add(normalized)
        for memory_id in duplicate_ids:
            self.delete(memory_id)
        return {"expired_deleted": len(expired_ids), "duplicates_removed": len(duplicate_ids)}

    def read(self, memory_id: str) -> dict[str, Any] | None:
        """Return one active memory, or None when it is missing or expired."""
        self.consolidate()
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        if row is None or self._expired(row["expires_at"]):
            return None
        return self._row_to_memory(row)

    def write(self, fact: str, *, proposal_id: str | None = None) -> dict[str, Any]:
        """Validate, replace an outdated key, and persist one fact.

        Forbidden facts are rejected even when a person approved them. Nothing
        here is written to a knowledge collection.
        """
        reason = forbidden_reason(fact)
        if reason:
            raise MemoryWriteRejected(reason)
        cleaned = " ".join(fact.strip().split())
        parsed = analyze_fact(cleaned)
        if parsed is None:
            digest = hashlib.sha256(_normalize(cleaned).encode()).hexdigest()[:16]
            parsed = {
                "fact": cleaned,
                "kind": "note",
                "memory_key": f"note:{digest}",
                "country": None,
                "carrier": None,
                "client": None,
                "ttl_days": None,
            }
        normalized = _normalize(parsed["fact"])
        ttl_days = parsed.get("ttl_days")
        expires_at = (self._now() + timedelta(days=int(ttl_days))).isoformat() if ttl_days else None
        self.consolidate()
        with self._connect() as connection:
            existing_rows = connection.execute(
                "SELECT * FROM memories WHERE memory_key = ? OR normalized_fact = ?",
                (parsed["memory_key"], normalized),
            ).fetchall()
            for row in existing_rows:
                if row["normalized_fact"] == normalized and row["memory_key"] == parsed["memory_key"]:
                    return self._row_to_memory(row)
            if existing_rows:
                connection.execute(
                    "DELETE FROM memories WHERE memory_key = ? OR normalized_fact = ?",
                    (parsed["memory_key"], normalized),
                )
            memory_id = str(uuid4())
            created_at = self._now().isoformat()
            connection.execute(
                """
                INSERT INTO memories (
                    id, memory_key, kind, fact, normalized_fact, country, carrier, client,
                    created_at, expires_at, proposal_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    parsed["memory_key"],
                    parsed["kind"],
                    parsed["fact"],
                    normalized,
                    parsed.get("country"),
                    parsed.get("carrier"),
                    parsed.get("client"),
                    created_at,
                    expires_at,
                    proposal_id,
                ),
            )
            row = connection.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        return self._row_to_memory(row)

    def delete(self, memory_id: str) -> bool:
        """Remove one memory. Returns False when the id is unknown."""
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            return cursor.rowcount == 1

    def list(self) -> list[dict[str, Any]]:
        """Return active memories after cleanup."""
        self.consolidate()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM memories ORDER BY created_at ASC, id ASC"
            ).fetchall()
        return [self._row_to_memory(row) for row in rows if not self._expired(row["expires_at"])]

    def get_pending(self, thread_id: str) -> dict[str, Any] | None:
        """Return the single pending proposal for this conversation, if any."""
        with self._connect() as connection:
            row = connection.execute("SELECT thread_id, proposal_json FROM pending WHERE id = 1").fetchone()
        if row is None or row["thread_id"] != thread_id:
            return None
        import json

        proposal = json.loads(row["proposal_json"])
        return proposal if isinstance(proposal, dict) else None

    def has_pending(self) -> bool:
        """True when a proposal is already waiting for the user."""
        with self._connect() as connection:
            row = connection.execute("SELECT 1 FROM pending WHERE id = 1").fetchone()
        return row is not None

    def put_pending(self, thread_id: str, proposal: dict[str, Any]) -> dict[str, Any]:
        """Store a proposal only when none is waiting.

        An unresolved proposal stays as-is. It is not replaced and it is not
        audited as discarded. The caller resolves it explicitly first.
        """
        import json

        with self._connect() as connection:
            current = connection.execute("SELECT proposal_json FROM pending WHERE id = 1").fetchone()
            if current is not None:
                previous = json.loads(current["proposal_json"])
                return previous if isinstance(previous, dict) else proposal
            connection.execute(
                "INSERT INTO pending (id, thread_id, proposal_json) VALUES (1, ?, ?)",
                (thread_id, json.dumps(proposal)),
            )
        return proposal

    def clear_pending(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM pending")

    def add_audit(
        self,
        *,
        proposal_id: str,
        proposed_fact: str,
        decision: str,
        written: bool,
        block_reason: str | None = None,
    ) -> dict[str, Any]:
        """Record how a proposal was resolved. The fact stays in the audit table only."""
        timestamp = self._now().isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO audits (timestamp, proposal_id, proposed_fact, decision, written, block_reason)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (timestamp, proposal_id, proposed_fact, decision, 1 if written else 0, block_reason),
            )
            audit_id = cursor.lastrowid
        return {
            "id": audit_id,
            "timestamp": timestamp,
            "proposal_id": proposal_id,
            "proposed_fact": proposed_fact,
            "decision": decision,
            "written": written,
            "block_reason": block_reason,
        }

    def list_audits(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM audits ORDER BY id ASC").fetchall()
        return [
            {
                "id": row["id"],
                "timestamp": row["timestamp"],
                "proposal_id": row["proposal_id"],
                "proposed_fact": row["proposed_fact"],
                "decision": row["decision"],
                "written": bool(row["written"]),
                "block_reason": row["block_reason"],
            }
            for row in rows
        ]


def get_store() -> AgentMemoryStore:
    """Return the process memory store, creating the default file on first use."""
    global _STORE
    if _STORE is None:
        configured = os.environ.get("TRACKFLOW_AGENT_MEMORY_PATH")
        _STORE = AgentMemoryStore(configured or DEFAULT_MEMORY_PATH)
    return _STORE


def set_store(store: AgentMemoryStore | None) -> None:
    """Replace the process store. Tests pass a temporary database, then None."""
    global _STORE
    _STORE = store


def resolve_pending(thread_id: str, message: str) -> dict[str, Any] | None:
    """Apply approve, reject, edit, or unclear to the pending proposal, if one exists."""
    store = get_store()
    pending = store.get_pending(thread_id)
    if pending is None:
        return None
    decision = classify_confirmation(message)
    kind = decision["decision"]
    proposed_fact = str(pending.get("fact") or "")
    fact_to_write = proposed_fact
    if kind == "edit":
        fact_to_write = decision["fact"]
    written = False
    block_reason = None
    recorded_decision = kind
    if kind in {"approve", "edit"}:
        try:
            store.write(fact_to_write, proposal_id=str(pending.get("proposal_id") or ""))
            written = True
        except MemoryWriteRejected as exc:
            recorded_decision = "blocked"
            block_reason = exc.reason
            fact_to_write = fact_to_write
    audit_fact = fact_to_write if kind in {"approve", "edit"} else proposed_fact
    audit = store.add_audit(
        proposal_id=str(pending.get("proposal_id") or ""),
        proposed_fact=audit_fact,
        decision=recorded_decision,
        written=written,
        block_reason=block_reason,
    )
    store.clear_pending()
    return {
        "decision": recorded_decision,
        "written": written,
        "block_reason": block_reason,
        "fact": fact_to_write if kind in {"approve", "edit"} else proposed_fact,
        "remainder": decision["remainder"],
        "audit": audit,
        "answer": confirmation_answer(
            decision=recorded_decision,
            fact=fact_to_write if written else "",
            written=written,
        ),
    }


def prepare_confirmation(question: str, thread_id: str) -> dict[str, Any] | None:
    """Resolve a pending proposal before the normal support turn, when one exists.

    A new memorable fact does not count as approve, reject, edit, or a topic
    change. The current proposal stays pending and no second proposal is stored.
    """
    if get_store().get_pending(thread_id) is None:
        return None
    decision = classify_confirmation(question)
    if decision["decision"] == "unclear" and is_memorable_fact(question):
        return None
    resolved = resolve_pending(thread_id, question)
    if resolved is None:
        return None
    remainder = resolved["remainder"]
    if resolved["decision"] in {"approve", "reject", "edit", "blocked"} and not remainder:
        return {
            "skip_graph": True,
            "memory_resolution": resolved,
            "result": _resolution_result(question, resolved),
        }
    follow_up = remainder if resolved["decision"] in {"approve", "reject", "edit", "blocked"} else question
    return {
        "skip_graph": False,
        "question": follow_up,
        "memory_resolution": resolved,
    }


def _resolution_result(question: str, resolved: dict[str, Any]) -> dict[str, Any]:
    output = {
        "decision": resolved["decision"],
        "written": resolved["written"],
        "block_reason": resolved["block_reason"],
    }
    return {
        "question": question,
        "retrieved_context": [],
        "answer": resolved["answer"],
        "error": None,
        "trace": [{"node": "resolve_memory", "order": 1, "output": output}],
        "intent": None,
        "incident_id": None,
        "incident_result": None,
        "guardrail_reason": None,
        "country_enforcement": None,
        "guardrail_events": [],
        "memory_proposal": None,
        "memory_resolution": resolved,
    }


def attach_proposal(result: dict[str, Any], question: str, thread_id: str) -> dict[str, Any]:
    """Offer at most one unsaved memory after a normal support answer."""
    if result.get("guardrail_reason") or result.get("error") == "Please provide a non-empty question.":
        return {**result, "memory_proposal": result.get("memory_proposal")}
    if get_store().has_pending():
        return {**result, "memory_proposal": None}
    proposal = build_proposal(question)
    if proposal is None:
        return {**result, "memory_proposal": None}
    get_store().put_pending(thread_id, proposal)
    note = (
        f'\n\nI can remember this for later TrackFlow support: "{proposal["fact"]}" '
        "I have not saved it yet. Reply with a clear approve, reject, or edit."
    )
    answer = str(result.get("answer") or "")
    combined = answer.rstrip() + note
    if guardrails.output_is_sensitive(combined):
        combined = answer
    return {**result, "answer": combined, "memory_proposal": proposal}
