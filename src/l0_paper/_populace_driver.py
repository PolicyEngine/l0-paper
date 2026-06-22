"""Load Populace's production fiscal-refresh build driver as an importable module.

The Populace dataset that PolicyEngine ships is built by the script
``populace/tools/build_us_fiscal_refresh_release.py``. That script is not packaged
as an importable module, but its pre-calibration logic (loading the base frame,
resolving Ledger facts into a target registry, and materializing the calibration
target measures onto the frame) is exactly the "build the dataset except the
calibration step" boundary this paper's experiments need.

Rather than re-implement that PolicyEngine-US materialization, we import the
driver from the sibling ``populace`` checkout and reuse its functions. The path is
discovered from the installed ``populace.build`` package (so it follows the
``[tool.uv.sources]`` editable install in ``pyproject.toml``), with an environment
override for non-standard layouts.

Coupling note: this depends on private (underscore) functions in the driver
script. The intended follow-up is to upstream a public
``populace.build.us.build_precalibration(...)`` API and drop this shim.
"""

from __future__ import annotations

import importlib.util
import os
from functools import lru_cache
from pathlib import Path
from types import ModuleType

#: Driver script path, relative to the Populace repository root.
_DRIVER_RELPATH = Path("tools") / "build_us_fiscal_refresh_release.py"

#: Environment variable that overrides Populace repo-root discovery.
_REPO_ENV = "L0_PAPER_POPULACE_REPO"


def _populace_repo_root() -> Path:
    """Locate the Populace repository root that backs the installed packages."""
    override = os.environ.get(_REPO_ENV)
    if override:
        root = Path(override).expanduser().resolve()
        if not (root / _DRIVER_RELPATH).is_file():
            raise FileNotFoundError(
                f"{_REPO_ENV}={root} does not contain {_DRIVER_RELPATH}."
            )
        return root

    import populace.build as _build  # imported lazily so import errors are clear

    # .../populace/packages/populace-build/src/populace/build/__init__.py
    here = Path(_build.__file__).resolve()
    for parent in here.parents:
        if (parent / _DRIVER_RELPATH).is_file():
            return parent
    raise FileNotFoundError(
        "Could not locate the Populace repository root from "
        f"{here}. Set {_REPO_ENV} to the populace checkout that holds "
        f"{_DRIVER_RELPATH}."
    )


@lru_cache(maxsize=1)
def load_driver() -> ModuleType:
    """Import and return the Populace fiscal-refresh build driver module.

    The module is loaded once and cached. Importing it runs the driver's
    module-level imports (numpy, pandas, populace.*) but not ``main()``.
    """
    driver_path = _populace_repo_root() / _DRIVER_RELPATH
    spec = importlib.util.spec_from_file_location(
        "l0_paper._populace_fiscal_refresh_driver", driver_path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not create a module spec for {driver_path}.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
