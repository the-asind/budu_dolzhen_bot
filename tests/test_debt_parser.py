"""Comprehensive tests for the new DebtParser implementation."""

import pytest
from bot.core import DebtParser, DebtParseError


@pytest.fixture
def author():
    """Fixture providing the author username for debt parser tests."""
    return "author_user"


# region Happy Path Tests
@pytest.mark.parametrize(
    "message, expected",
    [
        # Simple case: one debtor, integer amount
        ("@user1 1230 обед", {"user1": (123000, "обед")}),
        # Multiple debtors, same amount
        ("@user1 @user2 300", {"user1": (30000, ""), "user2": (30000, "")}),
        # Simple arithmetic expression
        ("@user3 500+200 ужин", {"user3": (70000, "ужин")}),
        # Division expression
        ("@user4 3000/3", {"user4": (100000, "")}),
        # 'я' keyword for splitting
        (
            "я @user1 @user2 3000/3 торт",
            {"user1": (100000, "торт"), "user2": (100000, "торт")},
        ),
        # Aggregation across lines
        (
            "@user1 100 обед\n@user1 50 чай",
            {"user1": (15000, "обед, чай")},
        ),
        # Complex aggregation
        (
            "@user1 1230 обед\nя @user1 @user2 3000/3 торт",
            {"user1": (223000, "обед, торт"), "user2": (100000, "торт")},
        ),
    ],
    ids=[
        "single-user-with-comment",
        "multi-user-same-amount",
        "arithmetic-addition",
        "arithmetic-division",
        "ya-keyword-splitting",
        "multi-line-aggregation",
        "complex-multi-line-aggregation",
    ],
)
def test_debt_parser_happy_path(message, expected, author):
    result = DebtParser.parse(message, author)
    assert len(result) == len(expected)
    for user, (amount, comment) in expected.items():
        assert result[user].amount == amount
        assert result[user].combined_comment == comment


# endregion


# region Error Path Tests
@pytest.mark.parametrize(
    "message, error_message",
    [
        ("some random text", "parser_no_mentions"),
        ("@user1", "parser_amount_not_found"),
        ("@user1+@user2 100", "invalid_username_format"),
        ("@user1 100/0", "parser_division_by_zero"),
        ("@usr 100", "invalid_username_format"),
        ("@user1 0", "parser_amount_positive"),
        ("@user1 -50", "parser_amount_positive"),
        ("@user1 @user1 100", "parser_duplicate_mention"),
    ],
    ids=[
        "no-user-mentions",
        "missing-amount",
        "invalid-username-format",
        "division-by-zero",
        "short-username",
        "zero-amount",
        "negative-amount",
        "duplicate-user-mention",
    ],
)
def test_debt_parser_error_path(message, error_message, author):
    with pytest.raises(DebtParseError, match=error_message):
        DebtParser.parse(message, author)


def test_username_case_insensitive(author):
    result = DebtParser.parse("@UserX 100", author)
    assert "userx" in result


# endregion
