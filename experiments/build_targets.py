#!/usr/bin/env python
"""Reproducibly build the complete L0 calibration-target bundle (consumer_facts.jsonl).

This assembles a complete multi-vintage *source-fact feed* -- NOT a "mixed-vintage
target set". That distinction is the whole reason the script looks the way it does,
so it's worth stating up front.

Source vintage vs. target period (why the feed is multi-vintage on purpose)
---------------------------------------------------------------------------
arch-data is a source-of-truth fact store: by design it records every fact at its
*true* native vintage (IRS SOI tax year 2023, JCT FY2024 estimates, CMS ACA 2022
enrollment, ...) and never relabels them. Resolving those multi-vintage facts to a
single calibration *target period* is a separate, downstream modeling step that
**Populace** owns -- arch-data's own contract says so:

    "Arch stores source-backed facts and target inputs. Populace owns the active
     calibration profile, source reconciliation, aging, and model variable mapping."
     -- arch-data/docs/pe-calibration-targets.md

Concretely, ``compile_us_fiscal_target_registry(facts, target_period=2024)`` ages
every fact to one period: for each target *shape* it strips the source period from
the identity key and keeps the latest source vintage <= the target period
(``_dynamic_us_fiscal_target_references``). Empirically the compiled registry is
single-period -- every target comes out at 2024 regardless of its source's vintage.

So a multi-vintage ``consumer_facts.jsonl`` is correct and intended: it is the
*input feed*, and Populace unifies the periods. This script does no aging or
relabeling itself; its only job is to make that feed **complete**.

Why a single ``arch build-bundle`` can't produce the complete feed
------------------------------------------------------------------
``arch build-bundle`` takes a *single* ``--year`` and looks up each source's
artifact at that literal year (``arch/source_package.py:_year_mapping`` -- exact
match only, no "latest <= year"). Its default-source path then *intentionally*
drops sources lacking that year ("merge **available** source-package suites for a
year" -- ``bundle.py:_resolve_bundle_sources``, skip unless ``explicit``). Because
the sources are pinned to *different* years, **no single ``--year`` captures them
all**: ``--year 2023`` skips ``jct-tax-expenditures-2024`` (which the production
registry compile *requires*) plus the census ACS age / SNAP-by-district and CMS ACA
sources; ``--year 2024`` would instead skip the SOI tables (latest tax year 2023).
Passing all sources ``explicit=True`` bypasses the skip but then the off-year ones
*fail* the exact-year artifact lookup. Hence: build per-vintage and merge.

(The one-command alternative would be an arch-data change -- have
``_resolve_bundle_sources`` build each source at its latest-available vintage <=
the target instead of skipping. That is pure feed-assembly convenience: it would
not change any target's period, since Populace already unifies them, and would make
this script unnecessary.)

What this script does
---------------------
  1. a **base bundle** -- the default sources at ``--year`` (2023, the latest SOI
     tax year), either reused from an existing run (``--base``) or rebuilt here
     (``--build-base``); and
  2. the **off-year sources** below, each built at its own pinned year via
     ``arch build-suite`` and concatenated in. All their artifacts are local in
     arch-data's ``db/`` package, so this step needs no network or R2 auth.

The merged ``consumer_facts.jsonl`` is written into this repo (default
``data/targets/``) alongside a provenance manifest, so the feed any experiment
consumes is regenerable from one command.

Example
-------
    # Reuse an existing default-source bundle, add the off-year sources, write into repo:
    uv run python experiments/build_targets.py \
        --base /path/to/arch-us-2024/consumer_facts.jsonl

    # Or build everything from scratch (the slow base build needs arch-data source
    # access: arch-raw R2 auth, or ARCH_SOURCE_ARTIFACT_FETCH=1 for public URLs):
    uv run python experiments/build_targets.py --build-base --year 2023
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO_ROOT / "data" / "targets" / "consumer_facts.jsonl"

#: Environment override for locating the arch-data checkout.
ARCH_REPO_ENV = "L0_PAPER_ARCH_REPO"

#: Sources that a default ``arch build-bundle --year 2023`` run drops, because their
#: artifact is declared only for the year shown here (not 2023), so the exact-year
#: lookup skips them (see module docstring). Each is built individually at its own
#: year and merged. The *year here is a source vintage*, not a target period --
#: Populace ages all of these to the single 2024 target period downstream. Kept as
#: an explicit literal so the set of "extra" sources is reviewable in one place; if
#: arch-data ever resolves per-source vintages itself, this map (and the whole
#: off-year step) becomes unnecessary.
OFF_YEAR_SOURCES: dict[str, int] = {
    "jct-tax-expenditures-2024": 2024,
    "census-acs-s0101-national-age-2024": 2024,
    "census-acs-s0101-state-age-2024": 2024,
    "census-acs-s0101-congressional-district-age-2024": 2024,
    "census-acs-s2201-congressional-district-snap-2024": 2024,
    "cms-aca-effectuated-enrollment-2022": 2022,
    "cms-aca-oep-state-level": 2024,
    "cms-aca-oep-state-level-2022": 2022,
    "cms-aca-oep-state-level-2025": 2025,
}


def _arch_repo(override: str | None) -> Path:
    """Locate the arch-data checkout (override > env > sibling of this repo)."""
    candidates = [override, os.environ.get(ARCH_REPO_ENV), str(REPO_ROOT.parent / "arch-data")]
    for cand in candidates:
        if not cand:
            continue
        root = Path(cand).expanduser().resolve()
        if (root / "arch" / "harness.py").is_file():
            return root
    raise FileNotFoundError(
        "Could not locate the arch-data checkout. Pass --arch-repo or set "
        f"{ARCH_REPO_ENV}; expected a sibling 'arch-data' next to {REPO_ROOT}."
    )


def _run_arch(arch_repo: Path, *args: str) -> None:
    cmd = ["uv", "run", "--directory", str(arch_repo), "arch", *args]
    print(f"  $ {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def _arch_commit(arch_repo: Path) -> str | None:
    try:
        return subprocess.run(
            ["git", "-C", str(arch_repo), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open() if line.strip()]


def build_base_bundle(arch_repo: Path, year: int, workdir: Path) -> Path:
    """Build the default-source bundle at ``year`` and return its consumer_facts path."""
    out = workdir / "base"
    _run_arch(arch_repo, "build-bundle", "--year", str(year), "--out", str(out), "--replace")
    return out / "consumer_facts.jsonl"


def build_off_year_suites(arch_repo: Path, workdir: Path) -> dict[str, Path]:
    """Build each off-year source at its pinned year; return {source: consumer_facts}."""
    paths: dict[str, Path] = {}
    for source, year in OFF_YEAR_SOURCES.items():
        out = workdir / "suites" / source
        print(f"- building {source} @ year {year}")
        _run_arch(arch_repo, "build-suite", source, "--year", str(year), "--out", str(out), "--replace")
        cf = out / "consumer_facts.jsonl"
        if not cf.is_file():
            raise FileNotFoundError(f"{source}: build-suite produced no consumer_facts.jsonl")
        paths[source] = cf
    return paths


def merge(base_facts: Path, suite_facts: dict[str, Path], out: Path) -> dict:
    """Concatenate base + off-year facts, guard against key collisions, write ``out``.

    Concatenation is the right merge here: the off-year sources were *absent* from
    the base bundle (that's why we rebuilt them), so they introduce no
    ``aggregate_fact_key`` collisions -- the guard below asserts that invariant
    rather than silently de-duplicating. Facts keep their native source periods;
    period unification happens later in Populace, not here.
    """
    base_rows = _read_jsonl(base_facts)
    merged = list(base_rows)
    added: dict[str, int] = {}
    for source, path in suite_facts.items():
        rows = _read_jsonl(path)
        added[source] = len(rows)
        merged.extend(rows)

    # Mirror arch.bundle's uniqueness guard: aggregate_fact_key must stay unique.
    agg = Counter(r["aggregate_fact_key"] for r in merged if "aggregate_fact_key" in r)
    collisions = {k: c for k, c in agg.items() if c > 1}
    if collisions:
        raise SystemExit(
            f"Refusing to write: {len(collisions)} duplicated aggregate_fact_key(s) "
            f"after merge, e.g. {list(collisions)[:3]}."
        )

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as fh:
        for r in merged:
            fh.write(json.dumps(r) + "\n")
    return {"base_facts": len(base_rows), "added": added, "total": len(merged)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--arch-repo", help="Path to the arch-data checkout (default: sibling ../arch-data).")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"Output consumer_facts.jsonl (default: {DEFAULT_OUT}).")
    parser.add_argument("--year", type=int, default=2023, help="Year for the base (default-source) bundle.")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--base", type=Path, help="Reuse an existing default-source consumer_facts.jsonl.")
    src.add_argument("--build-base", action="store_true", help="Build the base bundle here (slow; needs arch-data source access).")
    parser.add_argument("--workdir", type=Path, default=None, help="Scratch dir for intermediate suite builds (default: alongside --out).")
    args = parser.parse_args()

    arch_repo = _arch_repo(args.arch_repo)
    out = args.out.resolve()
    workdir = (args.workdir or (out.parent / "_build")).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    print(f"arch-data: {arch_repo}\nout: {out}\nworkdir: {workdir}\n")

    if args.build_base:
        print(f"== Building base bundle (default sources @ {args.year}) ==")
        base_facts = build_base_bundle(arch_repo, args.year, workdir)
    else:
        base_facts = args.base.expanduser().resolve()
        if not base_facts.is_file():
            sys.exit(f"--base not found: {base_facts}")
        print(f"== Reusing base bundle: {base_facts} ==")

    print("\n== Building off-year sources (local artifacts; no network) ==")
    suite_facts = build_off_year_suites(arch_repo, workdir)

    print("\n== Merging ==")
    counts = merge(base_facts, suite_facts, out)

    manifest = {
        "out": str(out),
        "arch_repo": str(arch_repo),
        "arch_commit": _arch_commit(arch_repo),
        "base_year": args.year,
        "base_source": "built here" if args.build_base else str(base_facts),
        "off_year_sources": OFF_YEAR_SOURCES,
        "counts": counts,
        "note": (
            "Complete L0 target bundle: base default-source bundle + off-year "
            "sources merged by concatenation. Regenerate with experiments/build_targets.py."
        ),
    }
    (out.parent / "targets_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(
        f"\nWrote {counts['total']} facts -> {out}\n"
        f"  base: {counts['base_facts']}  +  off-year: {sum(counts['added'].values())} "
        f"across {len(counts['added'])} sources\n"
        f"  manifest: {out.parent / 'targets_manifest.json'}"
    )


if __name__ == "__main__":
    main()
