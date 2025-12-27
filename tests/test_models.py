"""Tests for Pydantic models.

These tests verify:
1. Models parse actual Garmin API data correctly
2. None values are handled gracefully (the main bug we're preventing)
3. Computed properties work as expected
"""

import json
from datetime import date
from pathlib import Path


from garmin_health.models import (
    SleepEntry,
    DailyStats,
    WeightEntry,
    StressEntry,
    BodyBatteryEntry,
    Goals,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    """Load a JSON fixture file."""
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


# ============================================================================
# SleepEntry Tests
# ============================================================================

class TestSleepEntry:
    """Tests for SleepEntry model."""

    def test_from_garmin_with_real_data(self):
        """Parse actual Garmin sleep data."""
        data = load_fixture("sleep_sample.json")
        entry = SleepEntry.from_garmin(data)

        assert isinstance(entry.date, date)
        assert entry.duration_seconds >= 0
        assert entry.duration_hours >= 0

    def test_handles_none_daily_sleep_dto(self):
        """Garmin sometimes returns null dailySleepDTO."""
        data = {"_date": "2025-01-01", "dailySleepDTO": None}
        entry = SleepEntry.from_garmin(data)

        assert entry.date == date(2025, 1, 1)
        assert entry.duration_seconds == 0
        assert entry.duration_hours == 0.0
        assert entry.score == 0

    def test_handles_missing_sleep_scores(self):
        """sleepScores can be missing or null."""
        data = {
            "_date": "2025-01-01",
            "dailySleepDTO": {
                "sleepTimeSeconds": 25200,
                "sleepScores": None,
            },
        }
        entry = SleepEntry.from_garmin(data)

        assert entry.duration_seconds == 25200
        assert entry.duration_hours == 7.0
        assert entry.score == 0  # Default when missing

    def test_handles_empty_data(self):
        """Handle completely empty response."""
        data = {"_date": "2025-01-01"}
        entry = SleepEntry.from_garmin(data)

        assert entry.date == date(2025, 1, 1)
        assert entry.duration_seconds == 0

    def test_duration_hours_property(self):
        """Verify hours calculation."""
        entry = SleepEntry(
            date=date(2025, 1, 1),
            duration_seconds=27000,  # 7.5 hours
        )
        assert entry.duration_hours == 7.5

    def test_deep_pct_property(self):
        """Deep sleep percentage calculation."""
        entry = SleepEntry(
            date=date(2025, 1, 1),
            duration_seconds=28800,  # 8 hours
            deep_seconds=5760,  # 1.6 hours = 20%
        )
        assert entry.deep_pct == 20.0

    def test_deep_pct_handles_zero_duration(self):
        """No division by zero when duration is 0."""
        entry = SleepEntry(date=date(2025, 1, 1), duration_seconds=0)
        assert entry.deep_pct == 0.0
        assert entry.rem_pct == 0.0


# ============================================================================
# DailyStats Tests
# ============================================================================

class TestDailyStats:
    """Tests for DailyStats model."""

    def test_from_garmin_with_real_data(self):
        """Parse actual Garmin daily stats."""
        data = load_fixture("daily_stats_sample.json")
        entry = DailyStats.from_garmin(data)

        assert isinstance(entry.date, date)
        assert entry.total_steps >= 0

    def test_handles_all_none_values(self):
        """Handle response with all null values."""
        data = {
            "_date": "2025-01-01",
            "totalSteps": None,
            "restingHeartRate": None,
            "totalKilocalories": None,
        }
        entry = DailyStats.from_garmin(data)

        assert entry.date == date(2025, 1, 1)
        assert entry.total_steps == 0
        assert entry.resting_hr is None
        assert entry.total_calories == 0

    def test_active_minutes_property(self):
        """Verify minutes calculation."""
        entry = DailyStats(
            date=date(2025, 1, 1),
            active_seconds=3600,  # 1 hour
        )
        assert entry.active_minutes == 60

    def test_distance_km_property(self):
        """Verify km calculation."""
        entry = DailyStats(
            date=date(2025, 1, 1),
            distance_meters=5000,
        )
        assert entry.distance_km == 5.0


# ============================================================================
# WeightEntry Tests
# ============================================================================

class TestWeightEntry:
    """Tests for WeightEntry model."""

    def test_from_garmin_with_real_data(self):
        """Parse actual Garmin weight data."""
        data = load_fixture("weight_sample.json")
        entry = WeightEntry.from_garmin(data)

        assert isinstance(entry.date, date)
        assert entry.weight_kg > 0

    def test_converts_grams_to_kg(self):
        """Weight is stored in grams, converted to kg."""
        data = {
            "summaryDate": "2025-01-01",
            "maxWeight": 85000,  # 85 kg in grams
        }
        entry = WeightEntry.from_garmin(data)

        assert entry.weight_kg == 85.0

    def test_handles_zero_weight(self):
        """Handle missing weight value."""
        data = {
            "summaryDate": "2025-01-01",
            "maxWeight": None,
        }
        entry = WeightEntry.from_garmin(data)

        assert entry.weight_kg == 0.0

    def test_weight_lb_property(self):
        """Verify pounds calculation."""
        entry = WeightEntry(
            date=date(2025, 1, 1),
            weight_kg=100,
        )
        assert abs(entry.weight_lb - 220.462) < 0.01

    def test_body_composition_fields(self):
        """Optional body composition fields."""
        data = {
            "summaryDate": "2025-01-01",
            "maxWeight": 85000,
            "bmi": 24.5,
            "bodyFat": 22.3,
        }
        entry = WeightEntry.from_garmin(data)

        assert entry.bmi == 24.5
        assert entry.body_fat_pct == 22.3


# ============================================================================
# StressEntry Tests
# ============================================================================

class TestStressEntry:
    """Tests for StressEntry model."""

    def test_from_garmin_with_real_data(self):
        """Parse actual Garmin stress data."""
        data = load_fixture("stress_sample.json")
        entry = StressEntry.from_garmin(data)

        assert isinstance(entry.date, date)
        assert entry.avg_level >= 0

    def test_handles_none_values(self):
        """Handle null stress values."""
        data = {
            "_date": "2025-01-01",
            "avgStressLevel": None,
            "maxStressLevel": None,
        }
        entry = StressEntry.from_garmin(data)

        assert entry.avg_level == 0
        assert entry.max_level == 0


# ============================================================================
# BodyBatteryEntry Tests
# ============================================================================

class TestBodyBatteryEntry:
    """Tests for BodyBatteryEntry model."""

    def test_from_garmin_with_real_data(self):
        """Parse actual Garmin body battery data."""
        data = load_fixture("body_battery_sample.json")
        entry = BodyBatteryEntry.from_garmin(data)

        assert isinstance(entry.date, date)
        assert entry.charged >= 0
        assert entry.drained >= 0

    def test_handles_nested_data_structure(self):
        """Body battery uses nested data array."""
        data = {
            "_date": "2025-01-01",
            "data": [
                {"charged": 75, "drained": 60},
            ],
        }
        entry = BodyBatteryEntry.from_garmin(data)

        assert entry.charged == 75
        assert entry.drained == 60

    def test_handles_empty_data_array(self):
        """Handle missing or empty data array."""
        data = {"_date": "2025-01-01", "data": []}
        entry = BodyBatteryEntry.from_garmin(data)

        assert entry.charged == 0
        assert entry.drained == 0

    def test_handles_missing_data_key(self):
        """Handle completely missing data key."""
        data = {"_date": "2025-01-01"}
        entry = BodyBatteryEntry.from_garmin(data)

        assert entry.charged == 0
        assert entry.drained == 0

    def test_net_change_property(self):
        """Verify net change calculation."""
        entry = BodyBatteryEntry(
            date=date(2025, 1, 1),
            charged=80,
            drained=50,
        )
        assert entry.net_change == 30

        entry2 = BodyBatteryEntry(
            date=date(2025, 1, 1),
            charged=40,
            drained=70,
        )
        assert entry2.net_change == -30


# ============================================================================
# Goals Tests
# ============================================================================

class TestGoals:
    """Tests for Goals model."""

    def test_from_file_with_real_data(self):
        """Load actual goals.json."""
        data = load_fixture("goals_sample.json")
        goals = Goals.from_file(data)

        assert goals.weight_kg > 0
        assert goals.daily_steps > 0
        assert goals.sleep_hours > 0
        assert goals.workouts_per_week > 0

    def test_default_values(self):
        """Goals have sensible defaults."""
        goals = Goals()

        assert goals.weight_kg == 75.0
        assert goals.daily_steps == 10000
        assert goals.sleep_hours == 7.0
        assert goals.workouts_per_week == 3

    def test_from_empty_file(self):
        """Handle empty goals file."""
        goals = Goals.from_file({})

        assert goals.weight_kg == 75.0
        assert goals.daily_steps == 10000


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases that caused bugs in the original implementation."""

    def test_sleep_with_deeply_nested_none(self):
        """The classic None chain that caused TypeErrors."""
        # This structure caused: TypeError: 'NoneType' object is not subscriptable
        data = {
            "_date": "2025-01-01",
            "dailySleepDTO": {
                "sleepTimeSeconds": 25200,
                "sleepScores": {
                    "overall": None,  # This was the culprit
                },
            },
        }
        entry = SleepEntry.from_garmin(data)

        assert entry.score == 0  # Graceful default

    def test_weight_with_calendardate_fallback(self):
        """Some entries use calendarDate instead of summaryDate."""
        data = {
            "calendarDate": "2025-01-01",
            "maxWeight": 85000,
        }
        # This should not fail - we handle both field names
        entry = WeightEntry.from_garmin(data)
        assert entry.date == date(2025, 1, 1)

    def test_stats_with_zero_values(self):
        """Zero is a valid value, distinct from None."""
        data = {
            "_date": "2025-01-01",
            "totalSteps": 0,  # Explicitly zero (rest day)
            "restingHeartRate": 0,  # Should this be None?
        }
        entry = DailyStats.from_garmin(data)

        assert entry.total_steps == 0
        # Zero HR might indicate missing data, but we preserve it
        assert entry.resting_hr == 0
