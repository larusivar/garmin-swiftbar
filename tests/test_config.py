"""Tests for garmin_health.config module."""

import json
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from garmin_health.config import Config, SyncConfig, NotificationConfig, WidgetConfig


class TestSyncConfig:
    """Tests for SyncConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = SyncConfig()
        assert config.interval_minutes == 10
        assert config.change_threshold_steps == 100
        assert config.waking_hours_start == 7
        assert config.waking_hours_end == 23

    def test_should_sync_during_day(self, monkeypatch):
        """Test should_sync_now returns True during waking hours."""
        config = SyncConfig(waking_hours_start=7, waking_hours_end=23)

        # Mock datetime to return 12:00 (noon)
        class MockDatetime:
            @staticmethod
            def now():
                return datetime(2025, 12, 27, 12, 0, 0)

        monkeypatch.setattr("garmin_health.config.datetime", MockDatetime)
        assert config.should_sync_now() is True

    def test_should_not_sync_at_night(self, monkeypatch):
        """Test should_sync_now returns False during sleeping hours."""
        config = SyncConfig(waking_hours_start=7, waking_hours_end=23)

        # Mock datetime to return 3:00 AM
        class MockDatetime:
            @staticmethod
            def now():
                return datetime(2025, 12, 27, 3, 0, 0)

        monkeypatch.setattr("garmin_health.config.datetime", MockDatetime)
        assert config.should_sync_now() is False


class TestConfig:
    """Tests for main Config class."""

    def test_load_defaults_when_no_file(self, tmp_path):
        """Test loading config when file doesn't exist uses defaults."""
        config = Config.load(tmp_path / "nonexistent.json")

        assert config.sync.interval_minutes == 10
        assert config.widget.show_freshness is True
        assert config.notifications.daily_summary_enabled is True

    def test_load_from_file(self, temp_config_dir):
        """Test loading config from file."""
        config_path = temp_config_dir / "config.json"
        config = Config.load(config_path)

        assert config.sync.interval_minutes == 5
        assert config.sync.change_threshold_steps == 50
        assert config.notifications.sound == "Ping"
        assert config.widget.freshness_warning_minutes == 15

    def test_partial_config_uses_defaults(self, tmp_path):
        """Test partial config file fills missing values with defaults."""
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({
            "sync": {"interval_minutes": 15}
        }))

        config = Config.load(config_path)

        # Custom value
        assert config.sync.interval_minutes == 15
        # Default value (not in file)
        assert config.sync.change_threshold_steps == 100
        # Other sections use defaults
        assert config.widget.show_freshness is True

    def test_save_config(self, tmp_path):
        """Test saving config to file."""
        config_path = tmp_path / "config.json"

        config = Config()
        config.sync.interval_minutes = 20
        config.save(config_path)

        # Load and verify
        loaded = Config.load(config_path)
        assert loaded.sync.interval_minutes == 20

    def test_invalid_json_uses_defaults(self, tmp_path):
        """Test invalid JSON file falls back to defaults."""
        config_path = tmp_path / "config.json"
        config_path.write_text("{ invalid json }")

        config = Config.load(config_path)
        assert config.sync.interval_minutes == 10


class TestWidgetConfig:
    """Tests for WidgetConfig."""

    def test_default_values(self):
        """Test default widget configuration."""
        config = WidgetConfig()
        assert config.show_freshness is True
        assert config.freshness_warning_minutes == 30
        assert config.refresh_method == "url_scheme"


class TestNotificationConfig:
    """Tests for NotificationConfig."""

    def test_default_values(self):
        """Test default notification configuration."""
        config = NotificationConfig()
        assert config.daily_summary_enabled is True
        assert config.sound == "Glass"
        assert config.log_to_markdown is True
        assert config.log_file == "daily-summaries.md"
