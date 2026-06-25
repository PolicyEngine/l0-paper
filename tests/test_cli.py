"""The ``l0`` CLI is wired up and runs the pipeline end to end.

Invokes the real entry point (``python -m l0_paper.cli``) in a subprocess so the
dispatcher, subcommand routing, and packaging are exercised the way a user runs it.
"""

from __future__ import annotations

import subprocess
import sys


def test_l0_help_lists_commands():
    proc = subprocess.run(
        [sys.executable, "-m", "l0_paper.cli", "--help"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    for command in ("sweep", "poc", "figures", "demo"):
        assert command in proc.stdout


def test_l0_demo_cli_runs_end_to_end(tmp_path):
    out = tmp_path / "demo"
    proc = subprocess.run(
        [sys.executable, "-m", "l0_paper.cli", "demo", "--no-figures", "--epochs", "30", "--out", str(out)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert (out / "metrics_long.csv").is_file()
    assert (out / "target_diagnostics_long.csv").is_file()
    assert (out / "objective_summary.csv").is_file()
