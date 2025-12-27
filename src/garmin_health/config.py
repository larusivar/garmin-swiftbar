"""Configuration management for Garmin health automation.

Provides typed configuration with sensible defaults. Config is loaded from
~/.config/garmin-health/config.json (XDG compliant).

Usage:
    config = Config.load()
    if config.sync.should_sync_now():
        # ... sync logic
"""

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


def get_config_dir() -> Path:
    """Get config directory (XDG compliant)."""
    if env_dir := os.environ.get("XDG_CONFIG_HOME"):
        return Path(env_dir) / "garmin-health"
    return Path.home() / ".config" / "garmin-health"


@dataclass
class SyncConfig:
    """Configuration for background sync daemon."""

    interval_minutes: int = 10
    """How often to poll Garmin API (via launchd)."""

    change_threshold_steps: int = 100
    """Minimum step change to trigger widget refresh."""

    waking_hours_start: int = 7
    """Start of waking hours (24h format). No sync before this."""

    waking_hours_end: int = 23
    """End of waking hours (24h format). No sync after this."""

    def should_sync_now(self) -> bool:
        """Check if current time is within waking hours."""
        hour = datetime.now().hour
        return self.waking_hours_start <= hour <= self.waking_hours_end


@dataclass
class NotificationConfig:
    """Configuration for daily summary notifications."""

    daily_summary_enabled: bool = True
    """Whether to send daily summary notification at midnight."""

    daily_summary_time: str = "00:00"
    """Time to send daily summary (HH:MM format)."""

    sound: str = "Glass"
    """macOS notification sound name."""

    log_to_markdown: bool = True
    """Whether to append daily summaries to markdown log file."""

    log_file: str = "daily-summaries.md"
    """Filename for markdown log (relative to data dir)."""


@dataclass
class WidgetConfig:
    """Configuration for SwiftBar menu bar widget."""

    show_freshness: bool = True
    """Show data age indicator in menu bar (e.g., '· 2m')."""

    freshness_warning_minutes: int = 30
    """Minutes after which data is considered stale."""

    refresh_method: str = "url_scheme"
    """How to refresh widget: 'url_scheme', 'touch', or 'restart'."""


@dataclass
class Config:
    """Main configuration container."""

    sync: SyncConfig = field(default_factory=SyncConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    widget: WidgetConfig = field(default_factory=WidgetConfig)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Config":
        """Load config from file, using defaults for missing values.

        Args:
            path: Config file path. If None, uses default XDG location.

        Returns:
            Config instance with values from file merged with defaults.
        """
        if path is None:
            path = get_config_dir() / "config.json"

        config = cls()

        if not path.exists():
            return config

        try:
            with open(path) as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            # Log but don't fail - use defaults
            print(f"Warning: Could not load config from {path}: {e}", file=sys.stderr)
            return config

        # Merge loaded values into defaults
        if "sync" in raw:
            sync_data = raw["sync"]
            config.sync = SyncConfig(
                interval_minutes=sync_data.get("interval_minutes", config.sync.interval_minutes),
                change_threshold_steps=sync_data.get("change_threshold_steps", config.sync.change_threshold_steps),
                waking_hours_start=sync_data.get("waking_hours_start", config.sync.waking_hours_start),
                waking_hours_end=sync_data.get("waking_hours_end", config.sync.waking_hours_end),
            )

        if "notifications" in raw:
            notif_data = raw["notifications"]
            config.notifications = NotificationConfig(
                daily_summary_enabled=notif_data.get("daily_summary_enabled", config.notifications.daily_summary_enabled),
                daily_summary_time=notif_data.get("daily_summary_time", config.notifications.daily_summary_time),
                sound=notif_data.get("sound", config.notifications.sound),
                log_to_markdown=notif_data.get("log_to_markdown", config.notifications.log_to_markdown),
                log_file=notif_data.get("log_file", config.notifications.log_file),
            )

        if "widget" in raw:
            widget_data = raw["widget"]
            config.widget = WidgetConfig(
                show_freshness=widget_data.get("show_freshness", config.widget.show_freshness),
                freshness_warning_minutes=widget_data.get("freshness_warning_minutes", config.widget.freshness_warning_minutes),
                refresh_method=widget_data.get("refresh_method", config.widget.refresh_method),
            )

        return config

    def save(self, path: Optional[Path] = None) -> None:
        """Save current config to file.

        Args:
            path: Config file path. If None, uses default XDG location.
        """
        if path is None:
            path = get_config_dir() / "config.json"

        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "sync": {
                "interval_minutes": self.sync.interval_minutes,
                "change_threshold_steps": self.sync.change_threshold_steps,
                "waking_hours_start": self.sync.waking_hours_start,
                "waking_hours_end": self.sync.waking_hours_end,
            },
            "notifications": {
                "daily_summary_enabled": self.notifications.daily_summary_enabled,
                "daily_summary_time": self.notifications.daily_summary_time,
                "sound": self.notifications.sound,
                "log_to_markdown": self.notifications.log_to_markdown,
                "log_file": self.notifications.log_file,
            },
            "widget": {
                "show_freshness": self.widget.show_freshness,
                "freshness_warning_minutes": self.widget.freshness_warning_minutes,
                "refresh_method": self.widget.refresh_method,
            },
        }

        with open(path, "w") as f:
            json.dump(data, f, indent=2)
