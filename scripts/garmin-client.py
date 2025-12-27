#!/usr/bin/env python3
"""
Garmin Connect API client for health data.
Credentials stored in macOS Keychain.

Uses shared core module to avoid code duplication with sync daemon.
"""

import sys
import json
from datetime import date, datetime, timedelta
from pathlib import Path

# Add the src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from garmin_health.core import get_client, get_data_dir


def cmd_test():
    """Test connection to Garmin."""
    client = get_client()
    user = client.get_full_name()
    print(f"Connected to Garmin Connect as: {user}")


def cmd_today():
    """Get today's summary."""
    client = get_client()
    today = date.today().isoformat()

    # Get daily summary
    try:
        stats = client.get_stats(today)

        print("=== Today's Stats ===")
        steps = stats.get('totalSteps') or 0
        step_goal = stats.get('dailyStepGoal') or 10000
        calories = stats.get('totalKilocalories') or 0
        active_secs = stats.get('highlyActiveSeconds') or 0

        print(f"Steps: {steps:,} / {step_goal:,}")
        print(f"Calories: {calories:,} kcal")
        print(f"Active Minutes: {active_secs // 60} min")

        rhr = stats.get('restingHeartRate')
        if rhr:
            print(f"Resting HR: {rhr} bpm")

        # Get weight
        try:
            weight_data = client.get_body_composition(today)
            if weight_data and weight_data.get('weight'):
                weight_kg = weight_data['weight'] / 1000
                print(f"Weight: {weight_kg:.1f} kg")
        except Exception:
            pass

        # Get sleep
        try:
            sleep = client.get_sleep_data(today)
            if sleep and sleep.get('dailySleepDTO'):
                sleep_dto = sleep['dailySleepDTO']
                sleep_mins = sleep_dto.get('sleepTimeSeconds', 0) // 60
                sleep_hrs = sleep_mins // 60
                sleep_mins = sleep_mins % 60
                print(f"Sleep: {sleep_hrs}h {sleep_mins}m")
        except Exception:
            pass

    except Exception as e:
        print(f"Error getting today's stats: {e}")


def cmd_weight():
    """Get weight data and trends."""
    client = get_client()
    today = date.today()

    # Get last 30 days of weight data
    end_date = today.isoformat()
    start_date = (today - timedelta(days=30)).isoformat()

    try:
        weight_data = client.get_weigh_ins(start_date, end_date)

        if not weight_data or 'dailyWeightSummaries' not in weight_data:
            print("No weight data found in the last 30 days.")
            return

        summaries = weight_data['dailyWeightSummaries']
        if not summaries:
            print("No weight entries found.")
            return

        print("=== Weight Data ===")

        # Latest weight
        latest = summaries[-1]
        latest_kg = latest.get('maxWeight', 0) / 1000
        latest_date = latest.get('summaryDate', 'Unknown')
        print(f"Current: {latest_kg:.1f} kg ({latest_date})")

        # 7-day change
        if len(summaries) >= 2:
            week_ago_idx = max(0, len(summaries) - 8)
            week_ago = summaries[week_ago_idx]
            week_ago_kg = week_ago.get('maxWeight', 0) / 1000
            change = latest_kg - week_ago_kg
            trend = "↓" if change < 0 else "↑" if change > 0 else "→"
            print(f"7-day trend: {trend} {abs(change):.1f} kg")

        # Recent entries
        print("\nRecent measurements:")
        for entry in summaries[-5:]:
            entry_date = entry.get('summaryDate', '')
            entry_kg = entry.get('maxWeight', 0) / 1000
            print(f"  {entry_date}: {entry_kg:.1f} kg")

    except Exception as e:
        print(f"Error getting weight data: {e}")


def cmd_sleep():
    """Get sleep analysis."""
    client = get_client()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    try:
        # Try yesterday's sleep (most recent complete night)
        sleep = client.get_sleep_data(yesterday)

        if not sleep or not sleep.get('dailySleepDTO'):
            print("No sleep data found.")
            return

        dto = sleep['dailySleepDTO']

        print("=== Last Night's Sleep ===")

        sleep_secs = dto.get('sleepTimeSeconds') or 0
        total_mins = sleep_secs // 60
        hrs = total_mins // 60
        mins = total_mins % 60
        print(f"Duration: {hrs}h {mins}m")

        # Sleep stages
        stages = dto.get('sleepLevelsMap', {})
        if stages:
            print("\nSleep Stages:")
            for stage, data in stages.items():
                if isinstance(data, list) and data:
                    stage_mins = sum(d.get('seconds', 0) for d in data) // 60
                    print(f"  {stage.capitalize()}: {stage_mins} min")

        # Sleep score
        score = dto.get('sleepScores', {}).get('overall', {}).get('value')
        if score:
            print(f"\nSleep Score: {score}")

    except Exception as e:
        print(f"Error getting sleep data: {e}")


def cmd_activities():
    """Get recent activities."""
    client = get_client()

    try:
        activities = client.get_activities(0, 10)  # Last 10 activities

        if not activities:
            print("No recent activities found.")
            return

        print("=== Recent Activities ===")

        for act in activities[:5]:
            name = act.get('activityName', 'Unknown')
            act_type = act.get('activityType', {}).get('typeKey', 'unknown')
            start = act.get('startTimeLocal', '')[:10]
            duration_mins = act.get('duration', 0) / 60
            distance_km = act.get('distance', 0) / 1000 if act.get('distance') else 0

            print(f"\n{start}: {name}")
            print(f"  Type: {act_type}")
            print(f"  Duration: {int(duration_mins)} min")
            if distance_km > 0:
                print(f"  Distance: {distance_km:.2f} km")

    except Exception as e:
        print(f"Error getting activities: {e}")


def cmd_goals():
    """Show progress towards health goals."""
    data_dir = get_data_dir()
    goals_file = data_dir / "goals.json"

    if not goals_file.exists():
        print("Error: goals.json not found.")
        print(f"Create {goals_file} with your targets.")
        sys.exit(1)

    with open(goals_file) as f:
        goals = json.load(f)

    print("╔════════════════════════════════════════════╗")
    print("║           HEALTH GOAL PROGRESS             ║")
    print("╚════════════════════════════════════════════╝\n")

    # Weight goal
    target_weight = goals.get('weight_kg', 0)
    if target_weight > 0:
        weight_file = data_dir / "weight.json"
        if weight_file.exists():
            with open(weight_file) as f:
                weight_data = json.load(f)
            summaries = weight_data.get('dailyWeightSummaries', [])
            if summaries:
                # Sort by date (API returns newest first, we want chronological)
                summaries = sorted(summaries, key=lambda x: x.get('summaryDate', ''))
                latest = summaries[-1]
                current_weight = latest.get('maxWeight', 0) / 1000
                latest_date = latest.get('summaryDate', '')
                diff = current_weight - target_weight
                pct = min(100, max(0, 100 - abs(diff) / target_weight * 100))

                if diff <= 0:
                    status = "🎯 GOAL REACHED!"
                elif diff < 5:
                    status = f"Almost! ↓ {diff:.1f} kg"
                else:
                    status = f"↓ {diff:.1f} kg to go"

                bar_len = 20
                filled = int(pct / 100 * bar_len)
                bar = "█" * filled + "░" * (bar_len - filled)

                print(f"⚖️  WEIGHT ({latest_date})")
                print(f"   Current: {current_weight:.1f} kg  →  Target: {target_weight} kg")
                print(f"   [{bar}] {status}")

                # Trend (last 7 days)
                if len(summaries) >= 2:
                    week_ago_idx = max(0, len(summaries) - 8)
                    week_ago_kg = summaries[week_ago_idx].get('maxWeight', 0) / 1000
                    trend = current_weight - week_ago_kg
                    trend_arrow = "↓" if trend < 0 else "↑" if trend > 0 else "→"
                    print(f"   7-day trend: {trend_arrow} {abs(trend):.1f} kg\n")
        else:
            print("⚖️  WEIGHT: No data (run `garmin export` first)\n")

    # Steps goal
    target_steps = goals.get('daily_steps', 0)
    if target_steps > 0:
        stats_file = data_dir / "daily_stats.json"
        if stats_file.exists():
            with open(stats_file) as f:
                stats_data = json.load(f)

            # Find today's stats
            today = date.today().isoformat()
            today_stats = next((s for s in stats_data if s.get('_date') == today), None)

            if today_stats:
                current_steps = today_stats.get('totalSteps') or 0
            else:
                # Fallback to API
                try:
                    client = get_client()
                    live_stats = client.get_stats(today)
                    current_steps = live_stats.get('totalSteps') or 0
                except Exception:
                    current_steps = 0

            pct = min(100, current_steps / target_steps * 100)
            bar_len = 20
            filled = int(pct / 100 * bar_len)
            bar = "█" * filled + "░" * (bar_len - filled)

            if pct >= 100:
                status = "🎯 GOAL REACHED!"
            elif pct >= 75:
                status = f"Almost! {int(target_steps - current_steps):,} more"
            else:
                status = f"{int(target_steps - current_steps):,} steps to go"

            print("👟 STEPS (Today)")
            print(f"   Current: {current_steps:,}  →  Target: {target_steps:,}")
            print(f"   [{bar}] {pct:.0f}% {status}")

            # 7-day average
            week_stats = [s for s in stats_data if s.get('_date', '') >= (date.today() - timedelta(days=7)).isoformat()]
            if week_stats:
                avg_steps = sum(s.get('totalSteps') or 0 for s in week_stats) / len(week_stats)
                avg_pct = avg_steps / target_steps * 100
                print(f"   7-day avg: {int(avg_steps):,} ({avg_pct:.0f}% of goal)\n")
        else:
            print("👟 STEPS: No data (run `garmin export` first)\n")

    # Sleep goal
    target_sleep = goals.get('sleep_hours', 0)
    if target_sleep > 0:
        sleep_file = data_dir / "sleep.json"
        if sleep_file.exists():
            with open(sleep_file) as f:
                sleep_data = json.load(f)

            # Get most recent sleep (sort by date, newest first)
            if sleep_data:
                sleep_sorted = sorted(sleep_data, key=lambda x: x.get('_date', ''), reverse=True)
                latest = sleep_sorted[0]
                sleep_secs = latest.get('dailySleepDTO', {}).get('sleepTimeSeconds') or 0
                sleep_hrs = sleep_secs / 3600

                pct = min(100, sleep_hrs / target_sleep * 100)
                bar_len = 20
                filled = int(pct / 100 * bar_len)
                bar = "█" * filled + "░" * (bar_len - filled)

                if pct >= 100:
                    status = "🎯 GOAL REACHED!"
                elif pct >= 85:
                    status = f"Almost! +{(target_sleep - sleep_hrs)*60:.0f} min"
                else:
                    status = f"+{(target_sleep - sleep_hrs)*60:.0f} min needed"

                print("😴 SLEEP (Last Night)")
                print(f"   Duration: {sleep_hrs:.1f}h  →  Target: {target_sleep}h")
                print(f"   [{bar}] {pct:.0f}% {status}")

                # 7-day average
                week_sleep = sleep_sorted[:7] if len(sleep_sorted) >= 7 else sleep_sorted
                avg_secs = sum(s.get('dailySleepDTO', {}).get('sleepTimeSeconds') or 0 for s in week_sleep) / len(week_sleep)
                avg_hrs = avg_secs / 3600
                avg_pct = avg_hrs / target_sleep * 100
                print(f"   7-day avg: {avg_hrs:.1f}h ({avg_pct:.0f}% of goal)\n")
        else:
            print("😴 SLEEP: No data (run `garmin export` first)\n")

    # Workouts goal (weekly)
    target_workouts = goals.get('workouts_per_week', 0)
    if target_workouts > 0:
        activities_file = data_dir / "activities.json"
        if activities_file.exists():
            with open(activities_file) as f:
                activities = json.load(f)

            # Count activities in last 7 days
            week_ago = (date.today() - timedelta(days=7)).isoformat()
            week_activities = [a for a in activities if a.get('startTimeLocal', '')[:10] >= week_ago]
            count = len(week_activities)

            pct = min(100, count / target_workouts * 100)
            bar_len = 20
            filled = int(pct / 100 * bar_len)
            bar = "█" * filled + "░" * (bar_len - filled)

            if count >= target_workouts:
                status = "🎯 GOAL REACHED!"
            else:
                status = f"{target_workouts - count} more workout(s) needed"

            print("🏃 WORKOUTS (This Week)")
            print(f"   Count: {count}  →  Target: {target_workouts}/week")
            print(f"   [{bar}] {status}\n")
        else:
            print("🏃 WORKOUTS: No data (run `garmin export` first)\n")

    print("─" * 44)
    print("📅 Data updated: check file dates in ~/Health/Garmin/")


def cmd_export():
    """Export all Garmin data to disk."""
    import time

    client = get_client()
    export_dir = get_data_dir()
    export_dir.mkdir(parents=True, exist_ok=True)

    today = date.today()

    print(f"=== Exporting Garmin Data to {export_dir} ===\n")

    # 1. Export ALL activities (paginate through all)
    print("Fetching activities...")
    try:
        all_activities = []
        start = 0
        batch_size = 100
        while True:
            batch = client.get_activities(start, batch_size)
            if not batch:
                break
            all_activities.extend(batch)
            print(f"    ... {len(all_activities)} activities fetched")
            if len(batch) < batch_size:
                break
            start += batch_size
            time.sleep(0.5)

        with open(export_dir / "activities.json", "w") as f:
            json.dump(all_activities, f, indent=2, default=str)
        print(f"  ✓ {len(all_activities)} activities saved")
    except Exception as e:
        print(f"  ✗ Activities failed: {e}")

    # 2. Export weight data (last 5 years)
    print("Fetching weight data...")
    try:
        start = (today - timedelta(days=365*5)).isoformat()
        end = today.isoformat()
        weight = client.get_weigh_ins(start, end)
        with open(export_dir / "weight.json", "w") as f:
            json.dump(weight, f, indent=2, default=str)
        count = len(weight.get('dailyWeightSummaries', [])) if weight else 0
        print(f"  ✓ {count} weight entries saved")
    except Exception as e:
        print(f"  ✗ Weight failed: {e}")

    # 3. Export daily stats (6 years, every day)
    print("Fetching daily stats (6 years - this takes ~5 min)...")
    all_stats = []
    try:
        for days_back in range(0, 2200, 1):
            stat_date = (today - timedelta(days=days_back)).isoformat()
            try:
                stats = client.get_stats(stat_date)
                if stats:
                    stats['_date'] = stat_date
                    all_stats.append(stats)
            except Exception:
                pass
            if days_back % 100 == 0 and days_back > 0:
                print(f"    ... {days_back} days checked, {len(all_stats)} records found")
                time.sleep(1)
            time.sleep(0.05)

        with open(export_dir / "daily_stats.json", "w") as f:
            json.dump(all_stats, f, indent=2, default=str)
        print(f"  ✓ {len(all_stats)} days of stats saved")
    except Exception as e:
        print(f"  ✗ Daily stats failed: {e}")

    # 4. Export sleep data (last 6 years - ~2190 days)
    print("Fetching sleep data (6 years - this takes ~5 min)...")
    all_sleep = []
    try:
        for days_back in range(0, 2200, 1):  # 6 years
            sleep_date = (today - timedelta(days=days_back)).isoformat()
            try:
                sleep = client.get_sleep_data(sleep_date)
                if sleep and sleep.get('dailySleepDTO'):
                    sleep['_date'] = sleep_date
                    all_sleep.append(sleep)
            except Exception:
                pass
            if days_back % 100 == 0 and days_back > 0:
                print(f"    ... {days_back} days checked, {len(all_sleep)} sleep records found")
                time.sleep(1)  # Longer pause every 100 days
            time.sleep(0.05)  # Faster but still respectful

        with open(export_dir / "sleep.json", "w") as f:
            json.dump(all_sleep, f, indent=2, default=str)
        print(f"  ✓ {len(all_sleep)} nights of sleep saved")
    except Exception as e:
        print(f"  ✗ Sleep failed: {e}")

    # 5. Export heart rate data (last 30 days - more detailed)
    print("Fetching heart rate data (last 30 days)...")
    all_hr = []
    try:
        for days_back in range(0, 30):
            hr_date = (today - timedelta(days=days_back)).isoformat()
            try:
                hr = client.get_heart_rates(hr_date)
                if hr:
                    hr['_date'] = hr_date
                    all_hr.append(hr)
            except Exception:
                pass
            time.sleep(0.2)

        with open(export_dir / "heart_rate.json", "w") as f:
            json.dump(all_hr, f, indent=2, default=str)
        print(f"  ✓ {len(all_hr)} days of HR data saved")
    except Exception as e:
        print(f"  ✗ Heart rate failed: {e}")

    # 6. Export user profile
    print("Fetching user profile...")
    try:
        profile = client.get_user_summary(today.isoformat())
        with open(export_dir / "profile.json", "w") as f:
            json.dump(profile, f, indent=2, default=str)
        print("  ✓ Profile saved")
    except Exception as e:
        print(f"  ✗ Profile failed: {e}")

    # 7. Personal records
    print("Fetching personal records...")
    try:
        records = client.get_personal_record()
        with open(export_dir / "personal_records.json", "w") as f:
            json.dump(records, f, indent=2, default=str)
        print("  ✓ Personal records saved")
    except Exception as e:
        print(f"  ✗ Personal records failed: {e}")

    # 8. Body Battery (6 years)
    print("Fetching body battery data (6 years)...")
    all_bb = []
    try:
        for days_back in range(0, 2200, 1):
            bb_date = (today - timedelta(days=days_back)).isoformat()
            try:
                bb = client.get_body_battery(bb_date)
                if bb:
                    bb_entry = {'_date': bb_date, 'data': bb}
                    all_bb.append(bb_entry)
            except Exception:
                pass
            if days_back % 100 == 0 and days_back > 0:
                print(f"    ... {days_back} days checked, {len(all_bb)} records found")
                time.sleep(1)
            time.sleep(0.05)

        with open(export_dir / "body_battery.json", "w") as f:
            json.dump(all_bb, f, indent=2, default=str)
        print(f"  ✓ {len(all_bb)} days of body battery saved")
    except Exception as e:
        print(f"  ✗ Body battery failed: {e}")

    # 9. Stress data (6 years)
    print("Fetching stress data (6 years)...")
    all_stress = []
    try:
        for days_back in range(0, 2200, 1):
            stress_date = (today - timedelta(days=days_back)).isoformat()
            try:
                stress = client.get_stress_data(stress_date)
                if stress:
                    stress['_date'] = stress_date
                    all_stress.append(stress)
            except Exception:
                pass
            if days_back % 100 == 0 and days_back > 0:
                print(f"    ... {days_back} days checked, {len(all_stress)} records found")
                time.sleep(1)
            time.sleep(0.05)

        with open(export_dir / "stress.json", "w") as f:
            json.dump(all_stress, f, indent=2, default=str)
        print(f"  ✓ {len(all_stress)} days of stress data saved")
    except Exception as e:
        print(f"  ✗ Stress failed: {e}")

    # 10. HRV data (6 years)
    print("Fetching HRV data (6 years)...")
    all_hrv = []
    try:
        for days_back in range(0, 2200, 1):
            hrv_date = (today - timedelta(days=days_back)).isoformat()
            try:
                hrv = client.get_hrv_data(hrv_date)
                if hrv:
                    hrv['_date'] = hrv_date
                    all_hrv.append(hrv)
            except Exception:
                pass
            if days_back % 100 == 0 and days_back > 0:
                print(f"    ... {days_back} days checked, {len(all_hrv)} records found")
                time.sleep(1)
            time.sleep(0.05)

        with open(export_dir / "hrv.json", "w") as f:
            json.dump(all_hrv, f, indent=2, default=str)
        print(f"  ✓ {len(all_hrv)} days of HRV saved")
    except Exception as e:
        print(f"  ✗ HRV failed: {e}")

    # 11. Training status & readiness (recent - these are newer features)
    print("Fetching training metrics...")
    try:
        training = client.get_training_status(today.isoformat())
        with open(export_dir / "training_status.json", "w") as f:
            json.dump(training, f, indent=2, default=str)
        print("  ✓ Training status saved")
    except Exception as e:
        print(f"  ✗ Training status failed: {e}")

    try:
        readiness = client.get_training_readiness(today.isoformat())
        with open(export_dir / "training_readiness.json", "w") as f:
            json.dump(readiness, f, indent=2, default=str)
        print("  ✓ Training readiness saved")
    except Exception as e:
        print(f"  ✗ Training readiness failed: {e}")

    # 12. Respiration data (last year - typically newer feature)
    print("Fetching respiration data (1 year)...")
    all_resp = []
    try:
        for days_back in range(0, 365, 1):
            resp_date = (today - timedelta(days=days_back)).isoformat()
            try:
                resp = client.get_respiration_data(resp_date)
                if resp:
                    resp['_date'] = resp_date
                    all_resp.append(resp)
            except Exception:
                pass
            time.sleep(0.05)

        with open(export_dir / "respiration.json", "w") as f:
            json.dump(all_resp, f, indent=2, default=str)
        print(f"  ✓ {len(all_resp)} days of respiration saved")
    except Exception as e:
        print(f"  ✗ Respiration failed: {e}")

    # 13. SpO2 data (last year)
    print("Fetching SpO2 data (1 year)...")
    all_spo2 = []
    try:
        for days_back in range(0, 365, 1):
            spo2_date = (today - timedelta(days=days_back)).isoformat()
            try:
                spo2 = client.get_spo2_data(spo2_date)
                if spo2:
                    spo2['_date'] = spo2_date
                    all_spo2.append(spo2)
            except Exception:
                pass
            time.sleep(0.05)

        with open(export_dir / "spo2.json", "w") as f:
            json.dump(all_spo2, f, indent=2, default=str)
        print(f"  ✓ {len(all_spo2)} days of SpO2 saved")
    except Exception as e:
        print(f"  ✗ SpO2 failed: {e}")

    # 14. Devices info
    print("Fetching device info...")
    try:
        devices = client.get_devices()
        with open(export_dir / "devices.json", "w") as f:
            json.dump(devices, f, indent=2, default=str)
        print(f"  ✓ {len(devices) if devices else 0} devices saved")
    except Exception as e:
        print(f"  ✗ Devices failed: {e}")

    # 15. Earned badges & challenges
    print("Fetching badges...")
    try:
        badges = client.get_earned_badges()
        with open(export_dir / "badges.json", "w") as f:
            json.dump(badges, f, indent=2, default=str)
        print("  ✓ Badges saved")
    except Exception as e:
        print(f"  ✗ Badges failed: {e}")

    print("\n=== Export complete! ===")
    print(f"Data saved to: {export_dir}")

    # List files
    for f in sorted(export_dir.glob("*.json")):
        size = f.stat().st_size
        if size > 1024*1024:
            size_str = f"{size/1024/1024:.1f} MB"
        elif size > 1024:
            size_str = f"{size/1024:.1f} KB"
        else:
            size_str = f"{size} B"
        print(f"  {f.name}: {size_str}")


def cmd_sleep_report():
    """Comprehensive sleep analysis with correlations."""
    data_dir = get_data_dir()

    print("╔════════════════════════════════════════════╗")
    print("║           SLEEP ANALYSIS REPORT            ║")
    print("╚════════════════════════════════════════════╝\n")

    # Load sleep data
    sleep_file = data_dir / "sleep.json"
    if not sleep_file.exists():
        print("No sleep data found. Run `garmin export` first.")
        return

    with open(sleep_file) as f:
        sleep_data = json.load(f)

    if not sleep_data:
        print("No sleep records found.")
        return

    # Basic stats
    total_nights = len(sleep_data)
    durations = []
    scores = []
    deep_pcts = []
    rem_pcts = []

    for night in sleep_data:
        dto = night.get('dailySleepDTO', {})
        secs = dto.get('sleepTimeSeconds', 0)
        if secs:
            durations.append(secs / 3600)

        score_data = dto.get('sleepScores', {})
        if score_data:
            overall = score_data.get('overall', {}).get('value')
            if overall:
                scores.append(overall)

        # Sleep stages
        stages = dto.get('sleepLevels', {})
        total_sleep = dto.get('sleepTimeSeconds') or 1
        deep = (stages.get('deep', {}) or {}).get('seconds', 0) or 0
        rem = (stages.get('rem', {}) or {}).get('seconds', 0) or 0
        if total_sleep and total_sleep > 0:
            deep_pcts.append(deep / total_sleep * 100)
            rem_pcts.append(rem / total_sleep * 100)

    print(f"📊 OVERVIEW ({total_nights} nights analyzed)")
    print("─" * 44)

    if durations:
        avg_duration = sum(durations) / len(durations)
        min_duration = min(durations)
        max_duration = max(durations)
        print(f"   Duration:  avg {avg_duration:.1f}h  (range: {min_duration:.1f}h - {max_duration:.1f}h)")

    if scores:
        avg_score = sum(scores) / len(scores)
        print(f"   Sleep Score: avg {avg_score:.0f}/100")

    if deep_pcts:
        avg_deep = sum(deep_pcts) / len(deep_pcts)
        print(f"   Deep Sleep: avg {avg_deep:.1f}%")

    if rem_pcts:
        avg_rem = sum(rem_pcts) / len(rem_pcts)
        print(f"   REM Sleep: avg {avg_rem:.1f}%")

    # Weekly patterns
    print("\n📅 WEEKLY PATTERNS")
    print("─" * 44)

    weekday_durations = {i: [] for i in range(7)}
    for night in sleep_data:
        date_str = night.get('_date', '')
        if date_str:
            try:
                d = datetime.strptime(date_str, '%Y-%m-%d')
                weekday = d.weekday()
                secs = night.get('dailySleepDTO', {}).get('sleepTimeSeconds', 0)
                if secs:
                    weekday_durations[weekday].append(secs / 3600)
            except Exception:
                pass

    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    for i, day in enumerate(days):
        if weekday_durations[i]:
            avg = sum(weekday_durations[i]) / len(weekday_durations[i])
            bar_len = int(avg * 2)  # Scale for display
            bar = "█" * min(bar_len, 20)
            print(f"   {day}: {bar} {avg:.1f}h")

    # Recent trends (last 30 days)
    print("\n📈 RECENT TRENDS (Last 30 days)")
    print("─" * 44)

    recent = sorted(sleep_data, key=lambda x: x.get('_date', ''), reverse=True)[:30]
    if len(recent) >= 7:
        last_7 = recent[:7]
        prev_7 = recent[7:14] if len(recent) >= 14 else []

        def get_sleep_hrs(n):
            secs = (n.get('dailySleepDTO') or {}).get('sleepTimeSeconds') or 0
            return secs / 3600

        last_7_avg = sum(get_sleep_hrs(n) for n in last_7) / len(last_7)
        print(f"   Last 7 days avg: {last_7_avg:.1f}h")

        if prev_7:
            prev_7_avg = sum(get_sleep_hrs(n) for n in prev_7) / len(prev_7)
            change = last_7_avg - prev_7_avg
            trend = "↑" if change > 0 else "↓" if change < 0 else "→"
            print(f"   vs previous week: {trend} {abs(change):.1f}h ({'+' if change >= 0 else ''}{change*60:.0f} min)")

    # Load activity data for correlation
    stats_file = data_dir / "daily_stats.json"
    if stats_file.exists():
        print("\n🔗 ACTIVITY-SLEEP CORRELATION")
        print("─" * 44)

        with open(stats_file) as f:
            stats_data = json.load(f)

        # Build lookup by date
        stats_by_date = {s.get('_date'): s for s in stats_data}

        high_activity_sleep = []
        low_activity_sleep = []

        for night in sleep_data:
            sleep_date = night.get('_date', '')
            # Get previous day's activity
            try:
                prev_date = (datetime.strptime(sleep_date, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
                prev_stats = stats_by_date.get(prev_date)
                if prev_stats:
                    steps = prev_stats.get('totalSteps', 0) or 0
                    sleep_hrs = night.get('dailySleepDTO', {}).get('sleepTimeSeconds', 0) / 3600
                    if sleep_hrs > 0:
                        if steps > 10000:
                            high_activity_sleep.append(sleep_hrs)
                        elif steps < 5000:
                            low_activity_sleep.append(sleep_hrs)
            except Exception:
                pass

        if high_activity_sleep and low_activity_sleep:
            high_avg = sum(high_activity_sleep) / len(high_activity_sleep)
            low_avg = sum(low_activity_sleep) / len(low_activity_sleep)
            diff = high_avg - low_avg
            print(f"   After 10k+ steps: avg {high_avg:.1f}h sleep ({len(high_activity_sleep)} nights)")
            print(f"   After <5k steps:  avg {low_avg:.1f}h sleep ({len(low_activity_sleep)} nights)")
            print(f"   Difference: {'+' if diff >= 0 else ''}{diff*60:.0f} min")

    print("\n" + "═" * 44)


def cmd_patterns():
    """Weekly and seasonal pattern analysis."""
    data_dir = get_data_dir()

    print("╔════════════════════════════════════════════╗")
    print("║         WEEKLY & SEASONAL PATTERNS         ║")
    print("╚════════════════════════════════════════════╝\n")

    # Load daily stats
    stats_file = data_dir / "daily_stats.json"
    if not stats_file.exists():
        print("No daily stats found. Run `garmin export` first.")
        return

    with open(stats_file) as f:
        stats_data = json.load(f)

    # Load stress data
    stress_file = data_dir / "stress.json"
    stress_by_date = {}
    if stress_file.exists():
        with open(stress_file) as f:
            stress_data = json.load(f)
        stress_by_date = {s.get('_date'): s for s in stress_data}

    # Weekly patterns
    print("📅 DAY-OF-WEEK PATTERNS")
    print("─" * 44)

    weekday_steps = {i: [] for i in range(7)}
    weekday_stress = {i: [] for i in range(7)}

    for stat in stats_data:
        date_str = stat.get('_date', '')
        if date_str:
            try:
                d = datetime.strptime(date_str, '%Y-%m-%d')
                weekday = d.weekday()
                steps = stat.get('totalSteps', 0)
                if steps:
                    weekday_steps[weekday].append(steps)

                stress = stress_by_date.get(date_str, {}).get('overallStressLevel')
                if stress:
                    weekday_stress[weekday].append(stress)
            except Exception:
                pass

    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    print("\n   Steps by day:")
    max_steps = max(sum(v)/len(v) if v else 0 for v in weekday_steps.values()) or 1
    for i, day in enumerate(days):
        if weekday_steps[i]:
            avg = sum(weekday_steps[i]) / len(weekday_steps[i])
            bar_len = int(avg / max_steps * 15)
            bar = "█" * bar_len
            print(f"   {day}: {bar} {avg:,.0f}")

    print("\n   Stress by day:")
    for i, day in enumerate(days):
        if weekday_stress[i]:
            avg = sum(weekday_stress[i]) / len(weekday_stress[i])
            bar_len = int(avg / 100 * 15)
            bar = "█" * bar_len
            level = "Low" if avg < 30 else "Med" if avg < 50 else "High"
            print(f"   {day}: {bar} {avg:.0f} ({level})")

    # Monthly patterns
    print("\n📆 MONTHLY PATTERNS (This Year)")
    print("─" * 44)

    current_year = date.today().year
    monthly_steps = {i: [] for i in range(1, 13)}

    for stat in stats_data:
        date_str = stat.get('_date', '')
        if date_str and date_str.startswith(str(current_year)):
            try:
                d = datetime.strptime(date_str, '%Y-%m-%d')
                month = d.month
                steps = stat.get('totalSteps', 0)
                if steps:
                    monthly_steps[month].append(steps)
            except Exception:
                pass

    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    max_monthly = max(sum(v)/len(v) if v else 0 for v in monthly_steps.values()) or 1

    print("\n   Avg steps by month:")
    for i, month in enumerate(months, 1):
        if monthly_steps[i]:
            avg = sum(monthly_steps[i]) / len(monthly_steps[i])
            bar_len = int(avg / max_monthly * 12)
            bar = "█" * bar_len
            print(f"   {month}: {bar} {avg:,.0f}")

    # Best/Worst days
    print("\n🏆 BEST & WORST DAYS")
    print("─" * 44)

    # Filter out days with no steps
    valid_days = [s for s in stats_data if (s.get('totalSteps') or 0) > 0]
    sorted_by_steps = sorted(valid_days, key=lambda x: x.get('totalSteps', 0) or 0, reverse=True)
    if sorted_by_steps:
        best = sorted_by_steps[0]
        worst = sorted_by_steps[-1]
        print(f"   Best day:  {best.get('_date')} - {best.get('totalSteps', 0):,} steps")
        print(f"   Worst day: {worst.get('_date')} - {worst.get('totalSteps', 0):,} steps")

    print("\n" + "═" * 44)


def cmd_weight_trend():
    """ASCII visualization of weight trend."""
    data_dir = get_data_dir()

    print("╔════════════════════════════════════════════╗")
    print("║           WEIGHT TREND VISUALIZATION       ║")
    print("╚════════════════════════════════════════════╝\n")

    weight_file = data_dir / "weight.json"
    if not weight_file.exists():
        print("No weight data found. Run `garmin export` first.")
        return

    with open(weight_file) as f:
        weight_data = json.load(f)

    summaries = weight_data.get('dailyWeightSummaries', [])
    if not summaries:
        print("No weight entries found.")
        return

    # Sort by date
    summaries = sorted(summaries, key=lambda x: x.get('summaryDate', ''))

    # Get weights
    weights = [(s.get('summaryDate', ''), s.get('maxWeight', 0) / 1000) for s in summaries]
    weights = [(d, w) for d, w in weights if w > 0]

    if not weights:
        print("No valid weight entries.")
        return

    # Stats
    current = weights[-1][1]
    first = weights[0][1]
    change = current - first
    min_w = min(w for _, w in weights)
    max_w = max(w for _, w in weights)

    print(f"📊 OVERVIEW ({len(weights)} measurements)")
    print("─" * 44)
    print(f"   First: {first:.1f} kg ({weights[0][0]})")
    print(f"   Now:   {current:.1f} kg ({weights[-1][0]})")
    print(f"   Change: {'+' if change >= 0 else ''}{change:.1f} kg")
    print(f"   Range:  {min_w:.1f} - {max_w:.1f} kg")

    # ASCII chart - last 20 measurements
    print("\n📈 RECENT TREND (last 20 weigh-ins)")
    print("─" * 44)

    recent = weights[-20:]
    r_min = min(w for _, w in recent)
    r_max = max(w for _, w in recent)
    r_range = r_max - r_min if r_max > r_min else 1

    chart_height = 8
    chart_width = len(recent)

    # Build chart rows (top to bottom)
    for row in range(chart_height, -1, -1):
        line = "   "
        if row == chart_height:
            line += f"{r_max:.0f}│"
        elif row == 0:
            line += f"{r_min:.0f}│"
        else:
            line += "   │"

        for _, w in recent:
            # Calculate how many rows this weight fills
            fill_level = (w - r_min) / r_range * chart_height
            if fill_level >= row:
                line += "█"
            else:
                line += " "

        print(line)

    # X-axis
    print("   " + "   └" + "─" * chart_width)

    # Date labels
    if recent:
        first_date = recent[0][0][-5:]  # MM-DD
        last_date = recent[-1][0][-5:]
        print(f"     {first_date}" + " " * (chart_width - 10) + f"{last_date}")

    # Goals
    goals_file = data_dir / "goals.json"
    if goals_file.exists():
        with open(goals_file) as f:
            goals = json.load(f)
        target = goals.get('weight_kg', 0)
        if target:
            diff = current - target
            print(f"\n🎯 GOAL: {target} kg ({'+' if diff >= 0 else ''}{diff:.1f} kg to go)")

    print("\n" + "═" * 44)


def main():
    if len(sys.argv) < 2:
        print("Usage: garmin <command>")
        print("\nCommands:")
        print("  test           Test API connection")
        print("  today          Today's stats")
        print("  goals          Goal progress")
        print("  weight         Weight trend (30 days)")
        print("  weight-trend   ASCII weight visualization")
        print("  sleep          Last night's sleep")
        print("  sleep-report   Sleep analysis with correlations")
        print("  patterns       Weekly/seasonal patterns")
        print("  activities     Recent workouts")
        print("  export         Full data export")
        sys.exit(1)

    cmd = sys.argv[1]

    commands = {
        'test': cmd_test,
        'today': cmd_today,
        'weight': cmd_weight,
        'weight-trend': cmd_weight_trend,
        'sleep': cmd_sleep,
        'sleep-report': cmd_sleep_report,
        'patterns': cmd_patterns,
        'activities': cmd_activities,
        'goals': cmd_goals,
        'export': cmd_export,
    }

    if cmd not in commands:
        print(f"Unknown command: {cmd}")
        print(f"Available: {', '.join(commands.keys())}")
        sys.exit(1)

    commands[cmd]()


if __name__ == '__main__':
    main()
