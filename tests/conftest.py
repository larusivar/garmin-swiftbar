"""Shared test fixtures for garmin_health tests."""

import json
import pytest
from pathlib import Path
from datetime import date, timedelta
import tempfile


@pytest.fixture
def temp_data_dir():
    """Create temporary Garmin data directory with mock data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create mock daily_stats.json
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        stats = [
            {"_date": yesterday, "totalSteps": 8000},
            {"_date": today, "totalSteps": 10500},
        ]
        (tmpdir / "daily_stats.json").write_text(json.dumps(stats))

        # Create mock goals.json
        goals = {
            "weight_kg": 70,
            "daily_steps": 10000,
            "sleep_hours": 7,
            "workouts_per_week": 3,
        }
        (tmpdir / "goals.json").write_text(json.dumps(goals))

        # Create mock weight.json
        weight = {
            "dailyWeightSummaries": [
                {"summaryDate": yesterday, "maxWeight": 75500},
                {"summaryDate": today, "maxWeight": 75000},
            ]
        }
        (tmpdir / "weight.json").write_text(json.dumps(weight))

        # Create mock sleep.json
        sleep = [
            {
                "_date": today,
                "dailySleepDTO": {
                    "sleepTimeSeconds": int(7.3 * 3600),
                    "sleepScores": {"overall": {"value": 78}},
                },
            }
        ]
        (tmpdir / "sleep.json").write_text(json.dumps(sleep))

        yield tmpdir


@pytest.fixture
def temp_config_dir():
    """Create temporary config directory with test config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        config = {
            "sync": {
                "interval_minutes": 5,
                "change_threshold_steps": 50,
                "waking_hours_start": 8,
                "waking_hours_end": 22,
            },
            "notifications": {
                "daily_summary_enabled": True,
                "sound": "Ping",
            },
            "widget": {
                "show_freshness": True,
                "freshness_warning_minutes": 15,
            },
        }
        config_file = tmpdir / "config.json"
        config_file.write_text(json.dumps(config))

        yield tmpdir


@pytest.fixture
def mock_keychain(monkeypatch):
    """Mock macOS keychain access."""
    def mock_run(cmd, **kwargs):
        class MockResult:
            stdout = "test@example.com\n" if "email" in cmd else "testpassword\n"
            returncode = 0
        return MockResult()

    import subprocess
    monkeypatch.setattr(subprocess, "run", mock_run)
