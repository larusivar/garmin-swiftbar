"""SwiftBar widget renderer for Garmin health data.

This module generates SwiftBar-formatted output for the health widget.
It replaces the bash script with pure Python for better maintainability.

SwiftBar format reference:
- Menu bar: "text | options"
- Separator: "---"
- Submenu: "--item | options"
- Options: tooltip, sfimage, sfcolor, badge, terminal, href, bash, refresh

Example output:
    ✓ 9.3k/10k 💤7.2h · 2m | tooltip=Steps: 9,300/10,000...
    ---
    Health Dashboard | size=14 sfimage=heart.fill sfcolor=red
    ---
    Steps: ▰▰▰▰▰▰▰▰▱▱ 84% | sfimage=figure.walk sfcolor=#f0ad4e badge=1,766 to go
"""

import json
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from .data import HealthData
from .config import Config


def _get_script_path() -> Path:
    """Get path to the CLI script, relative to this package."""
    # Package is at src/garmin_health/, scripts are at scripts/
    package_dir = Path(__file__).parent  # garmin_health/
    src_dir = package_dir.parent  # src/
    project_dir = src_dir.parent  # project root
    return project_dir / "scripts" / "garmin-client.py"


def _get_python_path() -> str:
    """Get path to the Python interpreter running this code."""
    return sys.executable


def progress_bar(pct: float, width: int = 10) -> str:
    """Generate Unicode progress bar.

    Args:
        pct: Percentage (0-100+)
        width: Number of characters

    Returns:
        String like "▰▰▰▰▰▰▰▱▱▱"
    """
    pct = max(0, min(100, pct))
    filled = int(pct * width / 100)
    return "▰" * filled + "▱" * (width - filled)


def get_color(pct: float) -> str:
    """Get color based on goal percentage.

    Args:
        pct: Percentage of goal achieved

    Returns:
        Color string (green/#f0ad4e/#d9534f)
    """
    if pct >= 100:
        return "green"
    elif pct >= 75:
        return "#f0ad4e"  # Orange
    return "#d9534f"  # Red


def get_weight_color(diff: float) -> str:
    """Get color for weight difference from goal.

    Args:
        diff: Weight difference (positive = above goal)

    Returns:
        Color string
    """
    if diff <= 0:
        return "green"
    elif diff < 5:
        return "#f0ad4e"
    return "#d9534f"


def format_number(n: int) -> str:
    """Format number with thousand separators."""
    return f"{n:,}"


def format_number_short(n: int) -> str:
    """Format number in abbreviated form (e.g., 9.3k, 1.2M)."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".rstrip('0').rstrip('.')
    elif n >= 1_000:
        return f"{n / 1_000:.1f}k".rstrip('0').rstrip('.')
    return str(n)


def get_last_sync_time(data_dir: Path) -> str:
    """Get last sync time from file modification time."""
    try:
        stats_file = data_dir / "daily_stats.json"
        if stats_file.exists():
            mtime = os.path.getmtime(stats_file)
            return datetime.fromtimestamp(mtime).strftime("%H:%M")
    except Exception:
        pass
    return ""


def get_data_age_minutes(data_dir: Path) -> int:
    """Get minutes since daily_stats.json was last modified.

    Returns:
        Age in minutes, or -1 if unknown.
    """
    try:
        stats_file = data_dir / "daily_stats.json"
        if stats_file.exists():
            mtime = stats_file.stat().st_mtime
            age_seconds = time.time() - mtime
            return int(age_seconds / 60)
    except Exception:
        pass
    return -1


def format_time_ago(minutes: int) -> str:
    """Convert minutes to human-readable relative time.

    Args:
        minutes: Age in minutes.

    Returns:
        String like "now", "2m", "1h", "2d".
    """
    if minutes < 0:
        return "?"
    elif minutes < 1:
        return "now"
    elif minutes < 60:
        return f"{minutes}m"
    elif minutes < 1440:  # 24 hours
        hours = minutes // 60
        return f"{hours}h"
    else:
        days = minutes // 1440
        return f"{days}d"


def count_workouts_this_week(data: HealthData) -> int:
    """Count workouts in the last 7 days."""
    activities_file = data.data_dir / "activities.json"
    if not activities_file.exists():
        return 0

    week_ago = (date.today() - timedelta(days=7)).isoformat()
    try:
        with open(activities_file) as f:
            activities = json.load(f)
        return sum(
            1 for a in activities
            if a.get("startTimeLocal", "")[:10] >= week_ago
        )
    except Exception:
        return 0


def find_latest_with_steps(data: HealthData) -> Optional[tuple]:
    """Find the most recent day with step data.

    Returns:
        Tuple of (DailyStats, is_today) or None
    """
    today = date.today()
    for entry in reversed(data.stats()):
        if entry.total_steps > 0:
            return (entry, entry.date == today)
    return None


def find_latest_with_sleep(data: HealthData) -> Optional[tuple]:
    """Find the most recent day with sleep data.

    Returns:
        Tuple of (SleepEntry, is_recent) or None
    """
    today = date.today()
    for entry in reversed(data.sleep()):
        if entry.duration_seconds > 0:
            # Consider it recent if within last 2 days
            is_recent = (today - entry.date).days <= 1
            return (entry, is_recent)
    return None


def render_menu_bar(data: HealthData, config: Optional[Config] = None) -> tuple[str, list[str]]:
    """Render the menu bar line.

    Args:
        data: HealthData instance.
        config: Config instance. If None, loads from default location.

    Returns:
        Tuple of (menu_bar_text, tooltip_parts)
    """
    if config is None:
        config = Config.load()

    parts = []
    tooltip_parts = []
    goals = data.goals()

    # Steps (find latest day with data) - show as "890/10,000" format
    steps_result = find_latest_with_steps(data)
    if steps_result:
        stats_entry, is_today = steps_result
        steps = stats_entry.total_steps
        steps_pct = (steps / goals.daily_steps) * 100 if goals.daily_steps > 0 else 100

        if steps_pct >= 100:
            parts.append(f"✓ {format_number_short(steps)}/{format_number_short(goals.daily_steps)}")
        else:
            parts.append(f"{format_number_short(steps)}/{format_number_short(goals.daily_steps)}")

        date_note = "" if is_today else f" ({stats_entry.date})"
        tooltip_parts.append(f"Steps: {format_number(steps)}/{format_number(goals.daily_steps)}{date_note}")

    # Weight - only in tooltip, not menu bar (to reduce cycling items)
    latest_weight = data.latest_weight()
    if latest_weight:
        weight = latest_weight.weight_kg
        trend = data.weight_trend(7)
        tooltip_parts.append(f"Weight: {weight:.1f}kg (7d: {trend:+.1f}kg)")

    # Sleep - always show in menu bar
    sleep_result = find_latest_with_sleep(data)
    if sleep_result:
        sleep_entry, is_recent = sleep_result
        sleep_hrs = sleep_entry.duration_hours
        parts.append(f"💤{sleep_hrs:.1f}h")
        tooltip_parts.append(f"Sleep: {sleep_hrs:.1f}h (score: {sleep_entry.score})")

    # Add freshness indicator if enabled
    if config.widget.show_freshness:
        age_minutes = get_data_age_minutes(data.data_dir)
        freshness = format_time_ago(age_minutes)

        # Use warning color if data is stale
        if age_minutes > config.widget.freshness_warning_minutes:
            parts.append(f"⚠️{freshness}")
        else:
            parts.append(f"· {freshness}")

        tooltip_parts.append(f"Data age: {freshness}")

    menu_bar = " ".join(parts) if parts else "❤️ --"
    return menu_bar, tooltip_parts


def render_goals_section(data: HealthData) -> list[str]:
    """Render the goals section of the dropdown."""
    lines = []
    goals = data.goals()

    # Steps (find latest day with data)
    steps_result = find_latest_with_steps(data)
    if steps_result:
        stats_entry, is_today = steps_result
        steps = stats_entry.total_steps
        steps_pct = (steps / goals.daily_steps) * 100 if goals.daily_steps > 0 else 100
        steps_color = get_color(steps_pct)
        bar = progress_bar(steps_pct)

        if steps_pct >= 100:
            badge = "✓"
        else:
            remaining = goals.daily_steps - steps
            badge = f"{format_number(remaining)} to go"

        date_suffix = "" if is_today else f" ({stats_entry.date})"
        lines.append(f"Steps: {bar} {int(steps_pct)}%{date_suffix} | sfimage=figure.walk sfcolor={steps_color} badge={badge} color=black,white")

        # 7-day average
        avg_steps = data.avg_steps(7)
        lines.append(f"   {format_number(steps)} / {format_number(goals.daily_steps)} (7d avg: {format_number(avg_steps)}) | size=11 color=#666666,#bbbbbb")

    # Weight
    latest_weight = data.latest_weight()
    if latest_weight:
        weight = latest_weight.weight_kg
        diff = weight - goals.weight_kg
        weight_color = get_weight_color(diff)
        trend = data.weight_trend(7)

        if diff <= 0:
            badge = "Goal!"
        else:
            badge = f"-{diff:.1f}kg"

        lines.append(f"Weight: {weight:.1f}kg → {goals.weight_kg:.0f}kg | sfimage=scalemass sfcolor={weight_color} badge={badge} color=black,white")
        lines.append(f"   {latest_weight.date} · 7d: {trend:+.1f}kg | size=11 color=#666666,#bbbbbb")

    # Sleep (find latest day with data)
    sleep_result = find_latest_with_sleep(data)
    if sleep_result:
        sleep_entry, is_recent = sleep_result
        sleep_hrs = sleep_entry.duration_hours
        sleep_pct = (sleep_hrs / goals.sleep_hours) * 100 if goals.sleep_hours > 0 else 100
        sleep_color = get_color(sleep_pct)
        bar = progress_bar(sleep_pct)

        if sleep_pct >= 100:
            badge = "✓"
        else:
            needed_min = int((goals.sleep_hours - sleep_hrs) * 60)
            badge = f"+{needed_min}min"

        date_suffix = "" if is_recent else f" ({sleep_entry.date})"
        lines.append(f"Sleep: {bar} {int(sleep_pct)}%{date_suffix} | sfimage=moon.zzz sfcolor={sleep_color} badge={badge} color=black,white")

        # Details
        avg_sleep = data.avg_sleep_hours(7)
        score_text = f" · Score: {sleep_entry.score}" if sleep_entry.score else ""
        lines.append(f"   {sleep_hrs:.1f}h / {goals.sleep_hours:.0f}h (7d avg: {avg_sleep:.1f}h){score_text} | size=11 color=#666666,#bbbbbb")

    # Workouts
    workouts = count_workouts_this_week(data)
    workout_pct = (workouts / goals.workouts_per_week) * 100 if goals.workouts_per_week > 0 else 100
    workout_color = get_color(workout_pct)
    bar = progress_bar(workout_pct)

    if workouts >= goals.workouts_per_week:
        badge = "✓"
    else:
        left = goals.workouts_per_week - workouts
        badge = f"{left} more"

    lines.append(f"Workouts: {bar} {workouts}/{goals.workouts_per_week} | sfimage=figure.run sfcolor={workout_color} badge={badge} color=black,white")

    return lines


def render_vitals_section(data: HealthData) -> list[str]:
    """Render the vitals section."""
    lines = []
    lines.append("Vitals | size=12 sfimage=waveform.path.ecg color=black,white")

    # Body Battery
    latest_bb = data.latest_body_battery()
    if latest_bb and latest_bb.charged > 0:
        charged = latest_bb.charged
        if charged < 25:
            color = "#d9534f"
        elif charged < 50:
            color = "#f0ad4e"
        else:
            color = "green"
        lines.append(f"--Body Battery: {charged}% | sfimage=battery.100 sfcolor={color} color=black,white")

    # Stress
    latest_stress = data.latest_stress()
    if latest_stress and latest_stress.avg_level > 0:
        stress = latest_stress.avg_level
        if stress > 50:
            color = "#d9534f"
        elif stress > 25:
            color = "#f0ad4e"
        else:
            color = "green"
        lines.append(f"--Stress Level: {stress} | sfimage=brain.head.profile sfcolor={color} color=black,white")

    return lines


def render_analytics_section() -> list[str]:
    """Render the analytics submenu."""
    script = _get_script_path()
    python = _get_python_path()

    lines = [
        "Analytics | size=12 sfimage=chart.line.uptrend.xyaxis color=black,white",
        f"--📊 Goal Progress | bash='{python}' param1='{script}' param2='goals' terminal=true color=black,white",
        f"--📈 Sleep Report | bash='{python}' param1='{script}' param2='sleep-report' terminal=true color=black,white",
        f"--📅 Weekly Patterns | bash='{python}' param1='{script}' param2='patterns' terminal=true color=black,white",
        f"--📉 Weight Trend | bash='{python}' param1='{script}' param2='weight-trend' terminal=true color=black,white",
    ]
    return lines


def render_quick_actions() -> list[str]:
    """Render quick actions submenu."""
    script = _get_script_path()
    python = _get_python_path()

    lines = [
        "Quick Actions | size=12 sfimage=bolt.fill color=black,white",
        f"--📈 Today's Stats | bash='{python}' param1='{script}' param2='today' terminal=true shortcut=CMD+T color=black,white",
        f"--⚖️ Recent Weigh-ins | bash='{python}' param1='{script}' param2='weight' terminal=true color=black,white",
        f"--😴 Last Night's Sleep | bash='{python}' param1='{script}' param2='sleep' terminal=true color=black,white",
        f"--🏃 Recent Activities | bash='{python}' param1='{script}' param2='activities' terminal=true color=black,white",
    ]
    return lines


def render_footer(data: HealthData) -> list[str]:
    """Render footer with sync and links."""
    script = _get_script_path()
    python = _get_python_path()

    lines = []
    last_sync = get_last_sync_time(data.data_dir)

    if last_sync:
        lines.append(f"🔄 Sync Data (last: {last_sync}) | bash='{python}' param1='{script}' param2='export' terminal=true color=black,white")
    else:
        lines.append(f"🔄 Sync Data | bash='{python}' param1='{script}' param2='export' terminal=true color=black,white")

    lines.append("🌐 Open Garmin Connect | href=https://connect.garmin.com color=black,white")
    lines.append("---")
    lines.append("Refresh | refresh=true sfimage=arrow.clockwise color=black,white")

    return lines


def render_widget(data: Optional[HealthData] = None) -> str:
    """Render complete SwiftBar widget output.

    Args:
        data: HealthData instance. If None, uses default.

    Returns:
        Complete widget output as string.
    """
    if data is None:
        data = HealthData.default()

    lines = []

    # Menu bar - no tooltip (was causing cycling/parsing issues in SwiftBar)
    menu_bar, _ = render_menu_bar(data)
    lines.append(menu_bar)

    lines.append("---")

    # Header - use color=black,white for light/dark mode support
    lines.append("Health Dashboard | size=14 sfimage=heart.fill sfcolor=red shortcut=CMD+OPTION+H color=black,white")
    lines.append("---")

    # Goals
    lines.extend(render_goals_section(data))
    lines.append("---")

    # Vitals
    lines.extend(render_vitals_section(data))
    lines.append("---")

    # Analytics
    lines.extend(render_analytics_section())
    lines.append("---")

    # Quick Actions
    lines.extend(render_quick_actions())
    lines.append("---")

    # Footer
    lines.extend(render_footer(data))

    return "\n".join(lines)


if __name__ == "__main__":
    # Allow running directly for testing
    print(render_widget())
