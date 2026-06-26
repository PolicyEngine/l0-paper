"""Enable ``python -m l0_paper.cli <command> [args...]``."""

from __future__ import annotations

import sys

from l0_paper.cli import main

if __name__ == "__main__":
    sys.exit(main())
