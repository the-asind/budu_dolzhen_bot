import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

DebtStatus = Literal["pending", "active", "paid", "rejected"]
PaymentStatus = Literal["pending_confirmation", "confirmed"]


class User(BaseModel):
    """Represents a user in the system."""

    user_id: int
    username: Optional[str] = None
    first_name: str
    last_name: Optional[str] = None
    language_code: str = "ru"
    contact: Optional[str] = None
    payday_days: Optional[str] = None
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.now)


class TrustedUser(BaseModel):
    """Represents a trusted user relationship."""

    user_id: int
    trusted_user_id: int
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)


class Debt(BaseModel):
    """Represents a debt record."""

    debt_id: int
    creditor_id: int
    debtor_id: int
    amount: int  # in cents
    description: Optional[str] = None
    status: DebtStatus = "pending"
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
    confirmed_at: Optional[datetime.datetime] = None
    settled_at: Optional[datetime.datetime] = None

    @field_validator("amount")
    def amount_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v


class Payment(BaseModel):
    """Represents a payment record against a debt."""

    payment_id: int
    debt_id: int
    amount: int  # in cents
    status: PaymentStatus = "pending_confirmation"
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
    confirmed_at: Optional[datetime.datetime] = None

    @field_validator("amount")
    def amount_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v


class NetBalance(BaseModel):
    """Represents the net balance between two users."""

    creditor_id: int
    debtor_id: int
    total_debt: int  # in cents 