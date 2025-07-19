from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Dict, List

from bot.utils.validators import validate_username

__all__ = ["DebtParser", "DebtParseError", "ParsedDebt"]

class DebtParseError(Exception):
    """Raised when a message cannot be parsed into debts."""

@dataclass
class ParsedDebt:
    """Represents aggregated debt information for a single debtor."""
    debtor: str
    amount: int
    comments: List[str] = field(default_factory=list)

    def add(self, add_amount: int, comment: str | None = None) -> None:
        self.amount += add_amount
        if comment and comment not in self.comments:
            self.comments.append(comment)

    @property
    def combined_comment(self) -> str:
        return ", ".join(self.comments)

class DebtParser:
    """Parses free-form debt input messages."""

    @staticmethod
    def parse(message: str, author_username: str) -> Dict[str, ParsedDebt]:
        """Parse a message and return a dictionary of debts."""
        lines = [line.strip() for line in message.splitlines() if line.strip()]
        if not lines:
            raise DebtParseError("Empty message.")

        aggregated_debts: Dict[str, ParsedDebt] = {}

        if len(lines) == 1:
            DebtParser._parse_line(lines[0], author_username, aggregated_debts)
            return aggregated_debts

        for line in lines:
            try:
                DebtParser._parse_line(line, author_username, aggregated_debts)
            except DebtParseError as e:
                raise DebtParseError(f"Failed to parse line '{line}': {e}") from e
        return aggregated_debts

    @staticmethod
    def _parse_line(line: str, author_username: str, aggregated_debts: Dict[str, ParsedDebt]) -> None:
        """Parse single *line* and merge results into *aggregated_debts*.

        The grammar is strictly:
        [names]+ [amount_expr] [comment (optional)]
        where names are @username (≥4 chars) or the single char «я»/«Я».
        Amount expression can contain digits, + - * / with arbitrary spaces.
        Comment is the remainder of the line after the amount token.
        """

        tokens = line.strip().split()
        if not tokens:
            raise DebtParseError("Line does not match expected pattern.")

        name_tokens: list[str] = []
        i = 0
        for tok in tokens:
            if tok.lower() == "я" or tok.startswith("@"):
                name_tokens.append(tok)
                i += 1
            else:
                break

        if not name_tokens:
            raise DebtParseError("No user mentions found.")

        mentions: list[str] = []
        seen: set[str] = set()
        has_self = False
        for ntok in name_tokens:
            if ntok.lower() == "я":
                has_self = True
                continue

            username = ntok[1:]  # strip @
            try:
                username = validate_username(ntok)
                username = username.lower()
            except ValueError as exc:
                raise DebtParseError(str(exc)) from exc

            if username in seen:
                raise DebtParseError("Duplicate user mention")
            seen.add(username)
            mentions.append(username)

        if i >= len(tokens):
            raise DebtParseError("Amount not found.")

        amount_tokens: list[str] = []
        while i < len(tokens):
            tok = tokens[i]
            if re.fullmatch(r"[0-9+\-*/]+", tok):
                amount_tokens.append(tok)
                i += 1
            else:
                break

        if not amount_tokens:
            raise DebtParseError("Amount not found.")

        amount_expr_raw = "".join(amount_tokens)

        try:
            amount_value_float = float(DebtParser._safe_eval(amount_expr_raw))
        except ZeroDivisionError:
            raise DebtParseError("Division by zero")
        except (SyntaxError, TypeError, ValueError):
            raise DebtParseError("Invalid amount expression")

        if amount_value_float <= 0:
            raise DebtParseError("Amount must be positive.")

        # Convert to cents with half-up rounding for fractional results
        share_int = int(amount_value_float * 100 + 0.5)

        comment = " ".join(tokens[i:]).strip()

        # No debtors? (all mentions are author)
        debtors = [m for m in mentions if m != author_username]
        if not debtors:
            raise DebtParseError("No user mentions found.")

        # Amount is already per-debtor (spec). Author never owes himself.
        for debtor in debtors:
            if debtor in aggregated_debts:
                aggregated_debts[debtor].add(share_int, comment)
            else:
                aggregated_debts[debtor] = ParsedDebt(debtor, share_int, [comment] if comment else [])

        return

    @staticmethod
    def _safe_eval(expr: str) -> int:
        """Safely evaluate a simple arithmetic expression."""
        if re.search(r"[^0-9+\-*/]", expr):
            raise TypeError("Invalid characters in expression.")

        tree = ast.parse(expr, mode="eval")

        allowed_nodes = {
            ast.Expression,
            ast.BinOp,
            ast.UnaryOp,
            ast.Constant,
            ast.Num,
            ast.Add,
            ast.Sub,
            ast.Mult,
            ast.Div,
            ast.USub,
        }
        for node in ast.walk(tree):
            if type(node) not in allowed_nodes:
                raise TypeError(f"Unsafe node {type(node).__name__} in expression.")

        result = eval(compile(tree, filename="", mode="eval"))  # noqa: S307 safe by allowed_nodes
        if not isinstance(result, (int, float)):
            raise TypeError("Expression did not evaluate to a number.")

        if abs(result - int(result)) > 1e-9:
            raise ValueError("Expression result must be integer")
        return int(result) 