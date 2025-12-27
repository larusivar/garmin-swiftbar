"""Core Garmin utilities for API access and data operations.

This module provides the shared foundation used by:
- garmin-client.py (CLI)
- garmin-sync-daemon.py (background sync)
- daily-summary.py (notifications)

Key responsibilities:
- Keychain credential access
- Garmin API authentication with token caching
- Local JSON file updates
- SwiftBar widget refresh
"""

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Optional

# Lazy import to avoid startup cost when not needed
Garmin = None


# =============================================================================
# Path Configuration
# =============================================================================

def get_data_dir() -> Path:
    """Get Garmin data directory.

    Configurable via GARMIN_DATA_DIR environment variable.
    Defaults to ~/Health/Garmin (symlink) or iCloud path.
    """
    if env_dir := os.environ.get("GARMIN_DATA_DIR"):
        return Path(env_dir)

    symlink = Path.home() / "Health" / "Garmin"
    if symlink.exists():
        return symlink

    return Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/Health/Garmin"


def get_cache_dir() -> Path:
    """Get cache directory for OAuth tokens.

    Configurable via XDG_CACHE_HOME or defaults to ~/.cache/garmin.
    """
    if env_dir := os.environ.get("XDG_CACHE_HOME"):
        return Path(env_dir) / "garmin"
    return Path.home() / ".cache" / "garmin"


# Constants for backward compatibility
TOKEN_DIR = get_cache_dir()
EXPORT_DIR = get_data_dir()


# =============================================================================
# Keychain Access
# =============================================================================

def get_keychain_value(service: str) -> Optional[str]:
    """Get value from macOS Keychain.

    Args:
        service: The keychain service name (e.g., "garmin-email")

    Returns:
        The stored value, or None if not found.
    """
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-a", "garmin", "-s", service, "-w"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def get_credentials() -> tuple[str, str]:
    """Get Garmin credentials from macOS Keychain.

    Returns:
        Tuple of (email, password)

    Raises:
        SystemExit: If credentials are not found.
    """
    email = get_keychain_value("garmin-email")
    password = get_keychain_value("garmin-password")

    if not email or not password:
        print("Error: Garmin credentials not found in Keychain.", file=sys.stderr)
        print("Run these commands to set up:", file=sys.stderr)
        print('  security add-generic-password -a "garmin" -s "garmin-email" -w "your@email.com"', file=sys.stderr)
        print('  security add-generic-password -a "garmin" -s "garmin-password" -w "your-password"', file=sys.stderr)
        sys.exit(1)

    return email, password


# =============================================================================
# Garmin API Client
# =============================================================================

def get_client():
    """Get authenticated Garmin Connect client.

    Uses token caching to avoid repeated logins. Tokens are stored in
    ~/.cache/garmin/ and are valid for ~90 days.

    Returns:
        Authenticated Garmin client instance.

    Raises:
        SystemExit: If garminconnect is not installed or auth fails.
    """
    global Garmin
    if Garmin is None:
        try:
            from garminconnect import Garmin as GarminClient
            Garmin = GarminClient
        except ImportError:
            print("Error: garminconnect not installed.", file=sys.stderr)
            print("Run: pip3 install garminconnect", file=sys.stderr)
            sys.exit(1)

    email, password = get_credentials()

    # Ensure cache directory exists
    token_dir = get_cache_dir()
    token_dir.mkdir(parents=True, exist_ok=True)
    token_path = str(token_dir)

    client = Garmin(email, password)

    try:
        # Try to load saved session from cache directory
        client.login(token_path)
    except Exception:
        # Fresh login required
        try:
            client.login()
            # Save session for next time
            client.garth.dump(token_path)
        except Exception as e:
            print(f"Error: Could not authenticate with Garmin: {e}", file=sys.stderr)
            sys.exit(1)

    return client


# =============================================================================
# Data Operations
# =============================================================================

def fetch_today_stats(client) -> dict:
    """Fetch today's stats from Garmin API.

    Args:
        client: Authenticated Garmin client.

    Returns:
        Stats dictionary with '_date' key added.
    """
    today = date.today().isoformat()
    stats = client.get_stats(today)
    stats["_date"] = today
    return stats


def get_local_today_stats() -> Optional[dict]:
    """Get today's stats from local JSON file.

    Returns:
        Stats dict if found, None otherwise.
    """
    data_file = get_data_dir() / "daily_stats.json"
    if not data_file.exists():
        return None

    today = date.today().isoformat()
    with open(data_file) as f:
        all_stats = json.load(f)

    for entry in reversed(all_stats):
        if entry.get("_date") == today:
            return entry

    return None


def update_daily_stats_json(new_entry: dict) -> bool:
    """Update local daily_stats.json with new data.

    Updates today's entry if it exists, or appends a new entry.

    Args:
        new_entry: Stats dict with '_date' key.

    Returns:
        True if data changed (new or different steps), False otherwise.
    """
    data_file = get_data_dir() / "daily_stats.json"
    today = date.today().isoformat()

    if data_file.exists():
        with open(data_file) as f:
            all_stats = json.load(f)
    else:
        all_stats = []

    # Find and update existing entry
    old_steps = None
    new_steps = new_entry.get("totalSteps", 0)
    updated = False

    for i, entry in enumerate(all_stats):
        if entry.get("_date") == today:
            old_steps = entry.get("totalSteps", 0)
            all_stats[i] = new_entry
            updated = True
            break

    if not updated:
        all_stats.append(new_entry)

    # Write back
    with open(data_file, "w") as f:
        json.dump(all_stats, f, indent=2)

    # Return True if this is new data or steps changed
    if old_steps is None:
        return True
    return old_steps != new_steps


# =============================================================================
# SwiftBar Integration
# =============================================================================

def refresh_swiftbar() -> bool:
    """Trigger SwiftBar plugin refresh.

    Uses URL scheme for gentle refresh. If that fails, touches the plugin
    file to trigger refresh on next SwiftBar poll.

    Returns:
        True if refresh was attempted.
    """
    # Try URL scheme first (gentler, no restart)
    result = subprocess.run(
        ["open", "-g", "swiftbar://refreshplugin?name=garmin-health.30m.py"],
        capture_output=True
    )

    if result.returncode != 0:
        # Fallback: touch the plugin file
        plugin = Path.home() / "Library/Application Support/SwiftBar/Plugins/garmin-health.30m.py"
        if plugin.exists():
            plugin.touch()

    return True


def restart_swiftbar() -> None:
    """Full SwiftBar restart (more aggressive, use sparingly).

    Note: This kills and restarts SwiftBar, which briefly removes all
    menu bar plugins. Prefer refresh_swiftbar() for normal updates.
    """
    subprocess.run(["killall", "SwiftBar"], capture_output=True)
    subprocess.run(["open", "-a", "SwiftBar"], capture_output=True)
