"""Data access layer for Garmin health data.

Provides centralized access to all health data with:
- Caching to avoid repeated disk reads (47 MB of JSON)
- Chronological sorting at load time (prevents the "2021 weight" bug)
- Type-safe returns via Pydantic models
"""

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from .models import (
    SleepEntry,
    DailyStats,
    WeightEntry,
    StressEntry,
    BodyBatteryEntry,
    Goals,
)


class HealthData:
    """Centralized data access with caching and sorted loading.

    Usage:
        data = HealthData.default()
        latest = data.latest_sleep()
        week = data.sleep_range(start, end)
        all_sleep = data.sleep()

    The data directory is expected to contain:
        - sleep.json
        - daily_stats.json
        - weight.json
        - stress.json
        - body_battery.json
        - goals.json
    """

    # Default iCloud path for Garmin data
    DEFAULT_DIR = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/Health/Garmin"

    # Alternative symlink path
    SYMLINK_DIR = Path.home() / "Health/Garmin"

    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize with data directory.

        Args:
            data_dir: Path to Garmin data. If None, uses iCloud path.
        """
        if data_dir:
            self.data_dir = data_dir
        elif self.SYMLINK_DIR.exists():
            self.data_dir = self.SYMLINK_DIR
        else:
            self.data_dir = self.DEFAULT_DIR

        self._cache: dict = {}

    @classmethod
    def default(cls) -> "HealthData":
        """Create instance with default data directory."""
        return cls()

    def invalidate_cache(self) -> None:
        """Clear all cached data. Call after data sync."""
        self._cache.clear()

    # =========================================================================
    # Sleep Data
    # =========================================================================

    def sleep(self) -> list[SleepEntry]:
        """All sleep data, chronologically sorted.

        Returns:
            List of SleepEntry, oldest first.
        """
        if "sleep" not in self._cache:
            self._cache["sleep"] = self._load_sleep()
        return self._cache["sleep"]

    def _load_sleep(self) -> list[SleepEntry]:
        """Load and parse sleep.json."""
        path = self.data_dir / "sleep.json"
        if not path.exists():
            return []

        with open(path) as f:
            raw = json.load(f)

        # Sort chronologically ONCE at load time
        raw = sorted(raw, key=lambda x: x.get("_date", ""))
        return [SleepEntry.from_garmin(r) for r in raw]

    def latest_sleep(self) -> Optional[SleepEntry]:
        """Most recent sleep entry."""
        entries = self.sleep()
        return entries[-1] if entries else None

    def sleep_range(self, start: date, end: date) -> list[SleepEntry]:
        """Sleep entries within date range (inclusive)."""
        return [s for s in self.sleep() if start <= s.date <= end]

    def sleep_last_n_days(self, n: int) -> list[SleepEntry]:
        """Sleep entries for the last N days."""
        end = date.today()
        start = end - timedelta(days=n)
        return self.sleep_range(start, end)

    # =========================================================================
    # Daily Stats
    # =========================================================================

    def stats(self) -> list[DailyStats]:
        """All daily stats, chronologically sorted."""
        if "stats" not in self._cache:
            self._cache["stats"] = self._load_stats()
        return self._cache["stats"]

    def _load_stats(self) -> list[DailyStats]:
        """Load and parse daily_stats.json."""
        path = self.data_dir / "daily_stats.json"
        if not path.exists():
            return []

        with open(path) as f:
            raw = json.load(f)

        raw = sorted(raw, key=lambda x: x.get("_date", ""))
        return [DailyStats.from_garmin(r) for r in raw]

    def latest_stats(self) -> Optional[DailyStats]:
        """Most recent daily stats."""
        entries = self.stats()
        return entries[-1] if entries else None

    def today_stats(self) -> Optional[DailyStats]:
        """Today's stats if available."""
        today = date.today()
        for entry in reversed(self.stats()):
            if entry.date == today:
                return entry
            if entry.date < today:
                break
        return None

    def stats_range(self, start: date, end: date) -> list[DailyStats]:
        """Daily stats within date range (inclusive)."""
        return [s for s in self.stats() if start <= s.date <= end]

    def stats_last_n_days(self, n: int) -> list[DailyStats]:
        """Daily stats for the last N days."""
        end = date.today()
        start = end - timedelta(days=n)
        return self.stats_range(start, end)

    # =========================================================================
    # Weight Data
    # =========================================================================

    def weight(self) -> list[WeightEntry]:
        """All weight entries, chronologically sorted."""
        if "weight" not in self._cache:
            self._cache["weight"] = self._load_weight()
        return self._cache["weight"]

    def _load_weight(self) -> list[WeightEntry]:
        """Load and parse weight.json."""
        path = self.data_dir / "weight.json"
        if not path.exists():
            return []

        with open(path) as f:
            raw = json.load(f)

        # Weight data is nested under dailyWeightSummaries
        summaries = raw.get("dailyWeightSummaries", [])
        summaries = sorted(summaries, key=lambda x: x.get("summaryDate", ""))
        return [WeightEntry.from_garmin(r) for r in summaries]

    def latest_weight(self) -> Optional[WeightEntry]:
        """Most recent weight entry."""
        entries = self.weight()
        return entries[-1] if entries else None

    def weight_range(self, start: date, end: date) -> list[WeightEntry]:
        """Weight entries within date range (inclusive)."""
        return [w for w in self.weight() if start <= w.date <= end]

    def weight_last_n_days(self, n: int) -> list[WeightEntry]:
        """Weight entries for the last N days."""
        end = date.today()
        start = end - timedelta(days=n)
        return self.weight_range(start, end)

    # =========================================================================
    # Stress Data
    # =========================================================================

    def stress(self) -> list[StressEntry]:
        """All stress entries, chronologically sorted."""
        if "stress" not in self._cache:
            self._cache["stress"] = self._load_stress()
        return self._cache["stress"]

    def _load_stress(self) -> list[StressEntry]:
        """Load and parse stress.json."""
        path = self.data_dir / "stress.json"
        if not path.exists():
            return []

        with open(path) as f:
            raw = json.load(f)

        raw = sorted(raw, key=lambda x: x.get("_date", ""))
        return [StressEntry.from_garmin(r) for r in raw]

    def latest_stress(self) -> Optional[StressEntry]:
        """Most recent stress entry."""
        entries = self.stress()
        return entries[-1] if entries else None

    # =========================================================================
    # Body Battery Data
    # =========================================================================

    def body_battery(self) -> list[BodyBatteryEntry]:
        """All body battery entries, chronologically sorted."""
        if "body_battery" not in self._cache:
            self._cache["body_battery"] = self._load_body_battery()
        return self._cache["body_battery"]

    def _load_body_battery(self) -> list[BodyBatteryEntry]:
        """Load and parse body_battery.json."""
        path = self.data_dir / "body_battery.json"
        if not path.exists():
            return []

        with open(path) as f:
            raw = json.load(f)

        raw = sorted(raw, key=lambda x: x.get("_date", ""))
        return [BodyBatteryEntry.from_garmin(r) for r in raw]

    def latest_body_battery(self) -> Optional[BodyBatteryEntry]:
        """Most recent body battery entry."""
        entries = self.body_battery()
        return entries[-1] if entries else None

    # =========================================================================
    # Goals
    # =========================================================================

    def goals(self) -> Goals:
        """User's health goals."""
        if "goals" not in self._cache:
            self._cache["goals"] = self._load_goals()
        return self._cache["goals"]

    def _load_goals(self) -> Goals:
        """Load and parse goals.json."""
        path = self.data_dir / "goals.json"
        if not path.exists():
            return Goals()  # Return defaults

        with open(path) as f:
            raw = json.load(f)

        return Goals.from_file(raw)

    # =========================================================================
    # Aggregate Helpers
    # =========================================================================

    def avg_sleep_hours(self, days: int = 7) -> float:
        """Average sleep hours over last N days."""
        entries = self.sleep_last_n_days(days)
        if not entries:
            return 0.0
        return sum(e.duration_hours for e in entries) / len(entries)

    def avg_steps(self, days: int = 7) -> int:
        """Average steps over last N days."""
        entries = self.stats_last_n_days(days)
        if not entries:
            return 0
        return int(sum(e.total_steps for e in entries) / len(entries))

    def weight_trend(self, days: int = 7) -> float:
        """Weight change over last N days (positive = gained, negative = lost)."""
        entries = self.weight_last_n_days(days)
        if len(entries) < 2:
            return 0.0
        return entries[-1].weight_kg - entries[0].weight_kg

    def step_streak(self, goal: Optional[int] = None) -> int:
        """Count consecutive days meeting step goal.

        Args:
            goal: Step goal. If None, uses user's configured goal.

        Returns:
            Number of consecutive days from most recent.
        """
        if goal is None:
            goal = self.goals().daily_steps

        streak = 0
        for entry in reversed(self.stats()):
            if entry.total_steps >= goal:
                streak += 1
            else:
                break
        return streak
