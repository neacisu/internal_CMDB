"""Governance-as-code — signed policy decisions and hash-chain audit trail (F5.3).

Records every :class:`~internalcmdb.governance.policy_enforcer.PolicyEnforcer`
decision as an immutable, hash-chained audit entry suitable for compliance
verification and tamper detection.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_GENESIS_HASH = "0" * 64


@dataclass(frozen=True)
class SignedPolicyRecord:
    """A single hash-chained policy audit entry."""

    sequence_num: int
    decision: str
    record_hash: str
    prev_hash: str
    policy_codes: tuple[str, ...]
    signature: str
    created_at: str


class PolicyAuditChain:
    """Append-only hash-chain audit log for policy enforcement decisions."""

    def __init__(self, session: Session, *, signing_key: str = "") -> None:
        self._session = session
        self._signing_key = signing_key

    def record_decision(
        self,
        action: dict[str, Any],
        *,
        compliant: bool,
        policy_codes: list[str] | None = None,
        context: dict[str, Any] | None = None,
    ) -> SignedPolicyRecord | None:
        """Append a signed audit record for a policy check result."""
        codes = policy_codes or []
        decision = "allow" if compliant else "deny"
        try:
            prev_hash, next_seq = self._latest_chain_state()
            payload = {
                "sequence_num": next_seq,
                "action": action,
                "context": context or {},
                "decision": decision,
                "policy_codes": codes,
                "timestamp": datetime.now(tz=UTC).isoformat(),
            }
            record_hash = self._compute_hash(prev_hash, payload)
            signature = self._sign(record_hash)

            self._session.execute(
                text("""
                    INSERT INTO governance.policy_audit_chain
                        (sequence_num, action_jsonb, decision, policy_codes,
                         record_hash, prev_hash, signature)
                    VALUES
                        (:seq, CAST(:action AS jsonb), :decision, :codes,
                         :record_hash, :prev_hash, :signature)
                """),
                {
                    "seq": next_seq,
                    "action": json.dumps(action, sort_keys=True, default=str),
                    "decision": decision,
                    "codes": codes,
                    "record_hash": record_hash,
                    "prev_hash": prev_hash if prev_hash != _GENESIS_HASH else None,
                    "signature": signature,
                },
            )
            self._session.flush()

            return SignedPolicyRecord(
                sequence_num=next_seq,
                decision=decision,
                record_hash=record_hash,
                prev_hash=prev_hash,
                policy_codes=tuple(codes),
                signature=signature,
                created_at=payload["timestamp"],
            )
        except Exception:
            logger.warning("Policy audit chain write failed", exc_info=True)
            return None

    def verify_chain(self, limit: int = 100) -> dict[str, Any]:
        """Verify hash-chain integrity for the most recent *limit* records."""
        rows = self._session.execute(
            text("""
                SELECT sequence_num, action_jsonb, decision, policy_codes,
                       record_hash, prev_hash, signature, created_at
                FROM governance.policy_audit_chain
                ORDER BY sequence_num DESC
                LIMIT :limit
            """),
            {"limit": limit},
        ).fetchall()

        if not rows:
            return {"valid": True, "checked": 0, "errors": []}

        ordered = sorted(rows, key=lambda r: r.sequence_num)
        errors: list[str] = []
        expected_prev = _GENESIS_HASH

        for row in ordered:
            stored_prev = row.prev_hash or _GENESIS_HASH
            if row.sequence_num == ordered[0].sequence_num and row.prev_hash is None:
                stored_prev = _GENESIS_HASH

            if stored_prev != expected_prev and row.sequence_num != ordered[0].sequence_num:
                errors.append(f"sequence {row.sequence_num}: prev_hash mismatch")

            payload = {
                "sequence_num": row.sequence_num,
                "action": row.action_jsonb,
                "context": {},
                "decision": row.decision,
                "policy_codes": list(row.policy_codes or []),
                "timestamp": row.created_at.isoformat() if row.created_at else "",
            }
            computed = self._compute_hash(stored_prev, payload)
            if computed != row.record_hash:
                errors.append(f"sequence {row.sequence_num}: record_hash mismatch")

            expected_prev = row.record_hash

        return {"valid": not errors, "checked": len(ordered), "errors": errors}

    def _latest_chain_state(self) -> tuple[str, int]:
        row = self._session.execute(
            text("""
                SELECT record_hash, sequence_num
                FROM governance.policy_audit_chain
                ORDER BY sequence_num DESC
                LIMIT 1
            """)
        ).first()
        if row is None:
            return _GENESIS_HASH, 1
        return row.record_hash, row.sequence_num + 1

    @staticmethod
    def _compute_hash(prev_hash: str, payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, default=str)
        digest_input = f"{prev_hash}:{canonical}"
        return hashlib.sha256(digest_input.encode()).hexdigest()

    def _sign(self, record_hash: str) -> str:
        if not self._signing_key:
            return hashlib.sha256(f"unsigned:{record_hash}".encode()).hexdigest()
        return hashlib.sha256(f"{self._signing_key}:{record_hash}".encode()).hexdigest()
