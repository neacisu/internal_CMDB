"""internalCMDB — Chunk Ranker and Selection Rationale (pt-015).

Reranks a list of :class:`~internalcmdb.retrieval.broker.AssembledItem`
candidates using a deterministic-first scoring policy that mirrors ADR-003
retrieval ordering.  The ranker enforces the following score hierarchy:

  1. Mandatory context class (per evidence contract) → highest base score.
  2. Position in the contract's ``retrieval_order`` tuple (earlier = higher).
  3. Within same tier: mandatory items before recommended, recommended before
     supplementary.
  4. Token cost penalty: items that consume more budget are ranked lower when
     the remaining budget is tight.

Semantic chunks (``ContextClass.CHUNK_SEMANTIC``) are always ranked below all
deterministic items regardless of their similarity score.  This enforces the
ADR-003 guarantee that semantic augmentation never displaces deterministic
evidence.

Selection rationale is captured as a human-readable string for each selected
item and stored in
:attr:`~internalcmdb.retrieval.broker.AssembledItem.inclusion_reason`.

Usage::

    from internalcmdb.retrieval.ranker import Ranker
    from internalcmdb.retrieval.task_types import get_contract, TaskTypeCode

    contract = get_contract(TaskTypeCode.INFRASTRUCTURE_AUDIT)
    ranked = Ranker(contract).rank(candidates, token_budget=8000)
"""

from __future__ import annotations

from dataclasses import dataclass

# Lazy import to avoid circular dependency — AssembledItem is defined in broker.
# We use TYPE_CHECKING so mypy resolves the type without a runtime import cycle.
from typing import TYPE_CHECKING

from internalcmdb.retrieval.task_types import ContextClass, EvidenceContract

if TYPE_CHECKING:
    from internalcmdb.retrieval.broker import AssembledItem


# ---------------------------------------------------------------------------
# Tier constants — lower numeric value = higher priority
# ---------------------------------------------------------------------------
_TIER_MANDATORY: int = 0
_TIER_RECOMMENDED: int = 1
_TIER_SUPPLEMENTARY: int = 2  # present_class not in mandatory or recommended
_TIER_SEMANTIC: int = 3  # chunk_semantic always last


@dataclass(frozen=True)
class _ScoredItem:
    tier: int
    order_position: int  # position in contract.retrieval_order (or large int)
    token_count: int
    item_index: int  # original list position for stable sort
    original: AssembledItem


def _tier_for(ctx: ContextClass, contract: EvidenceContract) -> int:
    if ctx == ContextClass.CHUNK_SEMANTIC:
        return _TIER_SEMANTIC
    if ctx in contract.mandatory_classes:
        return _TIER_MANDATORY
    if ctx in contract.recommended_classes:
        return _TIER_RECOMMENDED
    return _TIER_SUPPLEMENTARY


def _order_position(ctx: ContextClass, contract: EvidenceContract) -> int:
    try:
        return contract.retrieval_order.index(ctx)
    except ValueError:
        return len(contract.retrieval_order) + 1


# ---------------------------------------------------------------------------
# Ranker
# ---------------------------------------------------------------------------


class Ranker:
    """Deterministic-first reranker for assembled evidence items.

    Args:
        contract: The evidence contract for the current task type.  Provides
                  mandatory/recommended class sets and retrieval_order.
    """

    def __init__(self, contract: EvidenceContract) -> None:
        self._contract = contract

    def rank(
        self,
        candidates: list[AssembledItem],
        token_budget: int,
    ) -> list[AssembledItem]:
        """Rank *candidates* and select items up to *token_budget*.

        Returns:
            Ordered list of items that fit within the budget.  Mandatory
            items are included even if they exceed the budget — they are
            placed at the head of the list with their ``inclusion_reason``
            updated to indicate budget overflow for visibility.
        """
        scored = self._score(candidates)
        scored_sorted = sorted(
            scored,
            key=lambda s: (s.tier, s.order_position, s.token_count, s.item_index),
        )
        return self._select(scored_sorted, token_budget)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _score(self, candidates: list[AssembledItem]) -> list[_ScoredItem]:
        return [
            _ScoredItem(
                tier=_tier_for(item.context_class, self._contract),
                order_position=_order_position(item.context_class, self._contract),
                token_count=item.estimated_token_count,
                item_index=idx,
                original=item,
            )
            for idx, item in enumerate(candidates)
        ]

    def _select(
        self,
        scored_sorted: list[_ScoredItem],
        token_budget: int,
    ) -> list[AssembledItem]:
        """Greedily select items respecting the token budget.

        Mandatory items are always included — if they overflow the budget
        their ``inclusion_reason`` is annotated with an overflow notice so
        the pack assembly stage can surface the issue.
        """
        selected: list[AssembledItem] = []
        remaining = token_budget

        for scored in scored_sorted:
            item = scored.original

            if scored.tier == _TIER_MANDATORY:
                # Always include mandatory items — annotate if over budget.
                if scored.token_count > remaining:
                    item = _annotate(
                        item,
                        f"[BUDGET-OVERFLOW mandatory item, "
                        f"cost={scored.token_count}, remaining={remaining}] "
                        + item.inclusion_reason,
                    )
                selected.append(item)
                remaining = max(0, remaining - scored.token_count)

            else:
                if remaining <= 0:
                    break
                if scored.token_count <= remaining:
                    tier_label = _tier_label(scored.tier)
                    item = _annotate(
                        item,
                        f"[{tier_label} rank={scored.order_position}] " + item.inclusion_reason,
                    )
                    selected.append(item)
                    remaining -= scored.token_count
                # else: item doesn't fit — skip (not mandatory)

        return selected


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tier_label(tier: int) -> str:
    labels = {
        _TIER_MANDATORY: "MANDATORY",
        _TIER_RECOMMENDED: "RECOMMENDED",
        _TIER_SUPPLEMENTARY: "SUPPLEMENTARY",
        _TIER_SEMANTIC: "SEMANTIC",
    }
    return labels.get(tier, "UNKNOWN")


def _annotate(item: AssembledItem, new_reason: str) -> AssembledItem:
    """Return a copy of *item* with *new_reason* as inclusion_reason.

    :class:`AssembledItem` is a plain dataclass (not frozen), so we mutate
    ``inclusion_reason`` directly and return the same instance.
    """
    item.inclusion_reason = new_reason
    return item
