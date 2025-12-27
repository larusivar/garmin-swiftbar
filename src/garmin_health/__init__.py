"""Garmin Health - Garmin Connect integration with Pydantic models."""

__version__ = "2.1.0"

from .models import SleepEntry, DailyStats, WeightEntry, StressEntry, BodyBatteryEntry, Goals
from .data import HealthData
from .core import (
    get_data_dir,
    get_cache_dir,
    get_keychain_value,
    get_credentials,
    get_client,
    fetch_today_stats,
    get_local_today_stats,
    update_daily_stats_json,
    refresh_swiftbar,
    restart_swiftbar,
    TOKEN_DIR,
    EXPORT_DIR,
)
from .config import (
    Config,
    SyncConfig,
    NotificationConfig,
    WidgetConfig,
    get_config_dir,
)
from .widget import render_widget

__all__ = [
    # Models
    "SleepEntry",
    "DailyStats",
    "WeightEntry",
    "StressEntry",
    "BodyBatteryEntry",
    "Goals",
    # Data access
    "HealthData",
    # Core utilities
    "get_data_dir",
    "get_cache_dir",
    "get_keychain_value",
    "get_credentials",
    "get_client",
    "fetch_today_stats",
    "get_local_today_stats",
    "update_daily_stats_json",
    "refresh_swiftbar",
    "restart_swiftbar",
    "TOKEN_DIR",
    "EXPORT_DIR",
    # Configuration
    "Config",
    "SyncConfig",
    "NotificationConfig",
    "WidgetConfig",
    "get_config_dir",
    # Widget
    "render_widget",
]
