import logging
import aiosqlite
from aiogram import Bot

from datetime import datetime, timedelta, timezone, date

from ..config import get_settings
from ..core.notification_service import NotificationService

logger = logging.getLogger(__name__)


async def send_weekly_reports(bot: Bot | None = None):
    """
    Job to send weekly debt summary reports to all users.
    """
    logger.info("Executing job: send_weekly_reports")
    settings = get_settings()
    created = False
    if bot is None:
        bot = Bot(settings.bot.token)
        created = True
    db_path = settings.db.path
    notif = NotificationService(bot)
    try:
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            users_cursor = await db.execute("SELECT user_id, username FROM users WHERE reminder_enabled = 1")
            users = await users_cursor.fetchall()

            for user in users:
                user_id = user["user_id"]
                try:
                    owe_cursor = await db.execute(
                        "SELECT SUM(amount) AS total FROM debts WHERE debtor_id = ? AND status = 'active'",
                        (user_id,),
                    )
                    owe_row = await owe_cursor.fetchone()
                    owes_total = owe_row["total"] or 0

                    owed_cursor = await db.execute(
                        "SELECT SUM(amount) AS total FROM debts WHERE creditor_id = ? AND status = 'active'",
                        (user_id,),
                    )
                    owed_row = await owed_cursor.fetchone()
                    owed_total = owed_row["total"] or 0

                    text = (
                        f"📊 Weekly Debt Summary 📊\n\n"
                        f"You owe: {owes_total / 100:.2f}\n"
                        f"Owed to you: {owed_total / 100:.2f}\n\n"
                        f"Have a great week!"
                    )
                    await notif.send_message(user_id, text)
                except Exception as e:
                    logger.error(f"Failed to send weekly report to {user_id}: {e}")

        logger.info("Weekly reports job completed successfully.")
    except Exception as e:
        logger.error(f"Error in send_weekly_reports job: {e}")
    finally:
        if created:
            await bot.session.close()


async def check_confirmation_timeouts(bot: Bot | None = None):
    """
    Job to reject pending debts that have exceeded the confirmation timeout.
    """
    logger.info("Executing job: check_confirmation_timeouts")
    settings = get_settings()
    created = False
    if bot is None:
        bot = Bot(settings.bot.token)
        created = True
    db_path = settings.db.path
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(hours=23)
    try:
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            # select debts pending before cutoff
            cursor = await db.execute(
                "SELECT debt_id, creditor_id, debtor_id FROM debts " "WHERE status = 'pending' AND created_at < ?",
                (cutoff.isoformat(),),
            )
            expired = await cursor.fetchall()

            notif = NotificationService(bot)

            for row in expired:
                debt_id = row["debt_id"]
                creditor_id = row["creditor_id"]
                debtor_id = row["debtor_id"]

                # update status to rejected
                try:
                    await db.execute(
                        "UPDATE debts SET status = 'rejected', updated_at = ? WHERE debt_id = ?",
                        (now_utc.isoformat(), debt_id),
                    )
                    await db.commit()
                except Exception as e:
                    logger.error(f"Failed to update debt {debt_id} status: {e}")
                    continue

                # notify creditor
                text = (
                    f"⚠️ Debt #{debt_id} from user {debtor_id} was not confirmed within 23 hours "
                    f"and has been automatically rejected."
                )
                try:
                    ok = await notif.send_message(creditor_id, text)
                    if not ok:
                        # If notification failed (e.g., user unregistered), process queue
                        await notif.process_queued_notifications()
                except Exception as e:
                    logger.error(f"Failed to notify creditor {creditor_id} for debt {debt_id}: {e}")
                    # Try to process queued notifications in case of error
                    try:
                        await notif.process_queued_notifications()
                    except Exception as e2:
                        logger.error(f"Failed to process queued notifications: {e2}")

        logger.info("Confirmation timeout check completed.")
    except Exception as e:
        logger.error(f"Error in check_confirmation_timeouts job: {e}")
    finally:
        if created:
            await bot.session.close()


async def send_payday_reminders(bot: Bot | None = None):
    """
    Job to send payday reminders to users based on their payday_days setting.
    """
    logger.info("Executing job: send_payday_reminders")
    settings = get_settings()
    created = False
    if bot is None:
        bot = Bot(settings.bot.token)
        created = True
    db_path = settings.db.path
    today_day = date.today().day
    try:
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            # fetch users with payday_days configured
            cursor = await db.execute(
                "SELECT user_id, payday_days FROM users WHERE payday_days IS NOT NULL AND payday_days != ''"
            )
            users = await cursor.fetchall()

            notif = NotificationService(bot)

            for user in users:
                user_id = user["user_id"]
                raw = user["payday_days"]
                try:
                    days = [int(d.strip()) for d in raw.split(",") if d.strip().isdigit()]
                    # Validate day numbers are in valid range
                    days = [d for d in days if 1 <= d <= 31]
                    if not days:
                        logger.warning(f"No valid days for user {user_id} after filtering")
                        continue
                except Exception:
                    logger.warning(f"Invalid payday_days format for user {user_id}: '{raw}'")
                    continue
                if today_day in days:
                    text = (
                        "💰 Payday Reminder 💰\n\n"
                        "Today is one of your configured payday days. "
                        "Don't forget to review and settle your debts!"
                    )
                    try:
                        await notif.send_message(user_id, text)
                    except Exception as e:
                        logger.error(f"Failed to send payday reminder to {user_id}: {e}")

        logger.info("Payday reminders job completed.")
    except Exception as e:
        logger.error(f"Error in send_payday_reminders job: {e}")
    finally:
        if created:
            await bot.session.close()
