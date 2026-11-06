"""
`amms <command> [args]`: dispatches to amms.core.tools.<module>.main

Only handles dispatching with each tool having its own argparse
So `amms check-snap -h` and `python -m amms.core.tools.check_snap -h` do the same
Currently registry backed commands (e.g. scan, submit, init) are frozen until there are more test runs
"""

from __future__ import annotations

import importlib
import sys

COMMANDS = {
    "check-snap": "check_snap",
    "ic-sanity": "ic_sanity",
    "plot-sfh": "plot_sfh",
    "run-summary": "run_summary",
}


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in COMMANDS:
        print(f"usage: amms {{{','.join(COMMANDS)}}} [args]", file=sys.stderr)
        sys.exit(0 if argv[:1] in (["-h"], ["--help"]) else 2)
    # Keep heavy package loads only for necessary commands
    importlib.import_module(f"amms.core.tools.{COMMANDS[argv[0]]}").main(argv[1:])
