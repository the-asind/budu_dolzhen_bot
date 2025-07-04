from ..db.repositories import debt_repo, payment_repo


class PaymentManager:
    """Manages the business logic for handling payments."""

    def __init__(self):
        self._payment_repo = payment_repo
        self._debt_repo = debt_repo

    async def process_payment(
        self, debt_id: int, amount_in_cents: int
    ) -> None:
        """
        Processes a payment for a given debt.

        In a real implementation, this would involve:
        1. Creating a payment record.
        2. Notifying the creditor for confirmation.
        3. Upon confirmation, updating the debt's balance.

        For now, we'll just create the payment record.

        Args:
            debt_id: The ID of the debt being paid.
            amount_in_cents: The amount paid.
        """
        # TODO: Add logic for creditor confirmation.
        # TODO: Add logic to update the debt amount.
        
        await self._payment_repo.create_payment(
            debt_id=debt_id, amount=amount_in_cents
        ) 