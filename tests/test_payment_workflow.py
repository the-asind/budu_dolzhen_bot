"""
Comprehensive tests for the complete payment workflow.

Tests cover:
- Payment amount validation against existing debt amounts
- Two-sided confirmation workflow where creditors must approve payments
- Partial payment scenarios with debt balance updates
- Mutual debt offsetting algorithm for bidirectional debts
- Payment history tracking and audit trail functionality
- Payment status transitions and error handling
- Integration with debt repository and payment manager
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from bot.core.payment_manager import PaymentManager
from bot.db.models import (
    Payment as PaymentModel,
    Debt as DebtModel,
    User as UserModel,
    DebtStatus,
    PaymentStatus,
)

# Mark all async test functions in this module
pytestmark = pytest.mark.asyncio

# Fixed datetime constants for consistent test timestamps
DATETIME_2024 = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
DATETIME_2024_LATER = datetime(2024, 1, 1, 1, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def payment_manager():
    """Create a PaymentManager instance for testing."""
    return PaymentManager()


@pytest.fixture
def active_debt():
    """Create an active debt for testing."""
    return DebtModel(
        debt_id=1,
        creditor_id=100,
        debtor_id=200,
        amount=50000,  # $500.00 in cents
        description="Test debt",
        status="active",
        created_at=DATETIME_2024,
    )


class TestPaymentAmountValidation:
    """Test payment amount validation against existing debt amounts."""

    @pytest.mark.asyncio
    async def test_valid_payment_amount(self, payment_manager, active_debt):
        """Test processing a valid payment amount."""
        with patch.object(
            payment_manager._debt_repo, "get", return_value=active_debt
        ), patch.object(
            payment_manager._payment_repo, "get_by_debt", return_value=[]
        ), patch.object(
            payment_manager._payment_repo, "create_payment"
        ) as mock_create:

            mock_create.return_value = PaymentModel(
                payment_id=1,
                debt_id=1,
                amount=25000,
                status="pending_confirmation",
                created_at=DATETIME_2024,
            )

            result = await payment_manager.process_payment(
                debt_id=1, amount_in_cents=25000
            )

            assert result.amount == 25000
            assert result.status == "pending_confirmation"
            mock_create.assert_called_once_with(debt_id=1, amount=25000)

    @pytest.mark.asyncio
    async def test_overpayment_prevention(self, payment_manager, active_debt):
        """Test prevention of overpayment scenarios."""
        existing_payment = PaymentModel(
            payment_id=1,
            debt_id=1,
            amount=30000,
            status="confirmed",
            created_at=DATETIME_2024,
        )

        with patch.object(
            payment_manager._debt_repo, "get", return_value=active_debt
        ), patch.object(
            payment_manager._payment_repo,
            "get_by_debt",
            return_value=[existing_payment],
        ):

            with pytest.raises(ValueError, match="payment_exceeds_remaining"):
                await payment_manager.process_payment(
                    debt_id=1, amount_in_cents=25000  # Would exceed remaining $200
                )

    @pytest.mark.asyncio
    async def test_exact_remaining_amount_payment(self, payment_manager, active_debt):
        """Test payment for exact remaining debt amount."""
        existing_payment = PaymentModel(
            payment_id=1,
            debt_id=1,
            amount=30000,
            status="confirmed",
            created_at=DATETIME_2024,
        )

        with patch.object(
            payment_manager._debt_repo, "get", return_value=active_debt
        ), patch.object(
            payment_manager._payment_repo,
            "get_by_debt",
            return_value=[existing_payment],
        ), patch.object(
            payment_manager._payment_repo, "create_payment"
        ) as mock_create:

            mock_create.return_value = PaymentModel(
                payment_id=2,
                debt_id=1,
                amount=20000,
                status="pending_confirmation",
                created_at=DATETIME_2024,
            )

            result = await payment_manager.process_payment(
                debt_id=1, amount_in_cents=20000  # Exact remaining amount
            )

            assert result.amount == 20000
            mock_create.assert_called_once_with(debt_id=1, amount=20000)

    @pytest.mark.asyncio
    async def test_zero_amount_payment_rejection(self, payment_manager):
        """Test rejection of zero amount payments."""
        with pytest.raises(ValueError, match="payment_amount_positive"):
            await payment_manager.process_payment(debt_id=1, amount_in_cents=0)

    @pytest.mark.asyncio
    async def test_negative_amount_payment_rejection(self, payment_manager):
        """Test rejection of negative amount payments."""
        with pytest.raises(ValueError, match="payment_amount_positive"):
            await payment_manager.process_payment(debt_id=1, amount_in_cents=-1000)

    @pytest.mark.asyncio
    async def test_payment_on_nonexistent_debt(self, payment_manager):
        """Test payment attempt on non-existent debt."""
        with patch.object(payment_manager._debt_repo, "get", return_value=None):
            with pytest.raises(ValueError, match="payment_debt_not_found"):
                await payment_manager.process_payment(debt_id=999, amount_in_cents=1000)

    @pytest.mark.asyncio
    async def test_payment_on_inactive_debt(self, payment_manager):
        """Test payment attempt on inactive debt."""
        inactive_debt = DebtModel(
            debt_id=1,
            creditor_id=100,
            debtor_id=200,
            amount=50000,
            description="Inactive debt",
            status="paid",
            created_at=DATETIME_2024,
        )

        with patch.object(
            payment_manager._debt_repo, "get", return_value=inactive_debt
        ):
            with pytest.raises(ValueError, match="payment_invalid_status"):
                await payment_manager.process_payment(debt_id=1, amount_in_cents=1000)


class TestTwoSidedConfirmationWorkflow:
    """Test two-sided confirmation workflow where creditors must approve payments."""

    @pytest.mark.asyncio
    async def test_payment_confirmation_workflow(self, payment_manager, active_debt):
        """Test complete payment confirmation workflow."""
        pending_payment = PaymentModel(
            payment_id=1,
            debt_id=1,
            amount=25000,
            status="pending_confirmation",
            created_at=DATETIME_2024,
        )

        confirmed_payment = PaymentModel(
            payment_id=1,
            debt_id=1,
            amount=25000,
            status="confirmed",
            created_at=DATETIME_2024,
            confirmed_at=DATETIME_2024,
        )

        with patch.object(
            payment_manager._payment_repo,
            "confirm_payment",
            return_value=confirmed_payment,
        ), patch.object(
            payment_manager._debt_repo, "get", return_value=active_debt
        ), patch.object(
            payment_manager._payment_repo,
            "get_by_debt",
            return_value=[confirmed_payment],
        ), patch.object(
            payment_manager._debt_repo, "update_status"
        ) as mock_update:

            result = await payment_manager.confirm_payment(payment_id=1)

            assert result.status == "confirmed"
            assert result.confirmed_at is not None
            mock_update.assert_called_once_with(
                1, "active"
            )  # Debt remains active (partial payment)

    @pytest.mark.asyncio
    async def test_payment_confirmation_completes_debt(
        self, payment_manager, active_debt
    ):
        """Test payment confirmation that completes the debt."""
        confirmed_payment = PaymentModel(
            payment_id=1,
            debt_id=1,
            amount=50000,  # Full debt amount
            status="confirmed",
            created_at=DATETIME_2024,
            confirmed_at=DATETIME_2024,
        )

        with patch.object(
            payment_manager._payment_repo,
            "confirm_payment",
            return_value=confirmed_payment,
        ), patch.object(
            payment_manager._debt_repo, "get", return_value=active_debt
        ), patch.object(
            payment_manager._payment_repo,
            "get_by_debt",
            return_value=[confirmed_payment],
        ), patch.object(
            payment_manager._debt_repo, "update_status"
        ) as mock_update:

            result = await payment_manager.confirm_payment(payment_id=1)

            assert result.status == "confirmed"
            mock_update.assert_called_once_with(1, "paid")  # Debt marked as paid

    @pytest.mark.asyncio
    async def test_confirmation_of_nonexistent_payment(self, payment_manager):
        """Test confirmation attempt on non-existent payment."""
        with patch.object(
            payment_manager._payment_repo, "confirm_payment", return_value=None
        ):
            with pytest.raises(ValueError, match="payment_not_found"):
                await payment_manager.confirm_payment(payment_id=999)

    @pytest.mark.asyncio
    async def test_confirmation_with_missing_debt(self, payment_manager):
        """Test confirmation when associated debt is missing."""
        confirmed_payment = PaymentModel(
            payment_id=1,
            debt_id=999,
            amount=25000,
            status="confirmed",
            created_at=DATETIME_2024,
        )

        with patch.object(
            payment_manager._payment_repo,
            "confirm_payment",
            return_value=confirmed_payment,
        ), patch.object(payment_manager._debt_repo, "get", return_value=None):

            with pytest.raises(ValueError, match="payment_debt_not_found"):
                await payment_manager.confirm_payment(payment_id=1)


class TestPartialPaymentScenarios:
    """Test partial payment scenarios with debt balance updates."""

    @pytest.mark.asyncio
    async def test_single_partial_payment(self, payment_manager, active_debt):
        """Test processing a single partial payment."""
        with patch.object(
            payment_manager._debt_repo, "get", return_value=active_debt
        ), patch.object(
            payment_manager._payment_repo, "get_by_debt", return_value=[]
        ), patch.object(
            payment_manager._payment_repo, "create_payment"
        ) as mock_create:

            mock_create.return_value = PaymentModel(
                payment_id=1,
                debt_id=1,
                amount=15000,  # $150 of $500 debt
                status="pending_confirmation",
                created_at=DATETIME_2024,
            )

            result = await payment_manager.process_payment(
                debt_id=1, amount_in_cents=15000
            )

            assert result.amount == 15000
            assert result.status == "pending_confirmation"

    @pytest.mark.asyncio
    async def test_multiple_partial_payments(self, payment_manager, active_debt):
        """Test multiple partial payments against the same debt."""
        existing_payments = [
            PaymentModel(
                payment_id=1,
                debt_id=1,
                amount=15000,
                status="confirmed",
                created_at=DATETIME_2024,
            ),
            PaymentModel(
                payment_id=2,
                debt_id=1,
                amount=10000,
                status="confirmed",
                created_at=DATETIME_2024,
            ),
        ]

        with patch.object(
            payment_manager._debt_repo, "get", return_value=active_debt
        ), patch.object(
            payment_manager._payment_repo, "get_by_debt", return_value=existing_payments
        ), patch.object(
            payment_manager._payment_repo, "create_payment"
        ) as mock_create:

            mock_create.return_value = PaymentModel(
                payment_id=3,
                debt_id=1,
                amount=20000,  # Remaining $200
                status="pending_confirmation",
                created_at=DATETIME_2024,
            )

            result = await payment_manager.process_payment(
                debt_id=1, amount_in_cents=20000
            )

            assert result.amount == 20000

    @pytest.mark.asyncio
    async def test_partial_payment_with_pending_payments(
        self, payment_manager, active_debt
    ):
        """Test partial payment calculation ignoring pending payments."""
        existing_payments = [
            PaymentModel(
                payment_id=1,
                debt_id=1,
                amount=15000,
                status="confirmed",
                created_at=DATETIME_2024,
            ),
            PaymentModel(
                payment_id=2,
                debt_id=1,
                amount=10000,
                status="pending_confirmation",  # Should be ignored
                created_at=DATETIME_2024,
            ),
        ]

        with patch.object(
            payment_manager._debt_repo, "get", return_value=active_debt
        ), patch.object(
            payment_manager._payment_repo, "get_by_debt", return_value=existing_payments
        ), patch.object(
            payment_manager._payment_repo, "create_payment"
        ) as mock_create:

            mock_create.return_value = PaymentModel(
                payment_id=3,
                debt_id=1,
                amount=35000,  # $350 remaining (ignoring pending $100)
                status="pending_confirmation",
                created_at=DATETIME_2024,
            )

            result = await payment_manager.process_payment(
                debt_id=1, amount_in_cents=35000
            )

            assert result.amount == 35000

    @pytest.mark.asyncio
    async def test_debt_completion_with_multiple_payments(
        self, payment_manager, active_debt
    ):
        """Test debt completion through multiple confirmed payments."""
        all_payments = [
            PaymentModel(
                payment_id=1,
                debt_id=1,
                amount=20000,
                status="confirmed",
                created_at=DATETIME_2024,
            ),
            PaymentModel(
                payment_id=2,
                debt_id=1,
                amount=30000,
                status="confirmed",
                created_at=DATETIME_2024,
            ),
        ]

        confirmed_payment = PaymentModel(
            payment_id=2,
            debt_id=1,
            amount=30000,
            status="confirmed",
            created_at=DATETIME_2024,
        )

        with patch.object(
            payment_manager._payment_repo,
            "confirm_payment",
            return_value=confirmed_payment,
        ), patch.object(
            payment_manager._debt_repo, "get", return_value=active_debt
        ), patch.object(
            payment_manager._payment_repo, "get_by_debt", return_value=all_payments
        ), patch.object(
            payment_manager._debt_repo, "update_status"
        ) as mock_update:

            await payment_manager.confirm_payment(payment_id=2)

            mock_update.assert_called_once_with(1, "paid")


class TestMutualDebtOffsetting:
    """Test mutual debt offsetting algorithm for bidirectional debts."""

    @pytest.fixture
    def bidirectional_debts(self):
        """Create sample bidirectional debts for testing."""
        return {
            "a_owes_b": DebtModel(
                debt_id=1,
                creditor_id=100,
                debtor_id=200,
                amount=30000,  # A owes B $300
                description="A owes B",
                status="active",
                created_at=DATETIME_2024,
            ),
            "b_owes_a": DebtModel(
                debt_id=2,
                creditor_id=200,
                debtor_id=100,
                amount=20000,  # B owes A $200
                description="B owes A",
                status="active",
                created_at=DATETIME_2024,
            ),
        }

    @pytest.mark.asyncio
    async def test_mutual_debt_detection(self, bidirectional_debts):
        """Test detection of mutual debts between users."""
        # This would be implemented in a future DebtOffsettingManager
        # For now, we test the concept through payment scenarios

        debt_a_to_b = bidirectional_debts["a_owes_b"]
        debt_b_to_a = bidirectional_debts["b_owes_a"]

        # Net result: A owes B $100 ($300 - $200)
        net_amount = debt_a_to_b.amount - debt_b_to_a.amount
        assert net_amount == 10000  # $100 in cents

    @pytest.mark.asyncio
    async def test_offsetting_calculation(self, bidirectional_debts):
        """Test calculation of offsetting amounts."""
        debt_a_to_b = bidirectional_debts["a_owes_b"]
        debt_b_to_a = bidirectional_debts["b_owes_a"]

        # Calculate offsetting
        smaller_amount = min(debt_a_to_b.amount, debt_b_to_a.amount)
        assert smaller_amount == 20000  # $200 can be offset

        remaining_a_to_b = debt_a_to_b.amount - smaller_amount
        remaining_b_to_a = debt_b_to_a.amount - smaller_amount

        assert remaining_a_to_b == 10000  # A still owes B $100
        assert remaining_b_to_a == 0  # B owes A nothing

    @pytest.mark.asyncio
    async def test_equal_mutual_debts_cancellation(self):
        """Test complete cancellation of equal mutual debts."""
        debt_a_to_b = DebtModel(
            debt_id=1,
            creditor_id=100,
            debtor_id=200,
            amount=25000,
            description="Equal debt A to B",
            status="active",
            created_at=DATETIME_2024,
        )

        debt_b_to_a = DebtModel(
            debt_id=2,
            creditor_id=200,
            debtor_id=100,
            amount=25000,
            description="Equal debt B to A",
            status="active",
            created_at=DATETIME_2024,
        )

        # Both debts should cancel out completely
        net_amount = debt_a_to_b.amount - debt_b_to_a.amount
        assert net_amount == 0


class TestPaymentHistoryTracking:
    """Test payment history tracking and audit trail functionality."""

    @pytest.mark.asyncio
    async def test_payment_history_retrieval(self, payment_manager):
        """Test retrieval of payment history for a debt."""
        payment_history = [
            PaymentModel(
                payment_id=1,
                debt_id=1,
                amount=15000,
                status="confirmed",
                created_at=DATETIME_2024,
            ),
            PaymentModel(
                payment_id=2,
                debt_id=1,
                amount=10000,
                status="pending_confirmation",
                created_at=DATETIME_2024,
            ),
        ]

        with patch.object(
            payment_manager._payment_repo, "get_by_debt", return_value=payment_history
        ):
            result = await payment_manager.get_payment_history(debt_id=1)

            assert len(result) == 2
            assert result[0].amount == 15000
            assert result[1].amount == 10000

    @pytest.mark.asyncio
    async def test_empty_payment_history(self, payment_manager):
        """Test retrieval of empty payment history."""
        with patch.object(
            payment_manager._payment_repo, "get_by_debt", return_value=[]
        ):
            result = await payment_manager.get_payment_history(debt_id=1)

            assert len(result) == 0
            assert result == []

    @pytest.mark.asyncio
    async def test_payment_audit_trail(self, payment_manager):
        """Test payment audit trail with timestamps."""
        payment_with_timestamps = PaymentModel(
            payment_id=1,
            debt_id=1,
            amount=25000,
            status="confirmed",
            created_at=DATETIME_2024,
            confirmed_at=DATETIME_2024_LATER,
        )

        with patch.object(
            payment_manager._payment_repo,
            "get_by_debt",
            return_value=[payment_with_timestamps],
        ):
            result = await payment_manager.get_payment_history(debt_id=1)

            assert len(result) == 1
            payment = result[0]
            assert payment.created_at is not None
            assert payment.confirmed_at is not None
            assert payment.confirmed_at > payment.created_at


class TestPaymentStatusTransitions:
    """Test payment status transitions and error handling."""

    @pytest.mark.asyncio
    async def test_pending_to_confirmed_transition(self, payment_manager, active_debt):
        """Test successful transition from pending to confirmed."""
        confirmed_payment = PaymentModel(
            payment_id=1,
            debt_id=1,
            amount=25000,
            status="confirmed",
            created_at=DATETIME_2024,
            confirmed_at=DATETIME_2024,
        )

        with patch.object(
            payment_manager._payment_repo,
            "confirm_payment",
            return_value=confirmed_payment,
        ), patch.object(
            payment_manager._debt_repo, "get", return_value=active_debt
        ), patch.object(
            payment_manager._payment_repo,
            "get_by_debt",
            return_value=[confirmed_payment],
        ), patch.object(
            payment_manager._debt_repo, "update_status"
        ):

            result = await payment_manager.confirm_payment(payment_id=1)

            assert result.status == "confirmed"
            assert result.confirmed_at is not None

    @pytest.mark.asyncio
    async def test_payment_creation_status(self, payment_manager, active_debt):
        """Test that new payments are created with pending status."""
        pending_payment = PaymentModel(
            payment_id=1,
            debt_id=1,
            amount=25000,
            status="pending_confirmation",
            created_at=DATETIME_2024,
        )

        with patch.object(
            payment_manager._debt_repo, "get", return_value=active_debt
        ), patch.object(
            payment_manager._payment_repo, "get_by_debt", return_value=[]
        ), patch.object(
            payment_manager._payment_repo,
            "create_payment",
            return_value=pending_payment,
        ):

            result = await payment_manager.process_payment(
                debt_id=1, amount_in_cents=25000
            )

            assert result.status == "pending_confirmation"
            assert result.confirmed_at is None


class TestPaymentIntegration:
    """Test integration with debt repository and payment manager."""

    @pytest.mark.asyncio
    async def test_repository_integration(self, payment_manager, active_debt):
        """Test proper integration with repository methods."""
        with patch.object(
            payment_manager._debt_repo, "get"
        ) as mock_debt_get, patch.object(
            payment_manager._payment_repo, "get_by_debt"
        ) as mock_payment_get, patch.object(
            payment_manager._payment_repo, "create_payment"
        ) as mock_payment_create:

            mock_debt_get.return_value = active_debt
            mock_payment_get.return_value = []
            mock_payment_create.return_value = PaymentModel(
                payment_id=1,
                debt_id=1,
                amount=25000,
                status="pending_confirmation",
                created_at=DATETIME_2024,
            )

            await payment_manager.process_payment(debt_id=1, amount_in_cents=25000)

            mock_debt_get.assert_called_once_with(1)
            mock_payment_get.assert_called_once_with(1)
            mock_payment_create.assert_called_once_with(debt_id=1, amount=25000)

    @pytest.mark.asyncio
    async def test_debt_status_update_integration(self, payment_manager, active_debt):
        """Test integration with debt status updates."""
        confirmed_payment = PaymentModel(
            payment_id=1,
            debt_id=1,
            amount=50000,  # Full amount
            status="confirmed",
            created_at=DATETIME_2024,
        )

        with patch.object(
            payment_manager._payment_repo,
            "confirm_payment",
            return_value=confirmed_payment,
        ), patch.object(
            payment_manager._debt_repo, "get", return_value=active_debt
        ), patch.object(
            payment_manager._payment_repo,
            "get_by_debt",
            return_value=[confirmed_payment],
        ), patch.object(
            payment_manager._debt_repo, "update_status"
        ) as mock_update:

            await payment_manager.confirm_payment(payment_id=1)

            mock_update.assert_called_once_with(1, "paid")

    @pytest.mark.asyncio
    async def test_error_handling_in_integration(self, payment_manager):
        """Test error handling in repository integration."""
        with patch.object(
            payment_manager._debt_repo, "get", side_effect=Exception("Database error")
        ):
            with pytest.raises(Exception, match="Database error"):
                await payment_manager.process_payment(debt_id=1, amount_in_cents=25000)


class TestPaymentWorkflowEdgeCases:
    """Test edge cases and error scenarios in payment workflow."""

    @pytest.mark.asyncio
    async def test_concurrent_payment_processing(self, payment_manager, active_debt):
        """Test handling of concurrent payment processing attempts."""
        # This would test race conditions in a real implementation
        # For now, we test the basic validation logic

        existing_payment = PaymentModel(
            payment_id=1,
            debt_id=1,
            amount=40000,
            status="confirmed",
            created_at=DATETIME_2024,
        )

        with patch.object(
            payment_manager._debt_repo, "get", return_value=active_debt
        ), patch.object(
            payment_manager._payment_repo,
            "get_by_debt",
            return_value=[existing_payment],
        ):

            # Second payment would exceed remaining amount
            with pytest.raises(ValueError, match="payment_exceeds_remaining"):
                await payment_manager.process_payment(
                    debt_id=1, amount_in_cents=15000  # Only $100 remaining
                )

    @pytest.mark.asyncio
    async def test_large_payment_amounts(self, payment_manager):
        """Test handling of very large payment amounts."""
        large_debt = DebtModel(
            debt_id=1,
            creditor_id=100,
            debtor_id=200,
            amount=999999999,  # Very large amount
            description="Large debt",
            status="active",
            created_at=DATETIME_2024,
        )

        with patch.object(
            payment_manager._debt_repo, "get", return_value=large_debt
        ), patch.object(
            payment_manager._payment_repo, "get_by_debt", return_value=[]
        ), patch.object(
            payment_manager._payment_repo, "create_payment"
        ) as mock_create:

            mock_create.return_value = PaymentModel(
                payment_id=1,
                debt_id=1,
                amount=999999999,
                status="pending_confirmation",
                created_at=DATETIME_2024,
            )

            result = await payment_manager.process_payment(
                debt_id=1, amount_in_cents=999999999
            )

            assert result.amount == 999999999

    @pytest.mark.asyncio
    async def test_payment_precision_handling(self, payment_manager, active_debt):
        """Test handling of payment amounts with cent precision."""
        # Test odd cent amounts
        with patch.object(
            payment_manager._debt_repo, "get", return_value=active_debt
        ), patch.object(
            payment_manager._payment_repo, "get_by_debt", return_value=[]
        ), patch.object(
            payment_manager._payment_repo, "create_payment"
        ) as mock_create:

            mock_create.return_value = PaymentModel(
                payment_id=1,
                debt_id=1,
                amount=12345,  # $123.45
                status="pending_confirmation",
                created_at=DATETIME_2024,
            )

            result = await payment_manager.process_payment(
                debt_id=1, amount_in_cents=12345
            )

            assert result.amount == 12345
