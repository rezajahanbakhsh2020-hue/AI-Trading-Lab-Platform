"""Host application presentation-shell checks.

The web UI is a Project 2 host surface. These tests assert the shell exists
and that the disconnected snapshot contract does not fabricate trading data.
"""

import os
import re


WEB_ROOT = os.path.join("web")


def test_host_application_shell_exists():
    assert os.path.exists(os.path.join(WEB_ROOT, "index.html"))
    assert os.path.exists(os.path.join(WEB_ROOT, "package.json"))
    assert os.path.exists(os.path.join(WEB_ROOT, "src", "ui", "App.tsx"))
    assert os.path.exists(os.path.join(WEB_ROOT, "src", "ui", "HostPage.tsx"))
    assert os.path.exists(os.path.join(WEB_ROOT, "src", "architecture", "hostView.ts"))


def test_host_snapshot_does_not_fabricate_trading_data():
    path = os.path.join(WEB_ROOT, "src", "architecture", "hostView.ts")
    with open(path, encoding="utf-8") as handle:
        source = handle.read()

    assert "No Project 1 data connected yet." in source
    assert "Project1IntegrationPort" in source
    assert "connected: false" in source
    assert "quote: null" in source
    assert "action: null" in source
    assert "takeProfits: []" in source
    assert "activity: []" in source
    assert not re.search(r"quote:\s*[0-9]", source)


def test_host_pages_are_presentation_destinations():
    path = os.path.join(WEB_ROOT, "src", "architecture", "hostView.ts")
    with open(path, encoding="utf-8") as handle:
        source = handle.read()

    for page in (
        "Dashboard",
        "Market",
        "Strategy",
        "Backtest",
        "Signals",
        "Performance",
        "Risk",
        "Monitoring",
        "Providers",
        "Logs",
        "Settings",
    ):
        assert page in source
