"""Comprehensive tests for the new DebtParser implementation."""

import pytest
from bot.core import DebtParser, DebtParseError

AUTHOR_USERNAME = "author_user"

# region Happy Path Tests
@pytest.mark.parametrize(
    "message, author, expected",
    [
        # Simple case: one debtor, integer amount
        ("@user1 1230 обед", AUTHOR_USERNAME, {"user1": (1230, "обед")}),
        # Multiple debtors, same amount
        ("@user1 @user2 300", AUTHOR_USERNAME, {"user1": (300, ""), "user2": (300, "")}),
        # Simple arithmetic expression
        ("@user3 500+200 ужин", AUTHOR_USERNAME, {"user3": (700, "ужин")}),
        # Division expression
        ("@user4 3000/3", AUTHOR_USERNAME, {"user4": (1000, "")}),
        # 'я' keyword for splitting
        ("я @user1 @user2 3000/3 торт", AUTHOR_USERNAME, {"user1": (1000, "торт"), "user2": (1000, "торт")}),
        # Aggregation across lines
        (
            "@user1 100 обед\n@user1 50 чай",
            AUTHOR_USERNAME,
            {"user1": (150, "обед, чай")},
        ),
        # Complex aggregation
        (
            "@user1 1230 обед\nя @user1 @user2 3000/3 торт",
            AUTHOR_USERNAME,
            {"user1": (2230, "обед, торт"), "user2": (1000, "торт")},
        ),
    ],
)
def test_debt_parser_happy_path(message, author, expected):
    result = DebtParser.parse(message, author)
    assert len(result) == len(expected)
    for user, (amount, comment) in expected.items():
        assert result[user].amount == amount
        assert result[user].combined_comment == comment

# endregion

# region Error Path Tests
@pytest.mark.parametrize(
    "message, author, error_message",
    [
        ("some random text", AUTHOR_USERNAME, "No user mentions found."),
        ("@user1", AUTHOR_USERNAME, "Amount not found."),
        ("@user1+@user2 100", AUTHOR_USERNAME, "Invalid Telegram username format"),
        ("@user1 100/0", AUTHOR_USERNAME, "Division by zero"),
        ("@usr 100", AUTHOR_USERNAME, "Invalid Telegram username format"),
        ("@user1 0", AUTHOR_USERNAME, "Amount must be positive."),
        ("@user1 -50", AUTHOR_USERNAME, "Amount must be positive."),
        ("@user1 @user1 100", AUTHOR_USERNAME, "Duplicate user mention"),
    ],
)
def test_debt_parser_error_path(message, author, error_message):
    with pytest.raises(DebtParseError, match=error_message):
        DebtParser.parse(message, author)

# endregion 