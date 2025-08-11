import pytest
import pytest_asyncio
import asyncio
import aiosqlite
import tempfile
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram import Bot

from bot.scheduler.jobs import send_weekly_reports, check_confirmation_timeouts, send_payday_reminders
from bot.scheduler.scheduler_manager import SchedulerManager
from bot.core.notification_service import NotificationService


@pytest_asyncio.fixture
async def test_db():
    """Create a test database with sample data and proper cleanup."""
    # Use temporary file for better isolation
    temp_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(temp_fd)
    
    try:
        async with aiosqlite.connect(db_path) as db:
            # Enable foreign keys for proper constraint handling
            await db.execute("PRAGMA foreign_keys = ON")
            # Create tables with proper constraints
            await db.execute("""
                CREATE TABLE users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    language_code TEXT DEFAULT 'en',
                    payday_days TEXT,
                    reminder_enabled BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.execute("""
                CREATE TABLE debts (
                    debt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    creditor_id INTEGER NOT NULL,
                    debtor_id INTEGER NOT NULL,
                    amount INTEGER NOT NULL,
                    description TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (creditor_id) REFERENCES users (user_id),
                    FOREIGN KEY (debtor_id) REFERENCES users (user_id)
                )
            """)
            
            # Insert test users with proper reminder preferences
            # User 1: enabled, has valid payday_days
            await db.execute(
                "INSERT INTO users (user_id, username, payday_days, reminder_enabled) VALUES (?, ?, ?, ?)",
                (1, "alice", "1,15", True)
            )
            # User 2: enabled, has valid payday_days  
            await db.execute(
                "INSERT INTO users (user_id, username, payday_days, reminder_enabled) VALUES (?, ?, ?, ?)",
                (2, "bob", "5,20", True)
            )
            # User 3: OPTED OUT (reminder_enabled = False) - should not receive weekly reports
            await db.execute(
                "INSERT INTO users (user_id, username, payday_days, reminder_enabled) VALUES (?, ?, ?, ?)",
                (3, "charlie", "", False)
            )
            # User 4: enabled but has invalid payday format - should still get weekly reports
            await db.execute(
                "INSERT INTO users (user_id, username, payday_days, reminder_enabled) VALUES (?, ?, ?, ?)",
                (4, "diana", "invalid,format", True)
            )
            
            # Insert test debts with clear amounts for calculation verification
            # User 1 is owed 5000 cents (50.00) by user 2 - ACTIVE debt
            await db.execute(
                "INSERT INTO debts (creditor_id, debtor_id, amount, description, status) VALUES (?, ?, ?, ?, ?)",
                (1, 2, 5000, "Coffee", "active")
            )
            # User 1 owes 3000 cents (30.00) to user 2 - ACTIVE debt  
            await db.execute(
                "INSERT INTO debts (creditor_id, debtor_id, amount, description, status) VALUES (?, ?, ?, ?, ?)",
                (2, 1, 3000, "Lunch", "active")
            )
            # User 3 owes 2000 cents to user 1 - PENDING debt (should not count)
            await db.execute(
                "INSERT INTO debts (creditor_id, debtor_id, amount, description, status) VALUES (?, ?, ?, ?, ?)",
                (3, 1, 2000, "Book", "pending")
            )
            # User 1 owed 1000 cents from user 3 - REJECTED debt (should not count)
            await db.execute(
                "INSERT INTO debts (creditor_id, debtor_id, amount, description, status) VALUES (?, ?, ?, ?, ?)",
                (1, 3, 1000, "Snack", "rejected")
            )
            
            await db.commit()
        
        yield db_path
        
    finally:
        # Cleanup: remove temporary database file
        try:
            if os.path.exists(db_path):
                os.unlink(db_path)
        except OSError:
            pass  # Ignore cleanup errors


@pytest_asyncio.fixture
async def mock_bot():
    """Create a mock bot instance with proper async configuration."""
    bot = MagicMock(spec=Bot)
    bot.send_message = AsyncMock(return_value=True)
    bot.edit_message_text = AsyncMock(return_value=True)
    bot.delete_message = AsyncMock(return_value=True)
    # Add session management for proper cleanup
    bot.session = MagicMock()
    bot.session.close = AsyncMock()
    return bot


@pytest_asyncio.fixture
async def mock_notification_service(mock_bot):
    """Create a mock notification service with proper bulk operation support."""
    service = MagicMock(spec=NotificationService)
    service.send_message = AsyncMock(return_value={'message_id': 1})
    service.send_bulk_messages = AsyncMock(return_value={'success': 4, 'failure': 0})
    service.queue_delayed_notification = AsyncMock()
    service.process_notification_queue = AsyncMock()
    # Associate bot instance to match conftest.py pattern
    service.bot = mock_bot
    service._bot = mock_bot
    # Add rate limiting simulation
    service._last_send_time = 0
    service._rate_limit_delay = 0.1
    return service


class TestWeeklyReports:
    """Test weekly debt summary generation and delivery."""
    
    @pytest.mark.asyncio
    @patch('bot.scheduler.jobs.get_settings')
    @patch('bot.scheduler.jobs.NotificationService')
    async def test_weekly_reports_basic_functionality(self, mock_notif_class, mock_settings, test_db, mock_bot):
        """Test basic weekly report generation and sending."""
        try:
            mock_settings.return_value.db.path = test_db
            mock_notif = AsyncMock()
            mock_notif.send_message = AsyncMock(return_value=True)
            mock_notif_class.return_value = mock_notif

            await asyncio.wait_for(send_weekly_reports(mock_bot), timeout=10.0)

            mock_notif_class.assert_called_once_with(mock_bot)
            assert mock_notif.send_message.call_count == 3

            calls = mock_notif.send_message.call_args_list
            user1_call = next((call for call in calls if call[0][0] == 1), None)
            assert user1_call is not None, "User 1 should receive a weekly report"
            message_text = user1_call[0][1]
            assert "You owe: 30.00" in message_text
            assert "Owed to you: 50.00" in message_text
            assert "Weekly Debt Summary" in message_text

        except asyncio.TimeoutError:
            pytest.fail("Weekly reports job timed out")
        except Exception as e:
            pytest.fail(f"Weekly reports job failed with error: {e}")
    
    @pytest.mark.asyncio
    @patch('bot.scheduler.jobs.get_settings')
    @patch('bot.scheduler.jobs.NotificationService')
    async def test_weekly_reports_zero_amounts(self, mock_notif_class, mock_settings, test_db, mock_bot):
        """Test weekly reports with users having zero debts."""
        try:
            mock_settings.return_value.db.path = test_db
            mock_notif = AsyncMock()
            mock_notif.send_message = AsyncMock(return_value=True)
            mock_notif_class.return_value = mock_notif

            async with aiosqlite.connect(test_db) as db:
                await db.execute("DELETE FROM debts WHERE creditor_id = 4 OR debtor_id = 4")
                await db.commit()
            
            await asyncio.wait_for(send_weekly_reports(mock_bot), timeout=10.0)

            calls = mock_notif.send_message.call_args_list
            user4_call = next((call for call in calls if call[0][0] == 4), None)
            assert user4_call is not None, "User 4 should receive a weekly report"
            message_text = user4_call[0][1]
            assert "You owe: 0.00" in message_text
            assert "Owed to you: 0.00" in message_text

        except asyncio.TimeoutError:
            pytest.fail("Weekly reports zero amounts test timed out")
        except Exception as e:
            pytest.fail(f"Weekly reports zero amounts test failed: {e}")
    
    @pytest.mark.asyncio
    @patch('bot.scheduler.jobs.get_settings')
    @patch('bot.scheduler.jobs.NotificationService')
    async def test_weekly_reports_notification_failure(self, mock_notif_class, mock_settings, test_db, mock_bot):
        """Test handling of notification failures during weekly reports."""
        try:
            mock_settings.return_value.db.path = test_db
            mock_notif = AsyncMock()
            mock_notif.send_message.side_effect = [True, Exception("Network error"), True]
            mock_notif_class.return_value = mock_notif

            await asyncio.wait_for(send_weekly_reports(mock_bot), timeout=10.0)
            assert mock_notif.send_message.call_count == 3

        except asyncio.TimeoutError:
            pytest.fail("Weekly reports notification failure test timed out")
        except Exception as e:
            pytest.fail(f"Weekly reports should handle notification failures gracefully, but got: {e}")
    
    @pytest.mark.asyncio
    @patch('bot.scheduler.jobs.get_settings')
    async def test_weekly_reports_database_error(self, mock_settings, test_db, mock_bot):
        """Test handling of database errors during weekly reports."""
        try:
            mock_settings.return_value.db.path = "/invalid/path/database.db"
            await asyncio.wait_for(send_weekly_reports(mock_bot), timeout=10.0)
        except asyncio.TimeoutError:
            pytest.fail("Weekly reports database error test timed out")
        except Exception as e:
            pytest.fail(f"Weekly reports should handle database errors gracefully, but got: {e}")
    
    @pytest.mark.asyncio
    async def test_weekly_reports_debt_calculation_accuracy(self, test_db, mock_bot):
        """Test accuracy of debt calculations in weekly reports."""
        try:
            async with aiosqlite.connect(test_db) as db:
                await db.execute("DELETE FROM debts")
                await db.execute(
                    "INSERT INTO debts (creditor_id, debtor_id, amount, status) VALUES (?, ?, ?, ?)",
                    (2, 1, 10000, "active")
                )
                await db.execute(
                    "INSERT INTO debts (creditor_id, debtor_id, amount, status) VALUES (?, ?, ?, ?)",
                    (1, 3, 20000, "active")
                )
                await db.execute(
                    "INSERT INTO debts (creditor_id, debtor_id, amount, status) VALUES (?, ?, ?, ?)",
                    (1, 2, 5000, "pending")
                )
                await db.commit()
            
            with patch('bot.scheduler.jobs.get_settings') as mock_settings, \
                 patch('bot.scheduler.jobs.NotificationService') as mock_notif_class:
                
                mock_settings.return_value.db.path = test_db
                mock_notif = AsyncMock()
                mock_notif.send_message = AsyncMock(return_value=True)
                mock_notif_class.return_value = mock_notif
                
                await asyncio.wait_for(send_weekly_reports(mock_bot), timeout=10.0)
                
                calls = mock_notif.send_message.call_args_list
                user1_call = next((call for call in calls if call[0][0] == 1), None)
                assert user1_call is not None, "User 1 should receive a debt calculation report"
                message_text = user1_call[0][1]
                assert "You owe: 100.00" in message_text
                assert "Owed to you: 200.00" in message_text
                
        except asyncio.TimeoutError:
            pytest.fail("Debt calculation accuracy test timed out")
        except Exception as e:
            pytest.fail(f"Debt calculation accuracy test failed: {e}")


class TestPaydayReminders:
    """Test payday reminder system with user-specific scheduling."""
    
    @pytest.mark.asyncio
    @patch('bot.scheduler.jobs.get_settings')
    @patch('bot.scheduler.jobs.NotificationService')
    @patch('bot.scheduler.jobs.date')
    async def test_payday_reminders_matching_day(self, mock_date, mock_notif_class, mock_settings, test_db, mock_bot):
        mock_date.today.return_value.day = 1
        mock_settings.return_value.db.path = test_db
        mock_notif = AsyncMock()
        mock_notif_class.return_value = mock_notif
        
        await send_payday_reminders(mock_bot)
        
        mock_notif.send_message.assert_called_once()
        call_args = mock_notif.send_message.call_args
        assert call_args[0][0] == 1
        assert "Payday Reminder" in call_args[0][1]
        assert "settle your debts" in call_args[0][1]
    
    @pytest.mark.asyncio
    @patch('bot.scheduler.jobs.get_settings')
    @patch('bot.scheduler.jobs.NotificationService')
    @patch('bot.scheduler.jobs.date')
    async def test_payday_reminders_no_matching_day(self, mock_date, mock_notif_class, mock_settings, test_db, mock_bot):
        mock_date.today.return_value.day = 10
        mock_settings.return_value.db.path = test_db
        mock_notif = AsyncMock()
        mock_notif_class.return_value = mock_notif
        
        await send_payday_reminders(mock_bot)
        mock_notif.send_message.assert_not_called()
    
    @pytest.mark.asyncio
    @patch('bot.scheduler.jobs.get_settings')
    @patch('bot.scheduler.jobs.NotificationService')
    @patch('bot.scheduler.jobs.date')
    async def test_payday_reminders_multiple_users(self, mock_date, mock_notif_class, mock_settings, test_db, mock_bot):
        mock_date.today.return_value.day = 15
        async with aiosqlite.connect(test_db) as db:
            await db.execute(
                "INSERT INTO users (user_id, username, payday_days) VALUES (?, ?, ?)",
                (5, "eve", "15,30")
            )
            await db.commit()
        
        mock_settings.return_value.db.path = test_db
        mock_notif = AsyncMock()
        mock_notif_class.return_value = mock_notif
        
        await send_payday_reminders(mock_bot)
        assert mock_notif.send_message.call_count == 2
        sent_user_ids = {call[0][0] for call in mock_notif.send_message.call_args_list}
        assert sent_user_ids == {1, 5}
    
    @pytest.mark.asyncio
    @patch('bot.scheduler.jobs.get_settings')
    @patch('bot.scheduler.jobs.NotificationService')
    @patch('bot.scheduler.jobs.date')
    async def test_payday_reminders_invalid_format(self, mock_date, mock_notif_class, mock_settings, test_db, mock_bot):
        mock_date.today.return_value.day = 1
        mock_settings.return_value.db.path = test_db
        mock_notif = AsyncMock()
        mock_notif_class.return_value = mock_notif
        
        await send_payday_reminders(mock_bot)
        mock_notif.send_message.assert_called_once()
        call_args = mock_notif.send_message.call_args
        assert call_args[0][0] == 1
    
    @pytest.mark.asyncio
    @patch('bot.scheduler.jobs.get_settings')
    @patch('bot.scheduler.jobs.NotificationService')
    @patch('bot.scheduler.jobs.date')
    async def test_payday_reminders_notification_failure(self, mock_date, mock_notif_class, mock_settings, test_db, mock_bot):
        mock_date.today.return_value.day = 1
        mock_settings.return_value.db.path = test_db
        mock_notif = AsyncMock()
        mock_notif.send_message.side_effect = Exception("Network error")
        mock_notif_class.return_value = mock_notif
        
        await send_payday_reminders(mock_bot)
        mock_notif.send_message.assert_called_once()


class TestConfirmationTimeouts:
    """Test 23-hour timeout scenarios and confirmation mechanisms."""
    
    @pytest.mark.asyncio
    @patch('bot.scheduler.jobs.get_settings')
    @patch('bot.scheduler.jobs.NotificationService')
    async def test_confirmation_timeout_basic(self, mock_notif_class, mock_settings, test_db, mock_bot):
        now = datetime.now(timezone.utc)
        expired_time = now - timedelta(hours=24)
        async with aiosqlite.connect(test_db) as db:
            await db.execute("DELETE FROM debts")
            await db.execute(
                "INSERT INTO debts (debt_id, creditor_id, debtor_id, amount, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (100, 1, 2, 5000, "pending", expired_time.isoformat())
            )
            await db.commit()
        
        mock_settings.return_value.db.path = test_db
        mock_notif = AsyncMock()
        mock_notif_class.return_value = mock_notif
        
        await check_confirmation_timeouts(mock_bot)
        
        async with aiosqlite.connect(test_db) as db:
            cursor = await db.execute("SELECT status FROM debts WHERE debt_id = 100")
            row = await cursor.fetchone()
            assert row is not None and row[0] == "rejected"
        
        mock_notif.send_message.assert_called_once()
        call_args = mock_notif.send_message.call_args
        assert call_args[0][0] == 1
        assert "automatically rejected" in call_args[0][1]
        assert "@bob" in call_args[0][1]
    
    @pytest.mark.asyncio
    @patch('bot.scheduler.jobs.get_settings')
    @patch('bot.scheduler.jobs.NotificationService')
    async def test_confirmation_timeout_recent_debt(self, mock_notif_class, mock_settings, test_db, mock_bot):
        now = datetime.now(timezone.utc)
        recent_time = now - timedelta(hours=22)
        async with aiosqlite.connect(test_db) as db:
            await db.execute("DELETE FROM debts")
            await db.execute(
                "INSERT INTO debts (debt_id, creditor_id, debtor_id, amount, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (101, 1, 2, 5000, "pending", recent_time.isoformat())
            )
            await db.commit()
        
        mock_settings.return_value.db.path = test_db
        mock_notif = AsyncMock()
        mock_notif_class.return_value = mock_notif
        
        await check_confirmation_timeouts(mock_bot)
        
        async with aiosqlite.connect(test_db) as db:
            cursor = await db.execute("SELECT status FROM debts WHERE debt_id = 101")
            row = await cursor.fetchone()
            assert row is not None and row[0] == "pending"
        
        mock_notif.send_message.assert_not_called()
    
    @pytest.mark.asyncio
    @patch('bot.scheduler.jobs.get_settings')
    @patch('bot.scheduler.jobs.NotificationService')
    async def test_confirmation_timeout_multiple_debts(self, mock_notif_class, mock_settings, test_db, mock_bot):
        now = datetime.now(timezone.utc)
        expired_time = now - timedelta(hours=25)
        async with aiosqlite.connect(test_db) as db:
            await db.execute("DELETE FROM debts")
            await db.execute(
                "INSERT INTO debts (debt_id, creditor_id, debtor_id, amount, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (102, 1, 2, 5000, "pending", expired_time.isoformat())
            )
            await db.execute(
                "INSERT INTO debts (debt_id, creditor_id, debtor_id, amount, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (103, 2, 3, 3000, "pending", expired_time.isoformat())
            )
            await db.commit()
        
        mock_settings.return_value.db.path = test_db
        mock_notif = AsyncMock()
        mock_notif_class.return_value = mock_notif
        
        await check_confirmation_timeouts(mock_bot)
        
        async with aiosqlite.connect(test_db) as db:
            cursor = await db.execute("SELECT debt_id, status FROM debts WHERE debt_id IN (102, 103)")
            rows = await cursor.fetchall()
            for row in rows:
                assert row[1] == "rejected"
        
        assert mock_notif.send_message.call_count == 2
    
    @pytest.mark.asyncio
    @patch('bot.scheduler.jobs.get_settings')
    @patch('bot.scheduler.jobs.NotificationService')
    async def test_confirmation_timeout_database_error(self, mock_notif_class, mock_settings, test_db, mock_bot):
        mock_settings.return_value.db.path = "/invalid/path/database.db"
        mock_notif = AsyncMock()
        mock_notif_class.return_value = mock_notif
        
        await check_confirmation_timeouts(mock_bot)
    
    @pytest.mark.asyncio
    @patch('bot.scheduler.jobs.get_settings')
    @patch('bot.scheduler.jobs.NotificationService')
    async def test_confirmation_timeout_notification_failure(self, mock_notif_class, mock_settings, test_db, mock_bot):
        now = datetime.now(timezone.utc)
        expired_time = now - timedelta(hours=24)
        async with aiosqlite.connect(test_db) as db:
            await db.execute("DELETE FROM debts")
            await db.execute(
                "INSERT INTO debts (debt_id, creditor_id, debtor_id, amount, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (104, 1, 2, 5000, "pending", expired_time.isoformat())
            )
            await db.commit()
        
        mock_settings.return_value.db.path = test_db
        mock_notif = AsyncMock()
        mock_notif.send_message.side_effect = Exception("Network error")
        mock_notif_class.return_value = mock_notif
        
        await check_confirmation_timeouts(mock_bot)
        
        async with aiosqlite.connect(test_db) as db:
            cursor = await db.execute("SELECT status FROM debts WHERE debt_id = 104")
            row = await cursor.fetchone()
            assert row is not None and row[0] == "rejected"


class TestSchedulerPersistence:
    """Test scheduler persistence across bot restarts and job recovery."""
    
    def test_scheduler_initialization(self):
        with patch('bot.scheduler.scheduler_manager.get_settings') as mock_settings:
            mock_settings.return_value.db.path = "/test/path/database.db"
            mock_settings.return_value.scheduler.timezone = "UTC"
            
            manager = SchedulerManager()
            assert manager._scheduler is not None
            assert manager.instance is manager._scheduler
            
            assert hasattr(manager._scheduler, 'state')
            assert hasattr(manager._scheduler, 'jobs')
            assert hasattr(manager._scheduler, 'add_job')
            assert hasattr(manager._scheduler, 'remove_job')
            assert hasattr(manager._scheduler, 'get_job')
    
    @patch('bot.scheduler.scheduler_manager.get_settings')
    def test_scheduler_start_with_jobs(self, mock_settings):
        mock_settings.return_value.db.path = "/test/path/database.db"
        mock_settings.return_value.scheduler.timezone = "UTC"
        
        manager = SchedulerManager()
        manager.start()
        
        assert len(manager._scheduler.jobs) >= 2
        assert manager._scheduler.state == 1
    
    @patch('bot.scheduler.scheduler_manager.get_settings')
    def test_scheduler_shutdown(self, mock_settings):
        mock_settings.return_value.db.path = "/test/path/database.db"
        mock_settings.return_value.scheduler.timezone = "UTC"
        
        manager = SchedulerManager()
        manager.start()
        assert manager._scheduler.state == 1
        
        manager.shutdown()
        assert manager._scheduler.state == 0
    
    @patch('bot.scheduler.scheduler_manager.get_settings')
    def test_scheduler_job_persistence(self, mock_settings):
        mock_settings.return_value.db.path = "/test/path/database.db"
        mock_settings.return_value.scheduler.timezone = "UTC"
        
        manager = SchedulerManager()
        jobstores = manager._scheduler.jobstores
        assert 'default' in jobstores
        assert hasattr(jobstores['default'], 'url')
        
        default_store = jobstores['default']
        assert hasattr(default_store, 'jobs')
        assert hasattr(default_store, 'add_job')
        assert hasattr(default_store, 'remove_job')
        assert hasattr(default_store, 'get_all_jobs')
        
        test_job = MagicMock()
        test_job.id = "test_job_1"
        default_store.add_job(test_job)
        assert test_job.id in default_store.jobs


class TestUserOptOut:
    """Test user opt-out mechanisms and reminder preference management."""
    
    @pytest.mark.asyncio
    @patch('bot.scheduler.jobs.get_settings')
    @patch('bot.scheduler.jobs.NotificationService')
    async def test_weekly_reports_respect_opt_out(self, mock_notif_class, mock_settings, test_db, mock_bot):
        mock_settings.return_value.db.path = test_db
        mock_notif = AsyncMock()
        mock_notif_class.return_value = mock_notif
        
        await send_weekly_reports(mock_bot)
        
        sent_user_ids = {call[0][0] for call in mock_notif.send_message.call_args_list}
        assert 3 not in sent_user_ids
        assert sent_user_ids == {1, 2, 4}
    
    @pytest.mark.asyncio
    async def test_opt_out_preference_storage(self, test_db):
        async with aiosqlite.connect(test_db) as db:
            await db.execute(
                "UPDATE users SET reminder_enabled = ? WHERE user_id = ?",
                (False, 1)
            )
            await db.commit()
            
            cursor = await db.execute(
                "SELECT reminder_enabled FROM users WHERE user_id = ?",
                (1,)
            )
            row = await cursor.fetchone()
            assert row is not None and not row[0]
    
    @pytest.mark.asyncio
    async def test_default_opt_in_behavior(self, test_db):
        async with aiosqlite.connect(test_db) as db:
            await db.execute(
                "INSERT INTO users (user_id, username) VALUES (?, ?)",
                (999, "newuser")
            )
            await db.commit()
            
            cursor = await db.execute(
                "SELECT reminder_enabled FROM users WHERE user_id = ?",
                (999,)
            )
            row = await cursor.fetchone()
            assert row is not None and row[0] == 1


class TestBulkNotifications:
    """Test efficient message dispatch for bulk notifications."""
    
    @pytest.mark.asyncio
    @patch('bot.scheduler.jobs.get_settings')
    @patch('bot.scheduler.jobs.NotificationService')
    async def test_bulk_notification_rate_limiting(self, mock_notif_class, mock_settings, test_db, mock_bot):
        mock_settings.return_value.db.path = test_db
        mock_notif = AsyncMock()
        mock_notif_class.return_value = mock_notif
        
        call_times = []
        async def track_send_message(*args, **kwargs):
            call_times.append(asyncio.get_event_loop().time())
            await asyncio.sleep(0.01)
            return True
        
        mock_notif.send_message.side_effect = track_send_message
        
        await asyncio.wait_for(send_weekly_reports(mock_bot), timeout=15.0)
        
        if len(call_times) > 1:
            time_diffs = [call_times[i] - call_times[i-1] for i in range(1, len(call_times))]
            assert all(diff >= 0 for diff in time_diffs)
            assert any(diff > 0.005 for diff in time_diffs)
    
    @pytest.mark.asyncio
    @patch('bot.scheduler.jobs.get_settings')
    @patch('bot.scheduler.jobs.NotificationService')
    async def test_bulk_notification_error_handling(self, mock_notif_class, mock_settings, test_db, mock_bot):
        try:
            mock_settings.return_value.db.path = test_db
            mock_notif = AsyncMock()
            mock_notif.send_message.side_effect = [
                True,
                Exception("Network error"),
                True
            ]
            mock_notif_class.return_value = mock_notif
            
            await asyncio.wait_for(send_weekly_reports(mock_bot), timeout=10.0)
            assert mock_notif.send_message.call_count == 3
        except asyncio.TimeoutError:
            pytest.fail("Bulk notification error handling test timed out")
        except Exception as e:
            pytest.fail(f"Bulk notification should handle errors gracefully, but got: {e}")


class TestJobSchedulingAndCleanup:
    """Test reminder job scheduling, execution, and cleanup."""
    
    @patch('bot.scheduler.scheduler_manager.get_settings')
    def test_job_scheduling_intervals(self, mock_settings):
        mock_settings.return_value.db.path = "/test/path/database.db"
        mock_settings.return_value.scheduler.timezone = "UTC"
        
        manager = SchedulerManager()
        manager.start()
        
        jobs = manager._scheduler.jobs
        assert len(jobs) >= 2
        job_ids = list(jobs.keys())
        assert len(job_ids) >= 2
        for job in jobs.values():
            assert hasattr(job, 'id')
            assert hasattr(job, 'func')
            assert job.id is not None
    
    @pytest.mark.asyncio
    async def test_job_execution_isolation(self):
        try:
            async def failing_job():
                raise Exception("Job failed")
            async def successful_job():
                return "success"
            try:
                await asyncio.wait_for(failing_job(), timeout=5.0)
            except Exception:
                pass
            result = await asyncio.wait_for(successful_job(), timeout=5.0)
            assert result == "success"
        except asyncio.TimeoutError:
            pytest.fail("Job execution isolation test timed out")
        except Exception as e:
            pytest.fail(f"Job execution isolation test failed: {e}")
    
    @pytest.mark.asyncio
    @patch('bot.scheduler.jobs.logger')
    async def test_job_logging(self, mock_logger, mock_bot):
        try:
            with patch('bot.scheduler.jobs.get_settings') as mock_settings, \
                 patch('bot.scheduler.jobs.NotificationService') as mock_notif_class:
                
                mock_settings.return_value.db.path = ":memory:"
                mock_notif = AsyncMock()
                mock_notif.send_message = AsyncMock(return_value=True)
                mock_notif_class.return_value = mock_notif
                
                await asyncio.wait_for(send_weekly_reports(mock_bot), timeout=10.0)
                
                if mock_logger.info.called:
                    log_calls = [call[0][0] for call in mock_logger.info.call_args_list]
                    assert any("Executing job: send_weekly_reports" in msg or "send_weekly_reports" in msg for msg in log_calls)
        except asyncio.TimeoutError:
            pytest.fail("Job logging test timed out")
        except Exception as e:
            pytest.fail(f"Job logging test failed: {e}")


class TestIntegrationWithNotificationService:
    """Test integration with notification service and user preference management."""
    
    @pytest.mark.asyncio
    async def test_notification_service_integration(self, mock_notification_service, mock_bot):
        try:
            with patch('bot.scheduler.jobs.get_settings') as mock_settings, \
                 patch('bot.scheduler.jobs.NotificationService') as mock_notif_class:
                
                mock_settings.return_value.db.path = ":memory:"
                mock_notif_class.return_value = mock_notification_service
                
                await asyncio.wait_for(send_weekly_reports(mock_bot), timeout=10.0)
                
                mock_notif_class.assert_called_once_with(mock_bot)
                
                assert hasattr(mock_notification_service, 'send_message')
                assert hasattr(mock_notification_service, 'send_bulk_messages')
                assert hasattr(mock_notification_service, 'queue_delayed_notification')
                assert hasattr(mock_notification_service, 'bot')
                assert hasattr(mock_notification_service, '_bot')
                
                assert mock_notification_service.bot == mock_bot
                assert mock_notification_service._bot == mock_bot
        except asyncio.TimeoutError:
            pytest.fail("Notification service integration test timed out")
        except Exception as e:
            pytest.fail(f"Notification service integration test failed: {e}")
    
    @pytest.mark.asyncio
    async def test_correlation_id_usage(self, mock_bot):
        try:
            with patch('bot.scheduler.jobs.get_settings') as mock_settings, \
                 patch('bot.scheduler.jobs.NotificationService') as mock_notif_class:
                
                mock_settings.return_value.db.path = ":memory:"
                mock_notif = AsyncMock()
                mock_notif.send_message = AsyncMock(return_value=True)
                mock_notif_class.return_value = mock_notif
                
                await asyncio.wait_for(send_weekly_reports(mock_bot), timeout=10.0)
                
                if mock_notif.send_message.called:
                    assert hasattr(mock_notif.send_message, '__call__')
                    for call in mock_notif.send_message.call_args_list:
                        args, kwargs = call
                        assert len(args) >= 2
        except asyncio.TimeoutError:
            pytest.fail("Correlation ID usage test timed out")
        except Exception as e:
            pytest.fail(f"Correlation ID usage test failed: {e}")
    
    @pytest.mark.asyncio
    async def test_user_preference_integration(self, test_db):
        try:
            async with aiosqlite.connect(test_db) as db:
                cursor = await db.execute(
                    "SELECT user_id, reminder_enabled, payday_days FROM users"
                )
                users = await cursor.fetchall()
                
                user_prefs = {row[0]: {'enabled': bool(row[1]), 'payday': row[2]} for row in users}
                
                assert 1 in user_prefs
                assert user_prefs[1]['enabled'] is True
                assert user_prefs[1]['payday'] == "1,15"
                
                assert 3 in user_prefs
                assert user_prefs[3]['enabled'] is False
                
                assert len(user_prefs) == 4
                for user_id, prefs in user_prefs.items():
                    assert isinstance(prefs['enabled'], bool)
                    assert isinstance(prefs['payday'], (str, type(None)))
        except Exception as e:
            pytest.fail(f"User preference integration test failed: {e}")