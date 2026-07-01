"""The ``l0`` command-line interface.

The experiment drivers ship inside the package (so ``pip install l0-paper`` gives a
runnable ``l0`` command) and each keeps its own argparse interface. This dispatcher
routes ``l0 <command> <args...>`` to the matching driver's ``main()``; commands are
imported lazily so e.g. ``l0 sweep`` does not pull in matplotlib and ``l0 build-*``
does not pull in the heavy real-data extras unless used.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Sequence

#: command name -> (module, one-line help). Module must expose ``main()``.
_COMMANDS: dict[str, tuple[str, str]] = {
    "sweep": (
        "l0_paper.cli.sweep",
        "Budget x seed sweep of the calibration conditions.",
    ),
    "poc": (
        "l0_paper.cli.poc",
        "Single-run proof of concept; builds/reuses the precalibration cache.",
    ),
    "figures": (
        "l0_paper.cli.figures",
        "Render figures + LaTeX tables from a sweep's metrics_long.csv.",
    ),
    "summarize": (
        "l0_paper.cli.summarize",
        "Readable summaries (CSV/Markdown) from a run manifest.",
    ),
    "merge-l2": (
        "l0_paper.cli.merge_l2",
        "Merge single-l2 sweep runs into one comparison directory.",
    ),
    "merge-runs": (
        "l0_paper.cli.merge_runs",
        "Merge compatible sweep shard directories into one run.",
    ),
    "fixed-lambda": (
        "l0_paper.cli.fixed_lambda",
        "Fixed-penalty L0 pilot matched to its achieved retained count.",
    ),
    "paper": ("l0_paper.cli.paper", "Run the current-paper reproduction workflow."),
    "build-candidate": (
        "l0_paper.cli.build_candidate",
        "Build the candidate-universe precalibration frame.",
    ),
    "build-targets": (
        "l0_paper.cli.build_targets",
        "Build the calibration target bundle from arch-data.",
    ),
    "demo": (
        "l0_paper.cli.demo",
        "Run the whole pipeline end-to-end on the toy frame (no real data).",
    ),
}


def _usage() -> str:
    width = max(len(name) for name in _COMMANDS)
    lines = ["usage: l0 <command> [args...]", "", "commands:"]
    lines += [f"  {name:<{width}}  {help_}" for name, (_, help_) in _COMMANDS.items()]
    lines += ["", "Run 'l0 <command> --help' for a command's own options."]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Dispatch ``l0 <command> [args...]`` to the matching driver."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(_usage())
        return 0
    command, rest = argv[0], argv[1:]
    if command not in _COMMANDS:
        print(f"l0: unknown command {command!r}\n", file=sys.stderr)
        print(_usage(), file=sys.stderr)
        return 2
    module = importlib.import_module(_COMMANDS[command][0])
    # Each driver parses sys.argv; present it the subcommand's own args.
    saved = sys.argv
    sys.argv = [f"l0 {command}", *rest]
    try:
        result = module.main()
    finally:
        sys.argv = saved
    return result if isinstance(result, int) else 0
