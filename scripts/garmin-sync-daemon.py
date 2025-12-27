#!/usr/bin/env python3
"""Smart Garmin sync daemon.

Polls Garmin API, compares with local data, and refreshes SwiftBar
only when data actually changes. Designed to run every 10 minutes via launchd.

Features:
- Lightweight: single API call per run
- Smart: only refreshes widget when data changes significantly
- Time-aware: respects waking hours from config
- Configurable: all settings via ~/.config/garmin-health/config.json
- Quiet: no output unless something changes or errors
"""

import sys
from pathlib import Path

# Add the src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from garmin_health.core import (
    get_client,
    fetch_today_stats,
    get_local_today_stats,
    update_daily_stats_json,
    refresh_swiftbar,
)
from garmin_health.config import Config


def smart_sync():
    """Main sync logic."""
    # Load configuration
    config = Config.load()

    # Check if we should sync based on time of day
    if not config.sync.should_sync_now():
        # Silent exit during sleeping hours
        return

    try:
        # Get current local steps
        local_stats = get_local_today_stats()
        local_steps = local_stats.get("totalSteps", 0) if local_stats else 0

        # Fetch from API
        client = get_client()
        api_stats = fetch_today_stats(client)
        api_steps = api_stats.get("totalSteps", 0)

        # Check if significant change
        diff = abs(api_steps - local_steps)
        if diff > config.sync.change_threshold_steps:
            print(f"Steps changed: {local_steps:,} -> {api_steps:,} (+{diff:,})")

            # Update local JSON
            changed = update_daily_stats_json(api_stats)
            if changed:
                refresh_swiftbar()
                print("SwiftBar refreshed")
        # else: no significant change, stay quiet

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    smart_sync()
