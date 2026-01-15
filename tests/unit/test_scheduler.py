"""Unit tests for background job scheduler."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from src.jobs.scheduler import JobScheduler, get_scheduler, reset_scheduler
from src.shared.feature_flags import FeatureFlags


class TestJobScheduler:
    """Tests for JobScheduler class."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset scheduler singleton before each test."""
        reset_scheduler()
        yield
        reset_scheduler()

    @pytest.fixture
    def mock_feature_flags(self):
        """Mock feature flags to enable background jobs."""
        with patch("src.jobs.scheduler.get_feature_flags") as mock:
            flags = MagicMock()
            flags.is_enabled.return_value = True
            mock.return_value = flags
            yield flags

    def test_scheduler_initialization(self, mock_feature_flags):
        """Test scheduler initializes correctly."""
        scheduler = JobScheduler()
        assert scheduler is not None
        assert not scheduler.is_running

    def test_scheduler_singleton(self, mock_feature_flags):
        """Test get_scheduler returns singleton."""
        s1 = get_scheduler()
        s2 = get_scheduler()
        assert s1 is s2

    def test_start_with_feature_enabled(self, mock_feature_flags):
        """Test scheduler starts when feature flag is enabled."""
        scheduler = JobScheduler()

        with patch.object(scheduler.scheduler, "start") as mock_start:
            scheduler.start()
            mock_start.assert_called_once()
            assert scheduler.is_running

    def test_start_with_feature_disabled(self):
        """Test scheduler does not start when feature flag is disabled."""
        with patch("src.jobs.scheduler.get_feature_flags") as mock:
            flags = MagicMock()
            flags.is_enabled.return_value = False
            mock.return_value = flags

            scheduler = JobScheduler()
            scheduler.start()

            assert not scheduler.is_running

    def test_shutdown(self, mock_feature_flags):
        """Test scheduler shutdown."""
        scheduler = JobScheduler()

        with patch.object(scheduler.scheduler, "start"):
            scheduler.start()

        with patch.object(scheduler.scheduler, "shutdown") as mock_shutdown:
            scheduler.shutdown()
            mock_shutdown.assert_called_once_with(wait=True)
            assert not scheduler.is_running

    def test_add_job_with_hours(self, mock_feature_flags):
        """Test adding a job with hour interval."""
        scheduler = JobScheduler()

        async def test_task():
            pass

        with patch.object(scheduler.scheduler, "add_job") as mock_add:
            mock_add.return_value = MagicMock(id="test-job")
            job_id = scheduler.add_job(test_task, hours=6, job_id="test-job")

            assert job_id == "test-job"
            mock_add.assert_called_once()

    def test_add_job_with_cron(self, mock_feature_flags):
        """Test adding a job with cron expression."""
        scheduler = JobScheduler()

        async def test_task():
            pass

        with patch.object(scheduler.scheduler, "add_job") as mock_add:
            mock_add.return_value = MagicMock(id="cron-job")
            job_id = scheduler.add_job(test_task, cron="0 6 * * *", job_id="cron-job")

            assert job_id == "cron-job"

    def test_add_job_requires_schedule(self, mock_feature_flags):
        """Test that add_job raises error without schedule."""
        scheduler = JobScheduler()

        async def test_task():
            pass

        with pytest.raises(ValueError, match="Must specify"):
            scheduler.add_job(test_task, job_id="no-schedule")

    def test_remove_job(self, mock_feature_flags):
        """Test removing a job."""
        scheduler = JobScheduler()

        with patch.object(scheduler.scheduler, "remove_job") as mock_remove:
            result = scheduler.remove_job("test-job")
            assert result is True
            mock_remove.assert_called_once_with("test-job")

    def test_remove_nonexistent_job(self, mock_feature_flags):
        """Test removing a job that doesn't exist."""
        scheduler = JobScheduler()

        with patch.object(scheduler.scheduler, "remove_job") as mock_remove:
            mock_remove.side_effect = Exception("Job not found")
            result = scheduler.remove_job("nonexistent")
            assert result is False

    def test_get_jobs(self, mock_feature_flags):
        """Test getting job list."""
        scheduler = JobScheduler()

        mock_job = MagicMock()
        mock_job.id = "test-job"
        mock_job.name = "test"
        mock_job.next_run_time = datetime.now(timezone.utc)
        mock_job.trigger = MagicMock(__str__=lambda s: "interval[6 hours]")

        with patch.object(scheduler.scheduler, "get_jobs", return_value=[mock_job]):
            jobs = scheduler.get_jobs()
            assert len(jobs) == 1
            assert jobs[0]["id"] == "test-job"

    def test_schedule_content_ingestion(self, mock_feature_flags):
        """Test scheduling content ingestion job."""
        scheduler = JobScheduler()

        with patch.object(scheduler, "add_job") as mock_add:
            mock_add.return_value = "content-ingestion"
            job_id = scheduler.schedule_content_ingestion(interval_hours=6)

            assert job_id == "content-ingestion"
            mock_add.assert_called_once()

    def test_schedule_token_cleanup(self, mock_feature_flags):
        """Test scheduling token cleanup job."""
        scheduler = JobScheduler()

        with patch.object(scheduler, "add_job") as mock_add:
            mock_add.return_value = "token-cleanup"
            job_id = scheduler.schedule_token_cleanup(interval_hours=24)

            assert job_id == "token-cleanup"

    def test_schedule_all_default_jobs(self, mock_feature_flags):
        """Test scheduling all default jobs."""
        scheduler = JobScheduler()

        with patch.object(scheduler, "add_job") as mock_add:
            mock_add.return_value = "job"
            job_ids = scheduler.schedule_all_default_jobs()

            assert len(job_ids) == 4  # content, token, review, analytics
            assert mock_add.call_count == 4


class TestScheduledTasks:
    """Tests for scheduled task functions."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session context manager."""
        with patch("src.jobs.tasks.get_db_session") as mock:
            session = AsyncMock()
            mock.return_value.__aenter__.return_value = session
            mock.return_value.__aexit__.return_value = None
            yield session

    @pytest.mark.asyncio
    async def test_run_token_cleanup(self, mock_db_session):
        """Test token cleanup task."""
        from src.jobs.tasks import run_token_cleanup

        # Mock the execute result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [{"id": 1}, {"id": 2}, {"id": 3}]
        mock_db_session.execute.return_value = mock_result

        result = await run_token_cleanup()

        assert result["tokens_removed"] == 3
        assert "completed_at" in result
        assert not result["errors"]

    @pytest.mark.asyncio
    async def test_run_token_cleanup_handles_error(self):
        """Test token cleanup handles errors gracefully."""
        from src.jobs.tasks import run_token_cleanup

        with patch("src.jobs.tasks.get_db_session") as mock:
            mock.return_value.__aenter__.side_effect = Exception("DB error")

            result = await run_token_cleanup()

            assert len(result["errors"]) > 0
            assert "DB error" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_run_review_notifications(self, mock_db_session):
        """Test review notifications task."""
        from src.jobs.tasks import run_review_notifications

        # Mock the execute result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            {"user_id": "user1", "email": "a@b.com", "items_due": 5},
            {"user_id": "user2", "email": "c@d.com", "items_due": 3},
        ]
        mock_db_session.execute.return_value = mock_result

        result = await run_review_notifications()

        assert result["users_notified"] == 2
        assert result["items_due"] == 8
