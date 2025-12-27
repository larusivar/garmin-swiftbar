#!/usr/bin/env python3
"""SwiftBar plugin for Garmin health data.

Refreshes every 30 minutes (per filename convention).
Place in SwiftBar plugins folder or symlink there.

SwiftBar: https://github.com/swiftbar/SwiftBar
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from garmin_health.data import HealthData
from garmin_health.widget import render_widget


def main():
    """Render the SwiftBar widget."""
    try:
        data = HealthData.default()
        print(render_widget(data))
    except Exception as e:
        # Show error in menu bar if something goes wrong
        print("⚠️ Error | color=red")
        print("---")
        print(f"Error: {e} | color=red")


if __name__ == "__main__":
    main()
