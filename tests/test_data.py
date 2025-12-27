"""Tests for data access layer.

These tests verify:
1. Data loads correctly from JSON files
2. Caching works as expected
3. Sorting is chronological
4. Range queries work correctly
5. Aggregate functions compute correctly
"""

import json
from datetime import date, timedelta
from pathlib import Path
import tempfile

import pytest

from garmin_health.data import HealthData
from garmin_health.models import SleepEntry, DailyStats, WeightEntry, Goals


@pytest.mark.skipif(
    not Path.home().joinpath("Health/Garmin").exists(),
    reason="Real Garmin data not available"
)
class TestHealthDataWithRealData:
    """Tests using real Garmin data."""

    @pytest.fixture
    def data(self):
        """Load real health data."""
        return HealthData.default()

    def test_loads_sleep_data(self, data):
        """Verify sleep data loads."""
        entries = data.sleep()
        assert len(entries) > 0
        assert all(isinstance(e, SleepEntry) for e in entries)

    def test_loads_stats_data(self, data):
        """Verify daily stats loads."""
        entries = data.stats()
        assert len(entries) > 0
        assert all(isinstance(e, DailyStats) for e in entries)

    def test_loads_weight_data(self, data):
        """Verify weight data loads."""
        entries = data.weight()
        assert len(entries) > 0
        assert all(isinstance(e, WeightEntry) for e in entries)

    def test_loads_goals(self, data):
        """Verify goals load."""
        goals = data.goals()
        assert isinstance(goals, Goals)
        assert goals.weight_kg > 0
        assert goals.daily_steps > 0

    def test_sleep_is_chronologically_sorted(self, data):
        """Sleep entries should be sorted oldest first."""
        entries = data.sleep()
        dates = [e.date for e in entries]
        assert dates == sorted(dates), "Sleep data should be sorted chronologically"

    def test_stats_is_chronologically_sorted(self, data):
        """Daily stats should be sorted oldest first."""
        entries = data.stats()
        dates = [e.date for e in entries]
        assert dates == sorted(dates), "Stats data should be sorted chronologically"

    def test_weight_is_chronologically_sorted(self, data):
        """Weight entries should be sorted oldest first."""
        entries = data.weight()
        dates = [e.date for e in entries]
        assert dates == sorted(dates), "Weight data should be sorted chronologically"

    def test_latest_sleep_returns_most_recent(self, data):
        """latest_sleep() should return the most recent entry."""
        latest = data.latest_sleep()
        all_entries = data.sleep()

        assert latest is not None
        assert latest.date == all_entries[-1].date

    def test_latest_weight_returns_most_recent(self, data):
        """latest_weight() should return the most recent entry."""
        latest = data.latest_weight()
        all_entries = data.weight()

        assert latest is not None
        assert latest.date == all_entries[-1].date


class TestCaching:
    """Tests for caching behavior."""

    def test_sleep_is_cached(self):
        """Repeated calls should return cached data."""
        data = HealthData.default()

        entries1 = data.sleep()
        entries2 = data.sleep()

        # Should be the exact same object (cached)
        assert entries1 is entries2

    def test_invalidate_cache_clears_all(self):
        """invalidate_cache() should clear all cached data."""
        data = HealthData.default()

        # Load some data
        _ = data.sleep()
        _ = data.stats()
        assert len(data._cache) > 0

        # Invalidate
        data.invalidate_cache()
        assert len(data._cache) == 0


class TestRangeQueries:
    """Tests for date range queries."""

    @pytest.fixture
    def data(self):
        return HealthData.default()

    def test_sleep_range_filters_correctly(self, data):
        """sleep_range() should filter to date range."""
        # Get last 30 days of entries
        end = date.today()
        start = end - timedelta(days=30)

        entries = data.sleep_range(start, end)

        for e in entries:
            assert start <= e.date <= end

    def test_sleep_last_n_days(self, data):
        """sleep_last_n_days() should return recent entries."""
        entries = data.sleep_last_n_days(7)

        cutoff = date.today() - timedelta(days=7)
        for e in entries:
            assert e.date >= cutoff

    def test_empty_range_returns_empty_list(self, data):
        """Date range with no data should return empty list."""
        # Query a date range in the future
        start = date.today() + timedelta(days=100)
        end = start + timedelta(days=10)

        entries = data.sleep_range(start, end)
        assert entries == []


class TestAggregates:
    """Tests for aggregate helper functions."""

    @pytest.fixture
    def data(self):
        return HealthData.default()

    def test_avg_sleep_hours(self, data):
        """Average sleep should be reasonable."""
        avg = data.avg_sleep_hours(7)

        # Reasonable sleep range: 0-14 hours
        assert 0 <= avg <= 14

    def test_avg_steps(self, data):
        """Average steps should be reasonable."""
        avg = data.avg_steps(7)

        # Reasonable steps range: 0-50000
        assert 0 <= avg <= 50000

    def test_weight_trend(self, data):
        """Weight trend should compute correctly."""
        trend = data.weight_trend(30)

        # Trend should be a reasonable value (-20 to +20 kg over 30 days)
        assert -20 <= trend <= 20

    def test_step_streak(self, data):
        """Step streak should be non-negative."""
        streak = data.step_streak()
        assert streak >= 0


class TestWithMockData:
    """Tests using mock data for precise verification."""

    @pytest.fixture
    def temp_data_dir(self):
        """Create a temporary directory with mock data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create mock sleep data
            sleep_data = [
                {"_date": "2025-01-01", "dailySleepDTO": {"sleepTimeSeconds": 25200}},
                {"_date": "2025-01-02", "dailySleepDTO": {"sleepTimeSeconds": 28800}},
                {"_date": "2025-01-03", "dailySleepDTO": {"sleepTimeSeconds": 21600}},
            ]
            with open(tmpdir / "sleep.json", "w") as f:
                json.dump(sleep_data, f)

            # Create mock stats data
            stats_data = [
                {"_date": "2025-01-01", "totalSteps": 8000},
                {"_date": "2025-01-02", "totalSteps": 12000},
                {"_date": "2025-01-03", "totalSteps": 5000},
            ]
            with open(tmpdir / "daily_stats.json", "w") as f:
                json.dump(stats_data, f)

            # Create mock weight data
            weight_data = {
                "dailyWeightSummaries": [
                    {"summaryDate": "2025-01-01", "maxWeight": 85000},
                    {"summaryDate": "2025-01-02", "maxWeight": 84500},
                    {"summaryDate": "2025-01-03", "maxWeight": 84000},
                ]
            }
            with open(tmpdir / "weight.json", "w") as f:
                json.dump(weight_data, f)

            # Create mock goals
            goals_data = {
                "weight_kg": 80,
                "daily_steps": 10000,
                "sleep_hours": 8,
                "workouts_per_week": 3,
            }
            with open(tmpdir / "goals.json", "w") as f:
                json.dump(goals_data, f)

            yield tmpdir

    def test_loads_mock_sleep(self, temp_data_dir):
        """Verify mock sleep data loads correctly."""
        data = HealthData(temp_data_dir)
        entries = data.sleep()

        assert len(entries) == 3
        assert entries[0].date == date(2025, 1, 1)
        assert entries[0].duration_hours == 7.0  # 25200 / 3600
        assert entries[1].duration_hours == 8.0
        assert entries[2].duration_hours == 6.0

    def test_loads_mock_stats(self, temp_data_dir):
        """Verify mock stats data loads correctly."""
        data = HealthData(temp_data_dir)
        entries = data.stats()

        assert len(entries) == 3
        assert entries[0].total_steps == 8000
        assert entries[1].total_steps == 12000

    def test_loads_mock_weight(self, temp_data_dir):
        """Verify mock weight data loads correctly."""
        data = HealthData(temp_data_dir)
        entries = data.weight()

        assert len(entries) == 3
        assert entries[0].weight_kg == 85.0
        assert entries[2].weight_kg == 84.0

    def test_loads_mock_goals(self, temp_data_dir):
        """Verify mock goals load correctly."""
        data = HealthData(temp_data_dir)
        goals = data.goals()

        assert goals.weight_kg == 80
        assert goals.daily_steps == 10000

    def test_step_streak_with_mock_data(self, temp_data_dir):
        """Verify step streak calculation."""
        data = HealthData(temp_data_dir)

        # With goal of 10000:
        # Day 3: 5000 (below goal) - streak ends
        # So streak should be 0 (most recent day is below goal)
        streak = data.step_streak(goal=10000)
        assert streak == 0

        # With goal of 4000:
        # All days meet goal, streak = 3
        streak = data.step_streak(goal=4000)
        assert streak == 3


class TestMissingFiles:
    """Tests for graceful handling of missing files."""

    @pytest.fixture
    def empty_data_dir(self):
        """Create empty temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_missing_sleep_returns_empty(self, empty_data_dir):
        """Missing sleep.json should return empty list."""
        data = HealthData(empty_data_dir)
        assert data.sleep() == []

    def test_missing_stats_returns_empty(self, empty_data_dir):
        """Missing daily_stats.json should return empty list."""
        data = HealthData(empty_data_dir)
        assert data.stats() == []

    def test_missing_weight_returns_empty(self, empty_data_dir):
        """Missing weight.json should return empty list."""
        data = HealthData(empty_data_dir)
        assert data.weight() == []

    def test_missing_goals_returns_defaults(self, empty_data_dir):
        """Missing goals.json should return default goals."""
        data = HealthData(empty_data_dir)
        goals = data.goals()

        assert goals.weight_kg == 75.0  # Default
        assert goals.daily_steps == 10000  # Default

    def test_latest_sleep_with_no_data(self, empty_data_dir):
        """latest_sleep() with no data should return None."""
        data = HealthData(empty_data_dir)
        assert data.latest_sleep() is None

    def test_avg_sleep_with_no_data(self, empty_data_dir):
        """avg_sleep_hours() with no data should return 0."""
        data = HealthData(empty_data_dir)
        assert data.avg_sleep_hours() == 0.0
