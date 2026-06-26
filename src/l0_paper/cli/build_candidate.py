#!/usr/bin/env python
"""Generate-big candidate universe via Populace's full US build plan (heavy).

The proof-of-concept (``l0 poc``) uses the published HuggingFace frame as the
candidate universe. This script is the code path for the *true* pre-prune
candidate universe: Populace's "generate big, then prune" imputation pipeline,
which grows the CPS ASEC well beyond the survey before calibration reduces it.

It is intentionally NOT run by default. At production scale the build needs the
donor source data (PUF, SCF, SIPP, CPS ORG, MEPS-IC, ACS) and roughly 48 GB of
RAM (see ``populace/SYSTEM_REQUIREMENTS.md``).

Pipeline (15 stages, from ``populace.build.us_runtime.US_STAGE_NAMES``):

    asec_load -> unit_assignment -> derive_cps_carried -> puf_tax_detail
    -> scf_wealth -> sipp_tips -> org_wages -> meps_esi_premiums
    -> prior_year_income -> mortgage_conversion -> acs_rent -> vehicle_assets
    -> entity_placement -> aca_marketplace_inputs -> export

``populace.build.us_runtime.us_plan`` assembles the ``StagePlan`` but requires one
``transform(frame) -> Frame`` implementation per stage to be *injected*. The
current Populace checkout does not expose a public factory for the production
implementations (the release tool recalibrates an existing frame instead of
running this plan), so :func:`build_stage_implementations` is the single
extension point that must be supplied. The known source-stage machinery
(``us_source_operation_handlers`` + ``run_source_stage`` over
``US_SOURCE_MANIFEST``) is imported here to point at the real building blocks.

Once the imputed candidate frame exists, freeze it exactly like the POC by
passing it to the pre-calibration materialization.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from pathlib import Path

from populace.build.us_runtime import (  # noqa: F401 -- re-exported as the real building blocks
    US_SOURCE_MANIFEST,
    US_STAGE_NAMES,
    us_plan,
    us_source_operation_handlers,
)
from populace.frame import Frame


def build_stage_implementations() -> Mapping[str, Callable[[Frame], Frame]]:
    """Return one ``transform(frame) -> Frame`` per stage in ``US_STAGE_NAMES``.

    Not yet available: Populace does not export the production stage
    implementations, so this must be filled in (or replaced by a public
    ``populace.build.us`` factory once one exists). The source/donor stages run
    through ``run_source_stage`` with ``us_source_operation_handlers()`` over the
    stages declared in ``US_SOURCE_MANIFEST``; the derive/placement/export stages
    are pandas transforms on the frame.
    """
    raise NotImplementedError(
        "Production per-stage implementations are not exposed by the current "
        "Populace checkout. Supply a transform for each of "
        f"{list(US_STAGE_NAMES)} (source stages via run_source_stage + "
        "us_source_operation_handlers over US_SOURCE_MANIFEST), or wait for a "
        "public populace.build.us implementation factory, then run this script."
    )


def load_seed_frame() -> Frame:
    """Load the CPS ASEC seed frame the plan's first stage expects.

    The ``asec_load`` stage reads the raw CPS ASEC. Wire this to
    ``populace.data`` loaders / the source manifest once the implementations are
    available.
    """
    raise NotImplementedError(
        "Seed-frame loading is not wired yet; provide the CPS ASEC seed frame "
        "consumed by the 'asec_load' stage."
    )


def build_full_candidate_frame() -> Frame:
    """Run the full US build plan to produce the pre-prune candidate frame."""
    plan = us_plan(build_stage_implementations())
    seed_frame = load_seed_frame()
    candidate_frame, _stage_records = plan.run(seed_frame, log=print)
    return candidate_frame


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger-facts", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--confirm-heavy", action="store_true",
                        help="Required acknowledgement of the ~48 GB / donor-data build.")
    args = parser.parse_args()
    if not args.confirm_heavy:
        parser.error(
            "Refusing to start the generate-big build without --confirm-heavy "
            "(needs donor source data and ~48 GB RAM; see SYSTEM_REQUIREMENTS.md)."
        )

    # Produce the candidate universe, then freeze it through the same
    # pre-calibration materialization the POC uses. The materialization reuses
    # the production driver (income_tax etc. via PolicyEngine-US), so the candidate
    # frame must be written to an .h5 the driver's _load_frame can read first; see
    # build_precalibration_dataset(base_h5=...) for that hand-off.
    candidate_frame = build_full_candidate_frame()
    raise NotImplementedError(
        "Candidate frame built; persist it to an .h5 and pass it to "
        "build_precalibration_dataset(base_h5=...) to freeze the pre-calibration "
        f"dataset into {args.out} using {args.ledger_facts}. "
        f"(candidate households: {candidate_frame.n('household')})"
    )


if __name__ == "__main__":
    main()
