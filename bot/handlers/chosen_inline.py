from aiogram import Router
from aiogram.types import ChosenInlineResult
from bot.core.debt_parser import DebtParser
from bot.core.debt_manager import DebtManager
from bot.db.repositories import UserRepository
from bot.core.notification_service import NotificationService
from bot.locales.main import _

chosen_router = Router(name="chosen_inline")

@chosen_router.chosen_inline_result()
async def handle_chosen_inline_result(
    chosen: ChosenInlineResult,
    notification_service: NotificationService,
):
    author = chosen.from_user.username or ""
    creditor = await UserRepository.get_by_username(author)

    parsed = DebtParser.parse(chosen.query, author_username=author)
    lines = []
    for debtor, pd in parsed.items():
        amount = f"{pd.amount/100:.2f}" if isinstance(pd.amount, int) else str(pd.amount)
        comment = pd.combined_comment or ""
        lines.append(f"@{debtor} {amount} {comment}".strip())

    if chosen.result_id == "all":
        summary = _("inline_bulk_debt_message").format(author=author, lines="\n".join(lines))
        debts = await DebtManager.process_message(
            author_username=author, message=summary
        )
        # send notifications
        for debt in debts:
            debtor_user = await UserRepository.get_by_username(debt.debtor_username)
            if debtor_user and creditor:
                await notification_service.send_debt_confirmation_request(debt, creditor, debtor_user)
        return

    if chosen.result_id.startswith("single_"):
        idx = int(chosen.result_id.split("_", 1)[1])
        line_text = lines[idx]
        debts = await DebtManager.process_message(
            author_username=author, message=line_text
        )
        debt = debts[0]
        debtor_user = await UserRepository.get_by_id(debt.debtor_id)
        if debtor_user and creditor:
            await notification_service.send_debt_confirmation_request(debt, creditor, debtor_user)
        return
    