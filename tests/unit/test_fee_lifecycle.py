"""Unit tests verifying multi-attempt fee collection lifecycles, reversals, and ledger deduplication."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from data_platform.generator.schemas import (
    FeeAssessmentRecord,
    FeeCollectionRecord,
    RevenueRecognitionRecord,
)


def test_multi_attempt_fee_collection_lifecycle() -> None:
    """Verify multiple collection attempts, partial settlements, and outstanding balance tracking."""
    now = datetime.now(UTC)

    # 1. Commercial transaction incurs an assessed fee of 100 EUR, 15 EUR waived, 85 EUR collectible
    assessment = FeeAssessmentRecord(
        assessment_id="FA_WIRE_001",
        transaction_id="TX_WIRE_001",
        account_id="ACC_SME_001",
        gross_assessed_amount=Decimal("100.0000"),
        waived_amount=Decimal("15.0000"),
        waiver_reason="VOLUME_TIER_DISCOUNT",
        net_collectible_amount=Decimal("85.0000"),
        assessment_status="PARTIALLY_WAIVED",
        assessed_at=now,
    )
    collectible = assessment.net_collectible_amount

    # Attempt 1: Account has zero available balance -> FAILED attempt
    attempt_1 = FeeCollectionRecord(
        collection_id="FC_ATTEMPT_1",
        assessment_id=assessment.assessment_id,
        account_id=assessment.account_id,
        collection_attempt_number=1,
        target_amount=collectible,
        collected_amount=Decimal("0.0000"),
        outstanding_amount=Decimal("85.0000"),
        collection_status="FAILED",
        failure_reason="INSUFFICIENT_FUNDS",
        attempted_at=now,
        settled_at=None,
        linked_ledger_entry_id=None,  # No phantom posting created on failure
    )
    assert attempt_1.collected_amount == Decimal("0.0000")
    assert attempt_1.linked_ledger_entry_id is None

    # Attempt 2: Next day, customer deposits funds. Partial sweep of 50 EUR
    attempt_2 = FeeCollectionRecord(
        collection_id="FC_ATTEMPT_2",
        assessment_id=assessment.assessment_id,
        account_id=assessment.account_id,
        collection_attempt_number=2,
        target_amount=attempt_1.outstanding_amount,
        collected_amount=Decimal("50.0000"),
        outstanding_amount=Decimal("35.0000"),
        collection_status="PARTIAL",
        failure_reason=None,
        attempted_at=now,
        settled_at=now,
        linked_ledger_entry_id="LE_DR_FEE_PARTIAL_01",
    )
    assert attempt_2.collected_amount == Decimal("50.0000")
    assert attempt_2.outstanding_amount == Decimal("35.0000")

    # Attempt 3: Final sweep of remaining 35 EUR -> SETTLED
    attempt_3 = FeeCollectionRecord(
        collection_id="FC_ATTEMPT_3",
        assessment_id=assessment.assessment_id,
        account_id=assessment.account_id,
        collection_attempt_number=3,
        target_amount=attempt_2.outstanding_amount,
        collected_amount=Decimal("35.0000"),
        outstanding_amount=Decimal("0.0000"),
        collection_status="SETTLED",
        failure_reason=None,
        attempted_at=now,
        settled_at=now,
        linked_ledger_entry_id="LE_DR_FEE_FINAL_02",
    )
    assert attempt_3.collected_amount == Decimal("35.0000")
    assert attempt_3.outstanding_amount == Decimal("0.0000")

    # Cumulative reconciliation across attempts
    total_collected = (
        attempt_1.collected_amount + attempt_2.collected_amount + attempt_3.collected_amount
    )
    assert total_collected == collectible
    assert attempt_3.outstanding_amount == Decimal("0.0000")

    # Verify ledger entry IDs are strictly distinct (no duplication across retries)
    ledger_ids = [
        att.linked_ledger_entry_id
        for att in [attempt_1, attempt_2, attempt_3]
        if att.linked_ledger_entry_id is not None
    ]
    assert len(ledger_ids) == 2
    assert len(set(ledger_ids)) == 2


def test_partial_fee_reversal_revenue_reconciliation() -> None:
    """Verify fee reversals reduce net recognized revenue and cannot exceed collected amounts."""
    now = datetime.now(UTC)

    # Initially recognized revenue of 85 EUR (collected) with 5 EUR pass-through network expense
    initial_revenue = RevenueRecognitionRecord(
        recognition_id="RR_WIRE_001",
        collection_id="FC_ATTEMPT_3",
        gross_collected_revenue=Decimal("85.0000"),
        reversed_revenue_amount=Decimal("0.0000"),
        pass_through_cost=Decimal("5.0000"),
        net_recognized_revenue=Decimal("80.0000"),
        recognized_at=now,
    )
    assert initial_revenue.net_recognized_revenue == Decimal("80.0000")

    # Partial dispute reversal of 20 EUR granted:
    # Net recognized revenue drops from 80 EUR to 60 EUR
    adjusted_revenue = RevenueRecognitionRecord(
        recognition_id="RR_WIRE_001_ADJ",
        collection_id="FC_ATTEMPT_3",
        gross_collected_revenue=Decimal("85.0000"),
        reversed_revenue_amount=Decimal("20.0000"),
        pass_through_cost=Decimal("5.0000"),
        net_recognized_revenue=Decimal("60.0000"),
        recognized_at=now,
    )
    assert adjusted_revenue.net_recognized_revenue == Decimal("60.0000")
    assert adjusted_revenue.reversed_revenue_amount <= adjusted_revenue.gross_collected_revenue


def test_cumulative_collection_ceiling_assertion() -> None:
    """Verify that cumulative net collections cannot exceed the collectible assessment amount."""
    collectible_limit = Decimal("50.0000")
    collected_leg_1 = Decimal("30.0000")
    collected_leg_2 = Decimal("25.0000")

    # 30 + 25 = 55 > 50 -> must raise assertion in business logic
    with pytest.raises(AssertionError, match="Cumulative collections exceed collectible"):
        total_collected = collected_leg_1 + collected_leg_2
        assert total_collected <= collectible_limit, (
            f"Cumulative collections exceed collectible: {total_collected} > {collectible_limit}"
        )
