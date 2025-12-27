#!/usr/bin/env python3
"""Daily health summary notification.

Runs at midnight to summarize the day's health metrics.
Sends a macOS notification and optionally logs to markdown file.
"""

import subprocess
import sys
from datetime import date
from pathlib import Path

# Add the src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from garmin_health.data import HealthData
from garmin_health.config import Config
from garmin_health.core import get_data_dir


def send_notification(title: str, message: str, subtitle: str = "", sound: str = "Glass"):
    """Send macOS notification with sound."""
    # Escape quotes for osascript
    message = message.replace('"', '\\"')
    subtitle = subtitle.replace('"', '\\"')

    script = f'display notification "{message}" with title "{title}"'
    if subtitle:
        script = f'display notification "{message}" with title "{title}" subtitle "{subtitle}"'
    if sound:
        script += f' sound name "{sound}"'

    subprocess.run(["osascript", "-e", script], capture_output=True)


def append_to_markdown_log(log_path: Path, summary: dict):
    """Append daily summary to markdown log file.

    Args:
        log_path: Path to the markdown log file.
        summary: Dictionary with summary data.
    """
    today = date.today().isoformat()

    # Build markdown entry
    lines = [
        f"## {today}",
        "",
        "| Metric | Value | Goal | Status |",
        "|--------|-------|------|--------|",
    ]

    # Steps row
    steps = summary.get("steps", 0)
    steps_goal = summary.get("steps_goal", 10000)
    steps_pct = int((steps / steps_goal) * 100) if steps_goal else 0
    steps_status = "✓" if steps >= steps_goal else f"{steps_pct}%"
    lines.append(f"| Steps | {steps:,} | {steps_goal:,} | {steps_status} |")

    # Sleep row
    sleep_hrs = summary.get("sleep_hrs", 0)
    sleep_goal = summary.get("sleep_goal", 7)
    sleep_pct = int((sleep_hrs / sleep_goal) * 100) if sleep_goal else 0
    sleep_status = "✓" if sleep_hrs >= sleep_goal else f"{sleep_pct}%"
    lines.append(f"| Sleep | {sleep_hrs:.1f}h | {sleep_goal}h | {sleep_status} |")

    # Weight row
    weight = summary.get("weight", 0)
    weight_goal = summary.get("weight_goal", 0)
    if weight > 0:
        diff = weight - weight_goal
        weight_status = "✓" if diff <= 0 else f"↓{diff:.1f}kg"
        lines.append(f"| Weight | {weight:.1f}kg | {weight_goal}kg | {weight_status} |")

    # Body battery row
    bb = summary.get("body_battery", 0)
    if bb > 0:
        lines.append(f"| Body Battery | {bb}% | - | - |")

    # Overall status
    status_msg = summary.get("status", "")
    if status_msg:
        lines.append("")
        lines.append(f"**Status:** {status_msg}")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Append to file
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # If file doesn't exist, add header
    if not log_path.exists():
        header = [
            "# Daily Health Summaries",
            "",
            "Automatically logged by garmin-health at midnight.",
            "",
            "---",
            "",
        ]
        with open(log_path, "w") as f:
            f.write("\n".join(header))

    with open(log_path, "a") as f:
        f.write("\n".join(lines))


def daily_summary():
    """Generate and send daily health summary."""
    config = Config.load()

    if not config.notifications.daily_summary_enabled:
        return

    try:
        data = HealthData.default()
        goals = data.goals()

        # Get today's stats
        stats = list(data.stats())
        today_stats = stats[-1] if stats else None
        steps = today_stats.total_steps if today_stats else 0
        steps_pct = int((steps / goals.daily_steps) * 100) if goals.daily_steps else 0
        steps_met = "✓" if steps >= goals.daily_steps else ""

        # Weight
        latest_weight = data.latest_weight()
        weight = latest_weight.weight_kg if latest_weight else 0
        weight_trend = data.weight_trend(7)

        # Sleep (from last night)
        latest_sleep = data.latest_sleep()
        sleep_hrs = latest_sleep.duration_hours if latest_sleep else 0
        sleep_score = latest_sleep.score if latest_sleep else 0
        sleep_met = "✓" if sleep_hrs >= goals.sleep_hours else ""

        # Body battery
        latest_bb = data.latest_body_battery()
        bb = latest_bb.charged if latest_bb else 0

        # Build summary message for notification
        lines = []

        # Steps
        if steps_met:
            lines.append(f"👟 {steps:,} steps {steps_met} ({steps_pct}%)")
        else:
            remaining = goals.daily_steps - steps
            lines.append(f"👟 {steps:,}/{goals.daily_steps:,} steps ({remaining:,} short)")

        # Weight
        if weight > 0:
            trend_arrow = "↓" if weight_trend < 0 else "↑" if weight_trend > 0 else "→"
            lines.append(f"⚖️ {weight:.1f}kg ({trend_arrow}{abs(weight_trend):.1f} this week)")

        # Sleep
        if sleep_hrs > 0:
            score_str = f" (score: {sleep_score})" if sleep_score else ""
            lines.append(f"😴 {sleep_hrs:.1f}h{sleep_met}{score_str}")

        # Body battery
        if bb > 0:
            lines.append(f"🔋 Body Battery: {bb}%")

        message = " | ".join(lines)

        # Determine overall status for subtitle
        goals_met = sum([
            1 if steps >= goals.daily_steps else 0,
            1 if sleep_hrs >= goals.sleep_hours else 0,
        ])

        if goals_met == 2:
            status = "Great day! All goals met 🎉"
        elif goals_met == 1:
            status = "Good effort today"
        else:
            status = "Tomorrow is a new day"

        # Send notification
        send_notification(
            "Daily Health Summary",
            message,
            status,
            config.notifications.sound
        )
        print(f"Summary sent: {message}")

        # Log to markdown if enabled
        if config.notifications.log_to_markdown:
            log_path = get_data_dir() / config.notifications.log_file
            summary_data = {
                "steps": steps,
                "steps_goal": goals.daily_steps,
                "sleep_hrs": sleep_hrs,
                "sleep_goal": goals.sleep_hours,
                "weight": weight,
                "weight_goal": goals.weight_kg,
                "body_battery": bb,
                "status": status,
            }
            append_to_markdown_log(log_path, summary_data)
            print(f"Logged to: {log_path}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        send_notification("Health Summary", f"Error generating summary: {e}")
        sys.exit(1)


if __name__ == "__main__":
    daily_summary()
