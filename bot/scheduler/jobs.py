import logging

logger = logging.getLogger(__name__)


async def send_weekly_reports():
    """
    Job to send weekly debt summary reports to all users.
    """
    # TODO:
    # 1. Get all users from the database.
    # 2. For each user, calculate their debt summary (who they owe, who owes them).
    # 3. Format the summary into a message.
    # 4. Use the notification service to send the message.
    logger.info("Executing job: send_weekly_reports")


async def check_confirmation_timeouts():
    """
    Job to reject pending debts that have exceeded the confirmation timeout.
    """
    # TODO:
    # 1. Find all debts with 'pending' status older than 23 hours.
    # 2. For each expired debt, change its status to 'rejected'.
    # 3. Notify the creditor that the debt was not confirmed in time.
    logger.info("Executing job: check_confirmation_timeouts") 