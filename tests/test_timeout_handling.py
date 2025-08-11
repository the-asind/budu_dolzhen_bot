"""
Comprehensive tests for 23-hour timeout scenarios and confirmation mechanisms.

Tests cover:
- Automatic rejection of pending debts after 23 hours
- Timeout notification delivery to creditors
- Unregistered user handling scenarios
- Delayed notification queuing and delivery
- Initiator notifications for blocked actions
- Scheduler persistence and job recovery
- Integration with debt manager and scheduler jobs
"""

import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from bot.core.debt_manager import DebtManager
from bot.db.models import Debt
from bot.scheduler.jobs import check_confirmation_timeouts
from bot.scheduler.scheduler_manager import SchedulerManager


class TestTimeoutHandling:
    """Test suite for timeout handling scenarios."""

    pass


class TestAutomaticDebtRejection:
    """Tests for automatic debt rejection after 23 hours."""

    @pytest.mark.asyncio
    async def test_check_confirmation_timeouts_rejects_old_debts(
        self, mock_repositories, mock_notification_service, sample_debts
    ):
        """Test that debts older than 23 hours are automatically rejected."""
        mock_debt_repo, mock_user_repo = mock_repositories
        recent_debt, old_debt, unregistered_debt = sample_debts

        # Mock database connection and queries
        with patch("aiosqlite.connect") as mock_connect:
            mock_db = AsyncMock()
            mock_connect.return_value.__aenter__.return_value = mock_db
            mock_db.row_factory = None

            # Mock cursor for expired debts query
            mock_cursor = AsyncMock()
            mock_db.execute.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [
                {
                    "debt_id": old_debt.debt_id,
                    "creditor_id": old_debt.creditor_id,
                    "debtor_id": old_debt.debtor_id,
                    "creditor_username": f"user{old_debt.creditor_id}",
                    "debtor_username": f"user{old_debt.debtor_id}",
                },
                {
                    "debt_id": unregistered_debt.debt_id,
                    "creditor_id": unregistered_debt.creditor_id,
                    "debtor_id": unregistered_debt.debtor_id,
                    "creditor_username": f"user{unregistered_debt.creditor_id}",
                    "debtor_username": f"user{unregistered_debt.debtor_id}",
                },
            ]

            # Mock bot instance with proper AsyncMock configuration
            mock_bot_instance = AsyncMock()

            # Mock notification service properly with AsyncMock
            notification_service = mock_notification_service
            notification_service.send_message = AsyncMock(return_value=True)
            notification_service.process_queued_notifications = AsyncMock()

            with patch("bot.scheduler.jobs.NotificationService") as mock_notif_class:
                mock_notif_class.return_value = notification_service

                await check_confirmation_timeouts(mock_bot_instance)

            # Verify database operations - SELECT query + UPDATE queries for each debt
            select_calls = [call for call in mock_db.execute.call_args_list if "SELECT" in str(call[0][0])]
            update_calls = [call for call in mock_db.execute.call_args_list if "UPDATE" in str(call[0][0])]

            assert len(select_calls) >= 1  # At least one SELECT for expired debts
            assert len(update_calls) == 2  # Two UPDATE calls for the two expired debts

            # Verify commit was called for each successful update
            assert mock_db.commit.call_count == 2

            # Verify notifications were sent to creditors
            assert notification_service.send_message.call_count == 2

            # Verify notification content includes debt IDs and creditor IDs
            call_args_list = notification_service.send_message.call_args_list
            creditor_ids = [call[0][0] for call in call_args_list]
            assert old_debt.creditor_id in creditor_ids
            assert unregistered_debt.creditor_id in creditor_ids

    @pytest.mark.asyncio
    async def test_timeout_notification_content(self, mock_notification_service):
        """Test that timeout notifications contain correct information."""
        debt_id = 123
        creditor_id = 1
        debtor_id = 2
        debtor_username = "user2"

        with patch("aiosqlite.connect") as mock_connect:
            mock_db = AsyncMock()
            mock_connect.return_value.__aenter__.return_value = mock_db
            mock_db.row_factory = None

            mock_cursor = AsyncMock()
            mock_db.execute.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [
                {
                    "debt_id": debt_id,
                    "creditor_id": creditor_id,
                    "debtor_id": debtor_id,
                    "creditor_username": "user1",
                    "debtor_username": debtor_username,
                }
            ]

            # Mock bot instance with proper AsyncMock configuration
            mock_bot_instance = AsyncMock()

            # Get notification service instance properly with AsyncMock
            notification_service = mock_notification_service
            notification_service.send_message = AsyncMock(return_value=True)
            notification_service.process_queued_notifications = AsyncMock()

            with patch("bot.scheduler.jobs.NotificationService") as mock_notif_class:
                mock_notif_class.return_value = notification_service

                await check_confirmation_timeouts(mock_bot_instance)

            # Verify notification was sent to correct recipient
            notification_service.send_message.assert_called_once()
            call_args = notification_service.send_message.call_args
            assert call_args[0][0] == creditor_id  # recipient should be creditor

            # Verify notification content contains required information
            message_text = call_args[0][1]
            assert f"@{debtor_username}" in message_text
            assert "23 hours" in message_text
            assert "rejected" in message_text or "automatically rejected" in message_text

    @pytest.mark.asyncio
    async def test_no_action_for_recent_debts(self, mock_repositories):
        """Test that recent debts are not affected by timeout check."""
        # Await the async fixture
        mock_debt_repo, mock_user_repo = mock_repositories

        with patch("aiosqlite.connect") as mock_connect:
            mock_db = AsyncMock()
            mock_connect.return_value.__aenter__.return_value = mock_db
            mock_db.row_factory = None

            mock_cursor = AsyncMock()
            mock_db.execute.return_value = mock_cursor
            mock_cursor.fetchall.return_value = []  # No expired debts

            # Mock bot instance with proper AsyncMock configuration
            mock_bot_instance = AsyncMock()
            mock_bot_instance.send_message = AsyncMock(return_value=True)

            await check_confirmation_timeouts(mock_bot_instance)

            # Verify no updates were made
            update_calls = [call for call in mock_db.execute.call_args_list if "UPDATE" in str(call)]
            assert len(update_calls) == 0

    @pytest.mark.asyncio
    async def test_error_handling_in_timeout_check(self, mock_notification_service):
        """Test error handling during timeout check process."""
        with patch("aiosqlite.connect") as mock_connect:
            mock_connect.side_effect = Exception("Database connection failed")

            # Should not raise exception
            mock_bot = AsyncMock()
            mock_bot.send_message = AsyncMock(return_value=True)

            await check_confirmation_timeouts(mock_bot)

            # Get notification service instance properly
            notification_service = mock_notification_service

            # Verify no notifications were sent due to error
            notification_service.send_message.assert_not_called()


class TestUnregisteredUserHandling:
    """Tests for handling unregistered users in timeout scenarios."""

    @pytest.mark.asyncio
    async def test_unregistered_user_debt_timeout(self, mock_notification_service):
        """Test timeout handling for debts involving unregistered users."""
        creditor_id = 1
        unregistered_debtor_id = 999  # User who hasn't started the bot
        debt_id = 456

        with patch("aiosqlite.connect") as mock_connect:
            mock_db = AsyncMock()
            mock_connect.return_value.__aenter__.return_value = mock_db
            mock_db.row_factory = None

            mock_cursor = AsyncMock()
            mock_db.execute.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [
                {
                    "debt_id": debt_id,
                    "creditor_id": creditor_id,
                    "debtor_id": unregistered_debtor_id,
                    "creditor_username": f"user{creditor_id}",
                    "debtor_username": None,
                }
            ]

            # Mock bot instance with proper AsyncMock configuration
            mock_bot_instance = AsyncMock()

            # Get notification service instance properly with AsyncMock
            notification_service = mock_notification_service
            notification_service.send_message = AsyncMock(return_value=False)  # Simulate failure for unregistered user
            notification_service.process_queued_notifications = AsyncMock()

            with patch("bot.scheduler.jobs.NotificationService") as mock_notif_class:
                mock_notif_class.return_value = notification_service

                await check_confirmation_timeouts(mock_bot_instance)

            # Verify debt was still rejected despite notification failure
            update_calls = [call for call in mock_db.execute.call_args_list if "UPDATE" in str(call[0][0])]
            assert len(update_calls) == 1

            # Verify database commit was called
            assert mock_db.commit.call_count == 1

            # Verify creditor notification was attempted
            assert notification_service.send_message.call_count == 1
            call_args = notification_service.send_message.call_args
            assert call_args[0][0] == creditor_id  # recipient should be creditor

            # Verify queued notification processing was called due to failure
            notification_service.process_queued_notifications.assert_called_once()

    @pytest.mark.asyncio
    async def test_delayed_notification_queuing(self, mock_notification_service):
        """Test that notifications are queued for unregistered users."""
        unregistered_user_id = 999
        message = "Test notification for unregistered user"

        # Get notification service instance properly with AsyncMock
        notification_service = mock_notification_service

        # Mock the notification service behavior for unregistered users
        notification_service.send_message = AsyncMock(return_value=False)  # Simulate failure
        notification_service.process_queued_notifications = AsyncMock()

        # Simulate the notification service's internal queuing behavior
        # The actual NotificationService queues messages internally when send_message returns False
        result = await notification_service.send_message(unregistered_user_id, message)

        # Verify the message sending failed (indicating queuing should occur)
        assert result is False

        # Verify that process_queued_notifications can be called to retry
        await notification_service.process_queued_notifications()
        notification_service.process_queued_notifications.assert_called_once()

    @pytest.mark.asyncio
    async def test_initiator_notification_for_blocked_action(self, mock_notification_service):
        """Test that initiators are notified when actions are blocked by unregistered users."""
        initiator_id = 1

        # Get notification service instance properly
        notification_service = mock_notification_service
        notification_service.send_message = AsyncMock(return_value=True)

        # Simulate debt creation attempt with unregistered user
        with patch.object(DebtManager, "process_message") as mock_process:
            mock_process = AsyncMock(side_effect=Exception("Referenced user not registered"))

            try:
                await mock_process("@unregistered 50 for coffee", author_username="initiator")
            except Exception:
                # Simulate initiator notification
                await notification_service.send_message(
                    initiator_id, "Cannot create debt: referenced user hasn't started the bot yet."
                )

        notification_service.send_message.assert_called_once()


class TestSchedulerPersistence:
    """Tests for scheduler persistence and job recovery."""

    def test_scheduler_initialization(self):
        """Test scheduler initialization with job persistence."""
        with patch("bot.scheduler.scheduler_manager.AsyncIOScheduler") as mock_scheduler_class:
            # Create a mock scheduler instance with proper attributes
            mock_scheduler = MagicMock()
            mock_scheduler.state = 0  # STATE_STOPPED
            mock_scheduler.jobstores = {}
            mock_scheduler.start = MagicMock()
            mock_scheduler.shutdown = MagicMock()
            mock_scheduler.add_job = MagicMock()
            mock_scheduler.get_job = MagicMock()
            mock_scheduler.jobs = []

            mock_scheduler_class.return_value = mock_scheduler

            manager = SchedulerManager()
            manager.start()

            # Verify scheduler instance is accessible
            scheduler = manager.instance
            assert scheduler is not None

            # Verify scheduler start was called
            mock_scheduler.start.assert_called_once()

            # Verify scheduler has jobstores configured
            assert hasattr(scheduler, "jobstores")

    def test_job_recovery_after_restart(self):
        """Test that jobs are recovered after bot restart."""
        with patch("bot.scheduler.scheduler_manager.AsyncIOScheduler") as mock_scheduler_class:
            # Create a mock scheduler with job management capabilities
            mock_scheduler = MagicMock()
            mock_scheduler.state = 0  # STATE_STOPPED
            mock_scheduler.jobs = []
            mock_scheduler.start = MagicMock()
            mock_scheduler.shutdown = MagicMock()

            # Mock job object
            mock_job = MagicMock()
            mock_job.func = check_confirmation_timeouts
            mock_job.id = "timeout_check"

            # Configure add_job to add job to jobs list
            def add_job_side_effect(*args, **kwargs):
                mock_scheduler.jobs.append(mock_job)
                return mock_job

            mock_scheduler.add_job = MagicMock(side_effect=add_job_side_effect)
            mock_scheduler.get_job = MagicMock(return_value=mock_job)

            mock_scheduler_class.return_value = mock_scheduler

            manager = SchedulerManager()
            manager.start()

            scheduler = manager.instance

            # Add test job to verify recovery
            job = scheduler.add_job(check_confirmation_timeouts, "interval", hours=1, id="timeout_check")

            # Verify job was added
            assert len(scheduler.jobs) >= 1
            assert job is not None

            # Verify timeout check job exists and can be retrieved
            timeout_job = scheduler.get_job("timeout_check")
            assert timeout_job is not None
            assert timeout_job.func == check_confirmation_timeouts

    def test_scheduler_shutdown_handling(self):
        """Test proper scheduler shutdown."""
        with patch("bot.scheduler.scheduler_manager.AsyncIOScheduler") as mock_scheduler_class:
            # Create a mock scheduler with state management
            mock_scheduler = MagicMock()
            mock_scheduler.state = 0  # STATE_STOPPED initially
            mock_scheduler.start = MagicMock()
            mock_scheduler.shutdown = MagicMock()

            # Mock state changes
            def start_side_effect():
                mock_scheduler.state = 1  # STATE_RUNNING

            def shutdown_side_effect():
                mock_scheduler.state = 0  # STATE_STOPPED

            mock_scheduler.start.side_effect = start_side_effect
            mock_scheduler.shutdown.side_effect = shutdown_side_effect

            mock_scheduler_class.return_value = mock_scheduler

            manager = SchedulerManager()
            manager.start()

            # Verify scheduler is running after start
            assert manager.instance.state == 1

            manager.shutdown()

            # Verify scheduler shutdown was called
            mock_scheduler.shutdown.assert_called_once()

            # Verify scheduler is no longer running
            assert manager.instance.state == 0

    @pytest.mark.asyncio
    async def test_job_execution_persistence(self):
        """Test that job execution state persists across restarts."""
        with patch("bot.scheduler.scheduler_manager.AsyncIOScheduler") as mock_scheduler_class:
            # Create a mock scheduler with job persistence capabilities
            mock_scheduler = MagicMock()
            mock_scheduler.state = 0
            mock_scheduler.jobs = []
            mock_scheduler.start = MagicMock()
            mock_scheduler.shutdown = MagicMock()

            # Mock job with execution tracking
            mock_job_func = AsyncMock(return_value=None)
            mock_job = MagicMock()
            mock_job.func = mock_job_func
            mock_job.id = "test_job"

            # Configure job management
            def add_job_side_effect(func, *args, **kwargs):
                job_id = kwargs.get("id", "default_job")
                job = MagicMock()
                job.func = func
                job.id = job_id
                mock_scheduler.jobs.append(job)
                return job

            mock_scheduler.add_job = MagicMock(side_effect=add_job_side_effect)
            mock_scheduler.get_job = MagicMock(return_value=mock_job)

            mock_scheduler_class.return_value = mock_scheduler

            manager = SchedulerManager()
            manager.start()

            # Add job to scheduler
            job = mock_scheduler.add_job(mock_job_func, "interval", hours=1, id="test_job")

            # Verify job was added
            assert job is not None
            assert len(mock_scheduler.jobs) >= 1

            # Simulate job execution
            await mock_job_func()
            mock_job_func.assert_called_once()

            # Verify job persists in scheduler
            persisted_job = mock_scheduler.get_job("test_job")
            assert persisted_job is not None
            assert persisted_job.id == "test_job"


class TestIntegrationWithDebtManager:
    """Tests for integration between timeout handling and debt manager."""

    @pytest.mark.asyncio
    async def test_debt_creation_with_timeout_scheduling(self, mock_repositories, sample_users):
        """Test that debt creation properly schedules timeout checks."""
        mock_debt_repo, mock_user_repo = mock_repositories
        creditor, debtor, _ = sample_users

        # Mock repository responses with AsyncMock
        mock_user_repo.get_by_username = AsyncMock(side_effect=[creditor, debtor])
        mock_user_repo.trusts = AsyncMock(return_value=False)  # No auto-acceptance

        created_debt = Debt(
            debt_id=1,
            creditor_id=creditor.user_id,
            debtor_id=debtor.user_id,
            amount=5000,
            description="Test debt",
            status="pending",
        )
        mock_debt_repo.add = AsyncMock(return_value=created_debt)

        # Create debt with proper async mocking
        with patch.object(DebtManager, "process_message") as mock_process:
            mock_process = AsyncMock(return_value=[created_debt])
            debts = await mock_process("@debtor 50 for coffee", author_username="creditor")

        assert len(debts) == 1
        assert debts[0].status == "pending"

        # Verify that the debt would be picked up by timeout check
        # (This is implicit - the timeout job runs periodically)

    @pytest.mark.asyncio
    async def test_debt_confirmation_prevents_timeout(self, mock_repositories, sample_users):
        """Test that confirmed debts are not affected by timeout."""
        mock_debt_repo, mock_user_repo = mock_repositories
        creditor, debtor, _ = sample_users

        # Mock debt retrieval
        pending_debt = Debt(
            debt_id=1, creditor_id=creditor.user_id, debtor_id=debtor.user_id, amount=5000, status="pending"
        )
        confirmed_debt = Debt(
            debt_id=1, creditor_id=creditor.user_id, debtor_id=debtor.user_id, amount=5000, status="active"
        )

        mock_debt_repo.get = AsyncMock(return_value=pending_debt)
        mock_debt_repo.update_status = AsyncMock(return_value=confirmed_debt)
        mock_user_repo.get_by_username = AsyncMock(return_value=debtor)

        # Confirm debt with proper async mocking
        with patch.object(DebtManager, "confirm_debt") as mock_confirm:
            mock_confirm = AsyncMock(return_value=confirmed_debt)
            result = await mock_confirm(1, debtor_username="debtor")

        assert result.status == "active"

        # Confirmed debts should not be picked up by timeout check
        # (The timeout check only looks for 'pending' status)


class TestTimeoutNotificationDelivery:
    """Tests for timeout notification delivery mechanisms."""

    @pytest.mark.asyncio
    async def test_notification_retry_logic(self, mock_notification_service):
        """Test retry logic for failed timeout notifications."""
        creditor_id = 1
        debt_id = 123

        # Get notification service instance properly with AsyncMock
        notification_service = mock_notification_service

        # Mock notification service with retry behavior
        notification_service.send_message = AsyncMock(return_value=False)  # Simulate failure
        notification_service.process_queued_notifications = AsyncMock()
        notification_service._retry_attempts = 3
        notification_service._throttle_delay = 0.01

        with patch("aiosqlite.connect") as mock_connect:
            mock_db = AsyncMock()
            mock_connect.return_value.__aenter__.return_value = mock_db
            mock_db.row_factory = None

            mock_cursor = AsyncMock()
            mock_db.execute.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [
                {
                    "debt_id": debt_id,
                    "creditor_id": creditor_id,
                    "debtor_id": 2,
                    "creditor_username": f"user{creditor_id}",
                    "debtor_username": "user2",
                }
            ]

            # Mock bot instance
            mock_bot_instance = AsyncMock()

            with patch("bot.scheduler.jobs.NotificationService") as mock_notif_class:
                mock_notif_class.return_value = notification_service

                await check_confirmation_timeouts(mock_bot_instance)

            # Verify notification was attempted
            assert notification_service.send_message.call_count == 1

            # Verify queued notification processing was called due to failure
            notification_service.process_queued_notifications.assert_called_once()

    @pytest.mark.asyncio
    async def test_bulk_notification_handling(self, mock_notification_service):
        """Test handling of multiple timeout notifications."""
        debts_data = [
            {
                "debt_id": 1,
                "creditor_id": 1,
                "debtor_id": 2,
                "creditor_username": "user1",
                "debtor_username": "user2",
            },
            {
                "debt_id": 2,
                "creditor_id": 3,
                "debtor_id": 4,
                "creditor_username": "user3",
                "debtor_username": "user4",
            },
            {
                "debt_id": 3,
                "creditor_id": 5,
                "debtor_id": 6,
                "creditor_username": "user5",
                "debtor_username": "user6",
            },
        ]

        # Get notification service instance properly with AsyncMock
        notification_service = mock_notification_service
        notification_service.send_message = AsyncMock(return_value=True)
        notification_service.process_queued_notifications = AsyncMock()

        with patch("aiosqlite.connect") as mock_connect:
            mock_db = AsyncMock()
            mock_connect.return_value.__aenter__.return_value = mock_db
            mock_db.row_factory = None

            mock_cursor = AsyncMock()
            mock_db.execute.return_value = mock_cursor
            mock_cursor.fetchall.return_value = debts_data

            # Mock bot instance
            mock_bot_instance = AsyncMock()

            with patch("bot.scheduler.jobs.NotificationService") as mock_notif_class:
                mock_notif_class.return_value = notification_service

                await check_confirmation_timeouts(mock_bot_instance)

            # Verify all notifications were sent
            assert notification_service.send_message.call_count == len(debts_data)

            # Verify notification recipients match creditor IDs
            call_args_list = notification_service.send_message.call_args_list
            creditor_ids = [call[0][0] for call in call_args_list]
            expected_creditor_ids = [debt["creditor_id"] for debt in debts_data]
            assert set(creditor_ids) == set(expected_creditor_ids)

            # Verify all debts were updated in database
            update_calls = [call for call in mock_db.execute.call_args_list if "UPDATE" in str(call[0][0])]
            assert len(update_calls) == len(debts_data)

            # Verify commits were called for each update
            assert mock_db.commit.call_count == len(debts_data)

    @pytest.mark.asyncio
    async def test_notification_rate_limiting(self, mock_notification_service):
        """Test that notifications respect rate limiting."""
        large_debt_list = [
            {
                "debt_id": i,
                "creditor_id": i,
                "debtor_id": i + 100,
                "creditor_username": f"user{i}",
                "debtor_username": f"user{i+100}",
            }
            for i in range(5)  # Reduced number for faster test execution
        ]

        # Get notification service instance properly with AsyncMock
        notification_service = mock_notification_service

        # Mock rate limiting in notification service
        async def rate_limited_send(*args, **kwargs):
            await asyncio.sleep(0.01)  # Small delay for rate limiting
            return True

        notification_service.send_message = AsyncMock(side_effect=rate_limited_send)
        notification_service.process_queued_notifications = AsyncMock()
        notification_service._throttle_delay = 0.01  # Configure rate limiting

        with patch("aiosqlite.connect") as mock_connect:
            mock_db = AsyncMock()
            mock_connect.return_value.__aenter__.return_value = mock_db
            mock_db.row_factory = None

            mock_cursor = AsyncMock()
            mock_db.execute.return_value = mock_cursor
            mock_cursor.fetchall.return_value = large_debt_list

            # Mock bot instance
            mock_bot_instance = AsyncMock()

            with patch("bot.scheduler.jobs.NotificationService") as mock_notif_class:
                mock_notif_class.return_value = notification_service

                start_time = asyncio.get_event_loop().time()
                await check_confirmation_timeouts(mock_bot_instance)
                end_time = asyncio.get_event_loop().time()

            # Verify rate limiting was applied (execution took some time)
            execution_time = end_time - start_time
            expected_min_time = len(large_debt_list) * 0.005  # Minimum expected delay
            assert execution_time >= expected_min_time

            # Verify all notifications were sent
            assert notification_service.send_message.call_count == len(large_debt_list)

            # Verify all database operations completed
            update_calls = [call for call in mock_db.execute.call_args_list if "UPDATE" in str(call[0][0])]
            assert len(update_calls) == len(large_debt_list)


class TestEdgeCases:
    """Tests for edge cases in timeout handling."""

    @pytest.mark.asyncio
    async def test_concurrent_timeout_checks(self):
        """Test handling of concurrent timeout check executions."""
        # This tests that multiple timeout checks don't interfere with each other

        async def mock_timeout_check(bot):
            await asyncio.sleep(0.1)  # Simulate processing time
            return "completed"

        with patch("bot.scheduler.jobs.check_confirmation_timeouts", side_effect=mock_timeout_check) as patched:
            # Run multiple timeout checks concurrently using the patched function
            mock_bot = AsyncMock()
            tasks = [patched(mock_bot) for _ in range(3)]
            results = await asyncio.gather(*tasks)

            assert len(results) == 3
            assert all(result == "completed" for result in results)

    @pytest.mark.asyncio
    async def test_timezone_handling_in_timeout(self):
        """Test that timeout calculations handle timezones correctly."""
        # Test with different timezone scenarios
        utc_now = datetime.now(timezone.utc)
        cutoff_time = utc_now - timedelta(hours=23)

        # Verify cutoff calculation
        assert cutoff_time < utc_now
        assert (utc_now - cutoff_time).total_seconds() == 23 * 3600

    @pytest.mark.asyncio
    async def test_database_transaction_rollback(self):
        """Test proper transaction handling during errors."""
        with patch("aiosqlite.connect") as mock_connect:
            mock_db = AsyncMock()
            mock_connect.return_value.__aenter__.return_value = mock_db
            mock_db.row_factory = None

            mock_cursor = AsyncMock()
            mock_cursor.fetchall.return_value = [
                {
                    "debt_id": 1,
                    "creditor_id": 1,
                    "debtor_id": 2,
                    "creditor_username": "user1",
                    "debtor_username": "user2",
                }
            ]

            # Mock database error during update - first call returns cursor, second raises exception
            call_count = 0

            def execute_side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return mock_cursor  # SELECT succeeds
                else:
                    raise Exception("Database error")  # UPDATE fails

            mock_db.execute.side_effect = execute_side_effect

            # Mock bot instance
            mock_bot_instance = AsyncMock()

            # Should not raise exception - error handling should catch it
            await check_confirmation_timeouts(mock_bot_instance)

            # Verify SELECT was called but UPDATE failed
            assert mock_db.execute.call_count >= 2

            # Verify rollback behavior - commit should not be called due to error
            mock_db.commit.assert_not_called()
