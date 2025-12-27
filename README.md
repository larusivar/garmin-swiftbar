# garmin-swiftbar

SwiftBar widget + automation for Garmin Connect health data on macOS.

## Features

- **Menu bar widget** showing steps, sleep, and data freshness
- **Auto-sync** from Garmin Connect (watch → cloud → local)
- **Daily summary notifications** at midnight with markdown logging
- **Analytics commands**: sleep report, weight trends, weekly patterns
- **Goal tracking**: visual progress bars for steps, sleep, weight, workouts
- **Configurable**: waking hours, sync thresholds, notification sounds

## Requirements

- macOS (uses Keychain for credentials)
- [SwiftBar](https://github.com/swiftbar/SwiftBar)
- Python 3.11+
- Garmin Connect account with syncing device

## Quick Start

1. Clone and set up virtual environment:
   ```bash
   git clone https://github.com/larusivar/garmin-swiftbar.git
   cd garmin-swiftbar
   python3 -m venv .venv
   .venv/bin/pip install garminconnect pydantic
   ```

2. Store Garmin credentials in Keychain:
   ```bash
   security add-generic-password -a "garmin" -s "garmin-email" -w "your@email.com"
   security add-generic-password -a "garmin" -s "garmin-password" -w "your-password"
   ```

3. Create data directory and export initial data:
   ```bash
   mkdir -p ~/Health/Garmin
   .venv/bin/python scripts/garmin-client.py export
   ```

4. Set up goals:
   ```bash
   cat > ~/Health/Garmin/goals.json << 'EOF'
   {
     "weight_kg": 80,
     "daily_steps": 10000,
     "sleep_hours": 7,
     "workouts_per_week": 3
   }
   EOF
   ```

5. Set up SwiftBar plugin:
   ```bash
   # Install SwiftBar from https://github.com/swiftbar/SwiftBar/releases
   mkdir -p ~/Library/Application\ Support/SwiftBar/Plugins
   ln -s $(pwd)/scripts/garmin-health.30m.py ~/Library/Application\ Support/SwiftBar/Plugins/
   chmod 755 scripts/garmin-health.30m.py
   open -a SwiftBar
   ```

## Commands

```bash
# Daily commands
.venv/bin/python scripts/garmin-client.py goals         # Progress vs targets
.venv/bin/python scripts/garmin-client.py today         # Today's stats

# Analytics
.venv/bin/python scripts/garmin-client.py sleep-report  # Sleep analysis
.venv/bin/python scripts/garmin-client.py patterns      # Weekly patterns
.venv/bin/python scripts/garmin-client.py weight-trend  # Weight chart

# Data
.venv/bin/python scripts/garmin-client.py weight        # Recent weigh-ins
.venv/bin/python scripts/garmin-client.py sleep         # Last night's sleep
.venv/bin/python scripts/garmin-client.py activities    # Recent workouts

# System
.venv/bin/python scripts/garmin-client.py test          # Test connection
.venv/bin/python scripts/garmin-client.py export        # Full data export
```

## Configuration

Create `~/.config/garmin-health/config.json`:

```json
{
  "sync": {
    "interval_minutes": 10,
    "change_threshold_steps": 100,
    "waking_hours_start": 7,
    "waking_hours_end": 23
  },
  "notifications": {
    "daily_summary_enabled": true,
    "daily_summary_time": "00:00",
    "sound": "Glass",
    "log_to_markdown": true,
    "log_file": "daily-summaries.md"
  },
  "widget": {
    "show_freshness": true,
    "freshness_warning_minutes": 30,
    "refresh_method": "url_scheme"
  }
}
```

## Automation (optional)

### Background sync daemon

Syncs every 10 minutes during waking hours:

```bash
# Create launchd plist
cat > ~/Library/LaunchAgents/com.user.garmin-sync.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.garmin-sync</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/garmin-swiftbar/.venv/bin/python3</string>
        <string>/path/to/garmin-swiftbar/scripts/garmin-sync-daemon.py</string>
    </array>
    <key>StartInterval</key>
    <integer>600</integer>
</dict>
</plist>
EOF

launchctl load ~/Library/LaunchAgents/com.user.garmin-sync.plist
```

### Daily summary notification

Sends notification at midnight:

```bash
# Create launchd plist
cat > ~/Library/LaunchAgents/com.user.garmin-daily.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.garmin-daily</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/garmin-swiftbar/.venv/bin/python3</string>
        <string>/path/to/garmin-swiftbar/scripts/daily-summary.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>0</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
</dict>
</plist>
EOF

launchctl load ~/Library/LaunchAgents/com.user.garmin-daily.plist
```

## Architecture

```
garmin-swiftbar/
├── src/garmin_health/
│   ├── core.py       # Garmin API client, keychain, data operations
│   ├── config.py     # Configuration management
│   ├── data.py       # Data access layer with caching
│   ├── models.py     # Pydantic models for health data
│   └── widget.py     # SwiftBar widget rendering
├── scripts/
│   ├── garmin-health.30m.py   # SwiftBar menu bar plugin
│   ├── garmin-client.py       # CLI tool
│   ├── garmin-sync-daemon.py  # Background sync
│   └── daily-summary.py       # Daily notifications
└── tests/
    └── ...
```

## Data Storage

All data is stored as JSON in `~/Health/Garmin/`:

| File | Description |
|------|-------------|
| `daily_stats.json` | Steps, calories, HR (6 years) |
| `sleep.json` | Sleep stages & duration (6 years) |
| `weight.json` | Scale measurements (5 years) |
| `activities.json` | All workouts |
| `body_battery.json` | Energy levels |
| `stress.json` | Stress scores |
| `goals.json` | Your targets |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `garminconnect not found` | `.venv/bin/pip install garminconnect` |
| `Credentials not in Keychain` | See Quick Start step 2 |
| `Token expired` | `trash ~/.cache/garmin/ && python scripts/garmin-client.py test` (or `rm -rf` if no `trash`) |
| `SwiftBar not updating` | `killall SwiftBar; open -a SwiftBar` |

## License

MIT
