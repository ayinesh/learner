"""Scheduled task definitions for background jobs.

This module contains the actual task implementations that are executed
by the JobScheduler. Each task is an async function designed to run
independently in the background.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from src.shared.config import get_settings
from src.shared.database import get_db_session

logger = logging.getLogger(__name__)


async def run_content_ingestion() -> dict[str, Any]:
    """Ingest new content from configured sources.

    This task:
    1. Checks configured content sources (arXiv, YouTube, etc.)
    2. Fetches new content since last ingestion
    3. Generates embeddings for semantic search
    4. Stores content in the database

    Returns:
        Summary of ingestion results.
    """
    logger.info("Starting content ingestion task")
    start_time = datetime.now(timezone.utc)
    results = {
        'started_at': start_time.isoformat(),
        'sources_checked': 0,
        'items_ingested': 0,
        'errors': [],
    }

    try:
        from src.shared.service_registry import get_service_registry

        registry = get_service_registry()
        content_service = registry.content_service

        # Get configured sources from settings
        settings = get_settings()

        # Process each source type
        source_configs = [
            ('arxiv', settings.content_sources.get('arxiv', {})),
            ('youtube', settings.content_sources.get('youtube', {})),
        ]

        for source_type, config in source_configs:
            if not config.get('enabled', False):
                continue

            results['sources_checked'] += 1
            try:
                # Each adapter handles its own ingestion logic
                adapter = content_service.get_adapter(source_type)
                if adapter:
                    ingested = await adapter.ingest_new_content(
                        since=datetime.now(timezone.utc) - timedelta(hours=6)
                    )
                    results['items_ingested'] += len(ingested)
                    logger.info(f"Ingested {len(ingested)} items from {source_type}")
            except Exception as e:
                error_msg = f"Error ingesting from {source_type}: {e}"
                logger.error(error_msg)
                results['errors'].append(error_msg)

    except Exception as e:
        error_msg = f"Content ingestion failed: {e}"
        logger.exception(error_msg)
        results['errors'].append(error_msg)

    results['completed_at'] = datetime.now(timezone.utc).isoformat()
    results['duration_seconds'] = (
        datetime.now(timezone.utc) - start_time
    ).total_seconds()

    logger.info(
        f"Content ingestion completed: {results['items_ingested']} items "
        f"from {results['sources_checked']} sources"
    )
    return results


async def run_token_cleanup() -> dict[str, Any]:
    """Clean up expired authentication tokens.

    This task removes expired tokens from the database to:
    - Maintain security by removing stale credentials
    - Reduce database storage usage
    - Keep the token table performant

    Returns:
        Summary of cleanup results.
    """
    logger.info("Starting token cleanup task")
    start_time = datetime.now(timezone.utc)
    results = {
        'started_at': start_time.isoformat(),
        'tokens_removed': 0,
        'errors': [],
    }

    try:
        now = datetime.now(timezone.utc)

        async with get_db_session() as session:
            from sqlalchemy import text

            # Delete expired refresh tokens
            query = text("""
                DELETE FROM refresh_tokens
                WHERE expires_at < :now
                RETURNING id
            """)
            result = await session.execute(query, {"now": now})
            deleted = result.fetchall()
            results['tokens_removed'] = len(deleted)

        logger.info(f"Removed {len(deleted)} expired refresh tokens")

    except Exception as e:
        error_msg = f"Token cleanup failed: {e}"
        logger.exception(error_msg)
        results['errors'].append(error_msg)

    results['completed_at'] = datetime.now(timezone.utc).isoformat()
    results['duration_seconds'] = (
        datetime.now(timezone.utc) - start_time
    ).total_seconds()

    return results


async def run_review_notifications() -> dict[str, Any]:
    """Send notifications for items due for spaced repetition review.

    This task:
    1. Identifies users with content due for review
    2. Groups items by topic for digestible notifications
    3. Queues notifications (email, push, etc.)

    Returns:
        Summary of notification results.
    """
    logger.info("Starting review notifications task")
    start_time = datetime.now(timezone.utc)
    results = {
        'started_at': start_time.isoformat(),
        'users_notified': 0,
        'items_due': 0,
        'errors': [],
    }

    try:
        now = datetime.now(timezone.utc)

        async with get_db_session() as session:
            from sqlalchemy import text

            # Find users with items due for review
            query = text("""
                SELECT
                    u.id as user_id,
                    u.email,
                    COUNT(sr.id) as items_due
                FROM users u
                JOIN spaced_repetition sr ON sr.user_id = u.id
                WHERE sr.next_review_at <= :now
                AND u.notification_preferences->>'review_reminders' = 'true'
                GROUP BY u.id, u.email
                HAVING COUNT(sr.id) > 0
            """)
            result = await session.execute(query, {"now": now})
            users_with_reviews = result.fetchall()

        for user in users_with_reviews:
            try:
                # In a real implementation, this would queue a notification
                # For now, we just log the intent
                logger.info(
                    f"User {user['user_id']} has {user['items_due']} items due for review"
                )
                results['users_notified'] += 1
                results['items_due'] += user['items_due']
            except Exception as e:
                error_msg = f"Failed to notify user {user['user_id']}: {e}"
                logger.error(error_msg)
                results['errors'].append(error_msg)

    except Exception as e:
        error_msg = f"Review notifications failed: {e}"
        logger.exception(error_msg)
        results['errors'].append(error_msg)

    results['completed_at'] = datetime.now(timezone.utc).isoformat()
    results['duration_seconds'] = (
        datetime.now(timezone.utc) - start_time
    ).total_seconds()

    logger.info(
        f"Review notifications completed: notified {results['users_notified']} users "
        f"about {results['items_due']} items due"
    )
    return results


async def run_analytics_aggregation() -> dict[str, Any]:
    """Aggregate daily analytics for reporting.

    This task computes:
    - Daily active users
    - Session statistics (count, duration, completion rate)
    - Assessment performance metrics
    - Content engagement metrics

    Returns:
        Summary of aggregation results.
    """
    logger.info("Starting analytics aggregation task")
    start_time = datetime.now(timezone.utc)
    results = {
        'started_at': start_time.isoformat(),
        'metrics_computed': 0,
        'errors': [],
    }

    try:
        db = get_db()
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()

        # Compute daily session metrics
        session_metrics = await _compute_session_metrics(db, yesterday)
        results['session_metrics'] = session_metrics
        results['metrics_computed'] += 1

        # Compute daily assessment metrics
        assessment_metrics = await _compute_assessment_metrics(db, yesterday)
        results['assessment_metrics'] = assessment_metrics
        results['metrics_computed'] += 1

        # Compute daily user engagement
        engagement_metrics = await _compute_engagement_metrics(db, yesterday)
        results['engagement_metrics'] = engagement_metrics
        results['metrics_computed'] += 1

        # Store aggregated metrics
        await _store_daily_metrics(db, yesterday, {
            'sessions': session_metrics,
            'assessments': assessment_metrics,
            'engagement': engagement_metrics,
        })

        logger.info(f"Computed {results['metrics_computed']} metric categories for {yesterday}")

    except Exception as e:
        error_msg = f"Analytics aggregation failed: {e}"
        logger.exception(error_msg)
        results['errors'].append(error_msg)

    results['completed_at'] = datetime.now(timezone.utc).isoformat()
    results['duration_seconds'] = (
        datetime.now(timezone.utc) - start_time
    ).total_seconds()

    return results


async def _compute_session_metrics(db, date) -> dict[str, Any]:
    """Compute session-related metrics for a given date."""
    query = """
        SELECT
            COUNT(*) as total_sessions,
            COUNT(DISTINCT user_id) as unique_users,
            AVG(EXTRACT(EPOCH FROM (ended_at - started_at))) as avg_duration_seconds,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END)::float /
                NULLIF(COUNT(*), 0) as completion_rate
        FROM learning_sessions
        WHERE DATE(started_at) = $1
    """
    row = await db.fetchrow(query, date)
    return {
        'total_sessions': row['total_sessions'] or 0,
        'unique_users': row['unique_users'] or 0,
        'avg_duration_seconds': float(row['avg_duration_seconds'] or 0),
        'completion_rate': float(row['completion_rate'] or 0),
    }


async def _compute_assessment_metrics(db, date) -> dict[str, Any]:
    """Compute assessment-related metrics for a given date."""
    query = """
        SELECT
            COUNT(*) as total_assessments,
            AVG(score) as avg_score,
            SUM(CASE WHEN passed THEN 1 ELSE 0 END)::float /
                NULLIF(COUNT(*), 0) as pass_rate
        FROM assessment_attempts
        WHERE DATE(completed_at) = $1
    """
    row = await db.fetchrow(query, date)
    return {
        'total_assessments': row['total_assessments'] or 0,
        'avg_score': float(row['avg_score'] or 0),
        'pass_rate': float(row['pass_rate'] or 0),
    }


async def _compute_engagement_metrics(db, date) -> dict[str, Any]:
    """Compute user engagement metrics for a given date."""
    query = """
        SELECT
            COUNT(DISTINCT user_id) as daily_active_users,
            COUNT(DISTINCT CASE
                WHEN DATE(created_at) = $1 THEN user_id
            END) as new_users
        FROM users
        WHERE DATE(last_login_at) = $1 OR DATE(created_at) = $1
    """
    row = await db.fetchrow(query, date)
    return {
        'daily_active_users': row['daily_active_users'] or 0,
        'new_users': row['new_users'] or 0,
    }


async def _store_daily_metrics(db, date, metrics: dict) -> None:
    """Store aggregated daily metrics in the database."""
    import json

    query = """
        INSERT INTO daily_metrics (date, metrics, created_at)
        VALUES ($1, $2, NOW())
        ON CONFLICT (date)
        DO UPDATE SET metrics = $2, updated_at = NOW()
    """
    await db.execute(query, date, json.dumps(metrics))


async def run_session_cleanup(max_age_days: int = 30) -> dict[str, Any]:
    """Clean up old abandoned sessions.

    This task marks sessions as abandoned if they've been inactive
    for too long without being properly ended.

    Args:
        max_age_days: Days after which inactive sessions are abandoned.

    Returns:
        Summary of cleanup results.
    """
    logger.info("Starting session cleanup task")
    start_time = datetime.now(timezone.utc)
    results = {
        'started_at': start_time.isoformat(),
        'sessions_abandoned': 0,
        'errors': [],
    }

    try:
        db = get_db()
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

        query = """
            UPDATE learning_sessions
            SET status = 'abandoned', ended_at = NOW()
            WHERE status = 'active'
            AND started_at < $1
            RETURNING id
        """
        abandoned = await db.fetch(query, cutoff)
        results['sessions_abandoned'] = len(abandoned)

        logger.info(f"Marked {len(abandoned)} sessions as abandoned")

    except Exception as e:
        error_msg = f"Session cleanup failed: {e}"
        logger.exception(error_msg)
        results['errors'].append(error_msg)

    results['completed_at'] = datetime.now(timezone.utc).isoformat()
    results['duration_seconds'] = (
        datetime.now(timezone.utc) - start_time
    ).total_seconds()

    return results


async def run_embedding_backfill(batch_size: int = 100) -> dict[str, Any]:
    """Backfill embeddings for content missing vector representations.

    This task finds content items without embeddings and generates them.

    Args:
        batch_size: Number of items to process per run.

    Returns:
        Summary of backfill results.
    """
    logger.info("Starting embedding backfill task")
    start_time = datetime.now(timezone.utc)
    results = {
        'started_at': start_time.isoformat(),
        'items_processed': 0,
        'items_failed': 0,
        'errors': [],
    }

    try:
        from src.shared.service_registry import get_service_registry
        from src.shared.feature_flags import FeatureFlags, get_feature_flags

        flags = get_feature_flags()
        if not flags.is_enabled(FeatureFlags.ENABLE_REAL_EMBEDDINGS):
            logger.info("Real embeddings disabled, skipping backfill")
            results['skipped'] = True
            return results

        db = get_db()
        registry = get_service_registry()

        # Find content without embeddings
        query = """
            SELECT id, title, content_type, metadata
            FROM learning_content
            WHERE embedding IS NULL
            ORDER BY created_at DESC
            LIMIT $1
        """
        items = await db.fetch(query, batch_size)

        for item in items:
            try:
                # Generate embedding using content service
                text = f"{item['title']} {item.get('metadata', {}).get('description', '')}"
                embedding = await registry.content_service.generate_embedding(text)

                # Store embedding
                update_query = """
                    UPDATE learning_content
                    SET embedding = $1, embedding_updated_at = NOW()
                    WHERE id = $2
                """
                await db.execute(update_query, embedding, item['id'])
                results['items_processed'] += 1

            except Exception as e:
                error_msg = f"Failed to generate embedding for content {item['id']}: {e}"
                logger.error(error_msg)
                results['items_failed'] += 1
                results['errors'].append(error_msg)

        logger.info(
            f"Embedding backfill completed: {results['items_processed']} processed, "
            f"{results['items_failed']} failed"
        )

    except Exception as e:
        error_msg = f"Embedding backfill failed: {e}"
        logger.exception(error_msg)
        results['errors'].append(error_msg)

    results['completed_at'] = datetime.now(timezone.utc).isoformat()
    results['duration_seconds'] = (
        datetime.now(timezone.utc) - start_time
    ).total_seconds()

    return results
