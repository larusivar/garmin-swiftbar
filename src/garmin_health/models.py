"""Pydantic models for Garmin Connect API data.

These models provide:
- Type-safe access to Garmin data
- Automatic None handling via defaults
- IDE autocomplete support
- Validation at the data boundary
"""

from datetime import date
from typing import Optional
from pydantic import BaseModel


class SleepEntry(BaseModel):
    """Sleep data with None-safe defaults.

    Parses the complex nested structure from Garmin's sleep API
    into a flat, easy-to-use model.
    """
    model_config = {"extra": "ignore"}  # Ignore unknown API fields

    date: date
    duration_seconds: int = 0
    score: int = 0
    deep_seconds: int = 0
    light_seconds: int = 0
    rem_seconds: int = 0
    awake_seconds: int = 0

    @property
    def duration_hours(self) -> float:
        """Sleep duration in hours."""
        return self.duration_seconds / 3600

    @property
    def deep_pct(self) -> float:
        """Deep sleep percentage (0-100)."""
        if self.duration_seconds == 0:
            return 0.0
        return (self.deep_seconds / self.duration_seconds) * 100

    @property
    def rem_pct(self) -> float:
        """REM sleep percentage (0-100)."""
        if self.duration_seconds == 0:
            return 0.0
        return (self.rem_seconds / self.duration_seconds) * 100

    @classmethod
    def from_garmin(cls, data: dict) -> "SleepEntry":
        """Parse Garmin API response with defensive None handling.

        The Garmin API returns deeply nested structures with frequent nulls.
        This method handles all the edge cases in one place.
        """
        dto = data.get("dailySleepDTO") or {}
        scores = dto.get("sleepScores") or {}
        overall = scores.get("overall") or {}

        return cls(
            date=date.fromisoformat(data.get("_date") or data.get("calendarDate", "1970-01-01")),
            duration_seconds=dto.get("sleepTimeSeconds") or 0,
            score=overall.get("value") or 0,
            deep_seconds=dto.get("deepSleepSeconds") or 0,
            light_seconds=dto.get("lightSleepSeconds") or 0,
            rem_seconds=dto.get("remSleepSeconds") or 0,
            awake_seconds=dto.get("awakeSleepSeconds") or 0,
        )


class DailyStats(BaseModel):
    """Daily activity statistics.

    Aggregates steps, calories, heart rate, and stress data
    from Garmin's daily summary API.
    """
    model_config = {"extra": "ignore"}

    date: date
    total_steps: int = 0
    total_calories: int = 0
    active_calories: int = 0
    active_seconds: int = 0
    resting_hr: Optional[int] = None
    max_hr: Optional[int] = None
    min_hr: Optional[int] = None
    avg_stress: Optional[int] = None
    floors_climbed: float = 0
    distance_meters: float = 0

    @property
    def active_minutes(self) -> int:
        """Active time in minutes."""
        return self.active_seconds // 60

    @property
    def distance_km(self) -> float:
        """Distance in kilometers."""
        return self.distance_meters / 1000

    @classmethod
    def from_garmin(cls, data: dict) -> "DailyStats":
        """Parse Garmin daily stats API response."""
        return cls(
            date=date.fromisoformat(data.get("_date") or data.get("calendarDate", "1970-01-01")),
            total_steps=data.get("totalSteps") or 0,
            total_calories=data.get("totalKilocalories") or 0,
            active_calories=data.get("activeKilocalories") or 0,
            active_seconds=data.get("activeSeconds") or 0,
            resting_hr=data.get("restingHeartRate"),
            max_hr=data.get("maxHeartRate"),
            min_hr=data.get("minHeartRate"),
            avg_stress=data.get("averageStressLevel"),
            floors_climbed=data.get("floorsAscended") or 0,
            distance_meters=data.get("totalDistanceMeters") or 0,
        )


class WeightEntry(BaseModel):
    """Weight measurement from Garmin Index scale.

    Note: Garmin stores weight in grams internally.
    """
    model_config = {"extra": "ignore"}

    date: date
    weight_kg: float
    bmi: Optional[float] = None
    body_fat_pct: Optional[float] = None
    muscle_mass_kg: Optional[float] = None
    bone_mass_kg: Optional[float] = None
    body_water_pct: Optional[float] = None

    @property
    def weight_lb(self) -> float:
        """Weight in pounds."""
        return self.weight_kg * 2.20462

    @classmethod
    def from_garmin(cls, data: dict) -> "WeightEntry":
        """Parse Garmin weight summary.

        Weight is stored in grams, we convert to kg.
        """
        # Handle both maxWeight and weight fields
        weight_grams = data.get("maxWeight") or data.get("weight") or 0

        return cls(
            date=date.fromisoformat(data.get("summaryDate") or data.get("calendarDate") or data.get("_date", "1970-01-01")),
            weight_kg=weight_grams / 1000,
            bmi=data.get("bmi"),
            body_fat_pct=data.get("bodyFat"),
            muscle_mass_kg=(data.get("muscleMass") or 0) / 1000 if data.get("muscleMass") else None,
            bone_mass_kg=(data.get("boneMass") or 0) / 1000 if data.get("boneMass") else None,
            body_water_pct=data.get("bodyWater"),
        )


class StressEntry(BaseModel):
    """Daily stress data from Garmin watch."""
    model_config = {"extra": "ignore"}

    date: date
    avg_level: int = 0
    max_level: int = 0

    @classmethod
    def from_garmin(cls, data: dict) -> "StressEntry":
        """Parse Garmin stress API response."""
        return cls(
            date=date.fromisoformat(data.get("_date") or data.get("calendarDate", "1970-01-01")),
            avg_level=data.get("avgStressLevel") or 0,
            max_level=data.get("maxStressLevel") or 0,
        )


class BodyBatteryEntry(BaseModel):
    """Body Battery energy data from Garmin watch.

    Note: Garmin API nests data in a 'data' array with usually one entry.
    Structure: {_date: "YYYY-MM-DD", data: [{charged, drained, ...}]}
    """
    model_config = {"extra": "ignore"}

    date: date
    charged: int = 0
    drained: int = 0

    @property
    def net_change(self) -> int:
        """Net energy change (positive = gained, negative = lost)."""
        return self.charged - self.drained

    @classmethod
    def from_garmin(cls, data: dict) -> "BodyBatteryEntry":
        """Parse Garmin Body Battery API response.

        Handles the nested data structure: {_date, data: [{charged, drained}]}
        """
        entry_date = data.get("_date") or data.get("calendarDate", "1970-01-01")

        # Extract from nested data array
        inner_data = data.get("data", [{}])
        inner = inner_data[0] if inner_data else {}

        return cls(
            date=date.fromisoformat(entry_date),
            charged=inner.get("charged") or 0,
            drained=inner.get("drained") or 0,
        )


class Goals(BaseModel):
    """User health goals loaded from goals.json."""

    weight_kg: float = 75.0
    daily_steps: int = 10000
    sleep_hours: float = 7.0
    workouts_per_week: int = 3

    @classmethod
    def from_file(cls, data: dict) -> "Goals":
        """Load goals from JSON file."""
        return cls(
            weight_kg=data.get("weight_kg", 75.0),
            daily_steps=data.get("daily_steps", 10000),
            sleep_hours=data.get("sleep_hours", 7.0),
            workouts_per_week=data.get("workouts_per_week", 3),
        )
