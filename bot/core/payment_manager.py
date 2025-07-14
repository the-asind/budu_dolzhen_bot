from typing import List

from ..db.repositories import DebtRepository, PaymentRepository
from ..db.models import Payment as PaymentModel, Debt as DebtModel


class PaymentManager:
    """Manages the business logic for handling payments."""

    def __init__(self):
        self._payment_repo = PaymentRepository()
        self._debt_repo = DebtRepository()

    async def process_payment(
        self,
        debt_id: int,
        amount_in_cents: int
    ) -> PaymentModel:
        """
        Processes a payment for a given debt.

        Steps:
        1. Validate debt exists and is active.
        2. Validate payment amount.
        3. Prevent overpayment.
        4. Create a pending payment record.

        Args:
            debt_id: The ID of the debt being paid.
            amount_in_cents: The amount paid in cents.

        Returns:
            The created PaymentModel.
        Raises:
            ValueError: If validation fails.
        """
        if amount_in_cents <= 0:
            raise ValueError("Payment amount must be positive")

        debt = await self._debt_repo.get(debt_id)
        if debt is None:
            raise ValueError(f"Debt with id {debt_id} not found")
        if debt.status != "active":
            raise ValueError(
                f"Cannot make payment on debt {debt_id} with status '{debt.status}'"
            )

        existing_payments = await self._payment_repo.get_by_debt(debt_id)
        total_confirmed = sum(p.amount for p in existing_payments if p.status == "confirmed")
        remaining = debt.amount - total_confirmed
        if amount_in_cents > remaining:
            raise ValueError(
                f"Payment amount {amount_in_cents} exceeds remaining debt {remaining}"
            )

        payment = await self._payment_repo.create_payment(
            debt_id=debt_id,
            amount=amount_in_cents
        )

        return payment

    async def confirm_payment(
        self,
        payment_id: int
    ) -> PaymentModel:
        """
        Confirms a pending payment, updates its status, and updates debt status if settled.

        Steps:
        1. Confirm the payment record.
        2. Recalculate total confirmed payments for the debt.
        3. If fully paid, mark debt as 'paid'; otherwise keep 'active'.

        Args:
            payment_id: The ID of the payment to confirm.

        Returns:
            The confirmed PaymentModel.
        Raises:
            ValueError: If payment or debt not found.
        """
        # Confirm the payment
        payment = await self._payment_repo.confirm_payment(payment_id)
        if payment is None:
            raise ValueError(f"Payment with id {payment_id} not found")

        # Retrieve associated debt
        debt = await self._debt_repo.get(payment.debt_id)
        if debt is None:
            raise ValueError(f"Debt with id {payment.debt_id} not found")

        # Sum confirmed payments
        all_payments = await self._payment_repo.get_by_debt(debt.debt_id)
        total_confirmed = sum(p.amount for p in all_payments if p.status == "confirmed")

        # Update debt status if fully paid
        if total_confirmed >= debt.amount:
            await self._debt_repo.update_status(debt.debt_id, "paid")
        else:
            await self._debt_repo.update_status(debt.debt_id, "active")

        return payment

    async def get_payment_history(
        self,
        debt_id: int
    ) -> List[PaymentModel]:
        """
        Retrieves the payment history for a given debt.

        Args:
            debt_id: The ID of the debt.

        Returns:
            List of PaymentModel records ordered by creation time.
        """
        return await self._payment_repo.get_by_debt(debt_id)
