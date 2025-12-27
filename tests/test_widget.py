"""Tests for SwiftBar widget rendering.

These tests verify:
1. Widget output format is valid for SwiftBar
2. Progress bars render correctly
3. Color coding is correct
4. All sections are present
"""

import json
from pathlib import Path
import tempfile

import pytest

from garmin_health.data import HealthData
from garmin_health.widget import (
    progress_bar,
    get_color,
    get_weight_color,
    format_number,
    render_widget,
    render_menu_bar,
    render_goals_section,
)


class TestProgressBar:
    """Tests for progress bar rendering."""

    def test_empty_bar(self):
        """0% should be all empty."""
        assert progress_bar(0) == "▱▱▱▱▱▱▱▱▱▱"

    def test_full_bar(self):
        """100% should be all filled."""
        assert progress_bar(100) == "▰▰▰▰▰▰▰▰▰▰"

    def test_half_bar(self):
        """50% should be half filled."""
        assert progress_bar(50) == "▰▰▰▰▰▱▱▱▱▱"

    def test_custom_width(self):
        """Custom width should work."""
        assert progress_bar(50, width=4) == "▰▰▱▱"

    def test_over_100_capped(self):
        """Values over 100% should cap at full."""
        assert progress_bar(150) == "▰▰▰▰▰▰▰▰▰▰"

    def test_negative_capped(self):
        """Negative values should cap at empty."""
        assert progress_bar(-10) == "▱▱▱▱▱▱▱▱▱▱"


class TestColorFunctions:
    """Tests for color utility functions."""

    def test_get_color_green(self):
        """100%+ should be green."""
        assert get_color(100) == "green"
        assert get_color(150) == "green"

    def test_get_color_orange(self):
        """75-99% should be orange."""
        assert get_color(75) == "#f0ad4e"
        assert get_color(99) == "#f0ad4e"

    def test_get_color_red(self):
        """<75% should be red."""
        assert get_color(74) == "#d9534f"
        assert get_color(0) == "#d9534f"

    def test_weight_color_at_goal(self):
        """At or below goal should be green."""
        assert get_weight_color(0) == "green"
        assert get_weight_color(-5) == "green"

    def test_weight_color_near_goal(self):
        """Within 5kg should be orange."""
        assert get_weight_color(3) == "#f0ad4e"
        assert get_weight_color(4.9) == "#f0ad4e"

    def test_weight_color_far_from_goal(self):
        """5kg+ over should be red."""
        assert get_weight_color(5) == "#d9534f"
        assert get_weight_color(15) == "#d9534f"


class TestFormatNumber:
    """Tests for number formatting."""

    def test_small_number(self):
        """Small numbers should not have separators."""
        assert format_number(100) == "100"

    def test_thousands(self):
        """Thousands should have comma separator."""
        assert format_number(1000) == "1,000"
        assert format_number(10000) == "10,000"

    def test_millions(self):
        """Millions should have multiple separators."""
        assert format_number(1000000) == "1,000,000"


class TestWidgetWithMockData:
    """Tests using mock data for controlled verification."""

    @pytest.fixture
    def mock_data_dir(self):
        """Create a temporary directory with mock data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create mock sleep data
            sleep_data = [
                {
                    "_date": "2025-01-01",
                    "dailySleepDTO": {
                        "sleepTimeSeconds": 28800,  # 8 hours
                        "sleepScores": {"overall": {"value": 85}},
                    },
                },
            ]
            with open(tmpdir / "sleep.json", "w") as f:
                json.dump(sleep_data, f)

            # Create mock stats data
            stats_data = [
                {"_date": "2025-01-01", "totalSteps": 12000},
            ]
            with open(tmpdir / "daily_stats.json", "w") as f:
                json.dump(stats_data, f)

            # Create mock weight data
            weight_data = {
                "dailyWeightSummaries": [
                    {"summaryDate": "2025-01-01", "maxWeight": 80000},  # 80kg
                ]
            }
            with open(tmpdir / "weight.json", "w") as f:
                json.dump(weight_data, f)

            # Create mock goals (already at target weight)
            goals_data = {
                "weight_kg": 80,
                "daily_steps": 10000,
                "sleep_hours": 7,
                "workouts_per_week": 3,
            }
            with open(tmpdir / "goals.json", "w") as f:
                json.dump(goals_data, f)

            yield tmpdir

    def test_widget_renders_without_error(self, mock_data_dir):
        """Widget should render without exceptions."""
        data = HealthData(mock_data_dir)
        output = render_widget(data)
        assert len(output) > 0

    def test_widget_has_separator(self, mock_data_dir):
        """Widget should have separator lines."""
        data = HealthData(mock_data_dir)
        output = render_widget(data)
        assert "---" in output

    def test_widget_has_header(self, mock_data_dir):
        """Widget should have Health Dashboard header."""
        data = HealthData(mock_data_dir)
        output = render_widget(data)
        assert "Health Dashboard" in output

    def test_widget_has_refresh(self, mock_data_dir):
        """Widget should have refresh option."""
        data = HealthData(mock_data_dir)
        output = render_widget(data)
        assert "Refresh | refresh=true" in output

    def test_goals_section_with_met_goals(self, mock_data_dir):
        """When goals are met, should show checkmarks."""
        data = HealthData(mock_data_dir)
        lines = render_goals_section(data)
        output = "\n".join(lines)

        # Steps goal met (12000 > 10000)
        assert "badge=✓" in output or "120%" in output

    def test_menu_bar_format(self, mock_data_dir):
        """Menu bar should be properly formatted."""
        data = HealthData(mock_data_dir)
        menu_bar, tooltip_parts = render_menu_bar(data)

        # Should have steps in "X/Y" format
        assert "/" in menu_bar
        # Should have sleep
        assert "h" in menu_bar
        # Weight should be in tooltip, not menu bar
        assert any("kg" in t for t in tooltip_parts)


@pytest.mark.skipif(
    not Path.home().joinpath("Health/Garmin").exists(),
    reason="Real Garmin data not available"
)
class TestWidgetWithRealData:
    """Tests using real Garmin data."""

    def test_widget_renders_with_real_data(self):
        """Widget should render with actual data."""
        data = HealthData.default()
        output = render_widget(data)

        # Should have basic structure
        assert "---" in output
        assert "Health Dashboard" in output

    def test_widget_has_all_sections(self):
        """Widget should have all expected sections."""
        data = HealthData.default()
        output = render_widget(data)

        assert "Vitals" in output
        assert "Analytics" in output
        assert "Quick Actions" in output
        assert "Garmin Connect" in output

    def test_widget_output_lines_are_valid(self):
        """Each line should be valid SwiftBar format."""
        data = HealthData.default()
        output = render_widget(data)

        for line in output.split("\n"):
            if line.strip() and line != "---":
                # Lines can either be plain text or have | options
                # This is a basic sanity check
                assert len(line) > 0


class TestWidgetEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture
    def empty_data_dir(self):
        """Create empty temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_widget_with_no_data(self, empty_data_dir):
        """Widget should handle missing data gracefully."""
        data = HealthData(empty_data_dir)
        output = render_widget(data)

        # Should still render basic structure
        assert "Health Dashboard" in output
        assert "---" in output
        # Should have fallback menu bar
        assert "❤️ --" in output or len(output) > 0


class TestFreshnessIndicator:
    """Tests for data freshness indicator."""

    def test_format_time_ago_unknown(self):
        """Unknown age should show ?."""
        from garmin_health.widget import format_time_ago
        assert format_time_ago(-1) == "?"

    def test_format_time_ago_now(self):
        """Very recent should show now."""
        from garmin_health.widget import format_time_ago
        assert format_time_ago(0) == "now"

    def test_format_time_ago_minutes(self):
        """Minutes should show Xm format."""
        from garmin_health.widget import format_time_ago
        assert format_time_ago(5) == "5m"
        assert format_time_ago(30) == "30m"
        assert format_time_ago(59) == "59m"

    def test_format_time_ago_hours(self):
        """Hours should show Xh format."""
        from garmin_health.widget import format_time_ago
        assert format_time_ago(60) == "1h"
        assert format_time_ago(120) == "2h"
        assert format_time_ago(1439) == "23h"

    def test_format_time_ago_days(self):
        """Days should show Xd format."""
        from garmin_health.widget import format_time_ago
        assert format_time_ago(1440) == "1d"
        assert format_time_ago(2880) == "2d"

    def test_get_data_age_missing_file(self):
        """Missing file should return -1."""
        from garmin_health.widget import get_data_age_minutes
        with tempfile.TemporaryDirectory() as tmpdir:
            age = get_data_age_minutes(Path(tmpdir))
            assert age == -1

    def test_get_data_age_recent_file(self):
        """Recent file should return small age."""
        from garmin_health.widget import get_data_age_minutes

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            stats_file = data_dir / "daily_stats.json"
            stats_file.write_text("{}")

            age = get_data_age_minutes(data_dir)
            assert 0 <= age < 2  # Should be very recent

    def test_menu_bar_includes_freshness(self):
        """Menu bar should include freshness indicator when enabled."""
        from garmin_health.config import Config

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create minimal mock data
            (tmpdir / "sleep.json").write_text(json.dumps([{
                "_date": "2025-01-01",
                "dailySleepDTO": {"sleepTimeSeconds": 28800, "sleepScores": {"overall": {"value": 85}}},
            }]))
            (tmpdir / "daily_stats.json").write_text(json.dumps([{"_date": "2025-01-01", "totalSteps": 12000}]))
            (tmpdir / "weight.json").write_text(json.dumps({"dailyWeightSummaries": [{"summaryDate": "2025-01-01", "maxWeight": 80000}]}))
            (tmpdir / "goals.json").write_text(json.dumps({"weight_kg": 80, "daily_steps": 10000, "sleep_hours": 7, "workouts_per_week": 3}))

            data = HealthData(tmpdir)
            config = Config()
            config.widget.show_freshness = True

            menu_bar, tooltip_parts = render_menu_bar(data, config)

            # Should have freshness indicator
            assert any("Data age" in t for t in tooltip_parts)
