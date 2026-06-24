"""Build and freeze the pre-calibration dataset for the L0 experiments.

This reproduces the Populace dataset PolicyEngine ships, stopping immediately
before the calibration step. The frozen artifact -- the materialized
:class:`~populace.frame.Frame` plus the :class:`~populace.calibrate.TargetRegistry`
-- becomes the single, shared input every calibration experiment runs on, so that
the calibration routine is the only thing that varies between conditions.

The boundary mirrors ``populace/tools/build_us_fiscal_refresh_release.py``:

    facts -> compile_us_fiscal_target_registry -> _load_frame
          -> (_with_aca_marketplace_source_outputs) -> _materialize_target_frame
          ===  pre-calibration dataset  ===  then calibrate(...)

The materialized frame carries formula-owned measure columns (``income_tax`` etc.)
that Populace's H5 export gate intentionally rejects, so the frame is persisted by
pickle (a regenerable cache keyed to the Populace version) rather than to ``.h5``.
The registry is written as its portable, content-addressed JSON artifact.
"""

from __future__ import annotations

import hashlib
import json
import pickle
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np

from populace.calibrate import TargetRegistry
from populace.calibrate.registry import TargetSpec
from populace.frame import Frame, Weights

from ._populace_driver import _populace_repo_root, load_driver

FRAME_PICKLE = "precalibration_frame.pkl"
REGISTRY_JSON = "registry.json"
MANIFEST_JSON = "precalibration_manifest.json"

ResetWeights = Literal["uniform", "keep"]


@dataclass(frozen=True)
class PreCalibrationArtifact:
    """A frozen pre-calibration dataset on disk, with its in-memory objects."""

    directory: Path
    frame: Frame
    registry: TargetRegistry
    manifest: dict[str, Any]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _absolute_path(path: str | Path) -> Path:
    """Return an absolute path without dereferencing symlinks.

    HuggingFace dataset snapshots expose ``*.h5`` files as symlinks to content
    blobs whose filenames are hashes. PolicyEngine-US validates the path suffix,
    so resolving that symlink turns a valid ``populace_us_2024.h5`` path into an
    invalid blob path with no ``.h5`` extension.
    """
    expanded = Path(path).expanduser()
    if expanded.is_absolute():
        return expanded
    return Path.cwd() / expanded


def _populace_commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "-C", str(_populace_repo_root()), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None


def _subsample_households(frame: Frame, n: int, seed: int) -> Frame:
    """Restrict the frame to ``n`` randomly chosen households (POC scale guard).

    Uses :meth:`populace.frame.Frame.select`, which prunes the nested group
    entities and slices weights consistently. Applied to the base frame *before*
    materialization, so it cuts both the PolicyEngine-US microsim cost and the
    calibration-matrix memory.
    """
    household = frame.table("household")
    n_households = len(household)
    if n >= n_households:
        return frame
    rng = np.random.default_rng(seed)
    chosen = rng.choice(household["household_id"].to_numpy(), size=n, replace=False)
    person = frame.table("person")
    mask = person["person_household_id"].isin(set(chosen.tolist())).to_numpy()
    return frame.select(mask)


def _reset_uniform(frame: Frame, weight_entity: str) -> Frame:
    """Replace ``weight_entity`` weights with a mass-preserving uniform vector.

    Starting the experiments from an already-calibrated weight vector would seed
    every condition with a solution. A uniform start that conserves total mass is
    the neutral pre-calibration state. The weight *kind* is preserved because the
    Populace ``Frame`` only allows forward kind transitions.
    """
    weights = frame.weights_for(weight_entity)
    total = float(weights.values.sum())
    n = len(weights.values)
    uniform = np.full(n, total / n, dtype=np.float64)
    return frame.with_weights(
        weight_entity, Weights(values=uniform, kind=weights.kind), mass="conserve"
    )


def _compile_registry(driver, facts, *, period: int, allow_partial: bool) -> TargetRegistry:
    """Compile the target registry, optionally tolerating a partial facts file.

    The production ``compile_us_fiscal_target_registry`` adds the JCT
    tax-expenditure references unconditionally, so any facts file that does not
    cover them fails. ``allow_partial`` resolves only the references derivable
    from the facts themselves (e.g. IRS SOI rows), which is enough to wire and
    smoke-test the full pipeline before a complete Ledger export exists. It is a
    verification aid, not a source of paper numbers.
    """
    if not allow_partial:
        return driver.compile_us_fiscal_target_registry(facts, target_period=period)

    from populace.build.ledger_targets import compile_ledger_target_references
    from populace.build.us.fiscal_targets import _dynamic_us_fiscal_target_references

    materialized = tuple(facts)
    references = _dynamic_us_fiscal_target_references(materialized, target_period=period)
    return compile_ledger_target_references(materialized, references, country="us")


def _drop_unsupported_filter_targets(
    driver, target_specs: tuple
) -> tuple[tuple, dict[str, list[str]]]:
    """Drop targets the US fiscal materializer cannot compute, before calibration.

    ``driver._materialize_target_frame`` hard-asserts (rather than silently
    ignoring) on any ``ledger_filter*`` metadata key outside the driver's
    ``SUPPORTED_LEDGER_FILTER_METADATA_KEYS`` -- e.g. ``income_percentile_range``
    (IRS SOI table 4.3) or ``qualifying_children`` (table 2.5). PolicyEngine's
    production build never feeds those tables; arch-data's *default* bundle does.
    We remove the affected targets here so the rest of the full target set
    materializes, and return the dropped ``{name: [keys]}`` so the reduction in
    target surface stays auditable (it is recorded in the pre-calibration
    manifest). This is the only place targets are removed for solver capability,
    so reruns are deterministic.
    """
    unsupported = driver._unsupported_ledger_filter_metadata(target_specs)
    if not unsupported:
        return target_specs, {}
    kept = tuple(
        spec
        for spec in target_specs
        if str(getattr(spec, "name", "")) not in unsupported
    )
    dropped = {name: list(keys) for name, keys in sorted(unsupported.items())}
    return kept, dropped


def build_precalibration_dataset(
    *,
    ledger_facts: str | Path,
    out_dir: str | Path,
    base_h5: str | Path | None = None,
    period: int | None = None,
    reset_weights: ResetWeights = "uniform",
    weight_entity: str = "household",
    aca_seed: int = 0,
    subsample: int | None = None,
    subsample_seed: int = 0,
    allow_partial_facts: bool = False,
    drop_unsupported_filters: bool = True,
) -> PreCalibrationArtifact:
    """Build the pre-calibration ``(frame, registry)`` and freeze it to ``out_dir``.

    Args:
        ledger_facts: Path to a PolicyEngine Ledger ``consumer_facts.jsonl`` that
            resolves the fiscal target values (see the project plan for how to
            obtain it from ``PolicyEngine/arch-data``).
        out_dir: Directory to write the frozen artifact into.
        base_h5: Candidate-universe frame. Defaults to the published
            ``policyengine/populace-us`` frame downloaded from HuggingFace.
        period: Target/build period. Defaults to the driver's ``PERIOD`` (2024).
        reset_weights: ``"uniform"`` (default) resets weights to a mass-preserving
            uniform start; ``"keep"`` leaves the loaded weights untouched.
        weight_entity: Entity whose weights calibration will fit. Default
            ``"household"``.
        aca_seed: Seed for the ACA marketplace source runtime (only used when ACA
            targets are present).
        drop_unsupported_filters: When True (default), drop targets whose
            ``ledger_filter`` metadata the US fiscal materializer cannot compute
            (recorded in the manifest) instead of letting materialization abort.
            See :func:`_drop_unsupported_filter_targets`.

    Returns:
        A :class:`PreCalibrationArtifact` with the in-memory frame and registry.
    """
    driver = load_driver()
    period = driver.PERIOD if period is None else period

    facts_path = Path(ledger_facts).expanduser().resolve()
    facts = driver._load_ledger_facts(facts_path)
    registry = _compile_registry(
        driver, facts, period=period, allow_partial=allow_partial_facts
    )
    target_specs = registry.specs

    dropped_unsupported: dict[str, list[str]] = {}
    if drop_unsupported_filters:
        target_specs, dropped_unsupported = _drop_unsupported_filter_targets(
            driver, target_specs
        )
        if dropped_unsupported:
            print(
                f"Dropping {len(dropped_unsupported)} target(s) with unsupported "
                "ledger_filter metadata before materialization: "
                + ", ".join(sorted(dropped_unsupported))
            )

    base_path = _absolute_path(base_h5) if base_h5 else driver._download_base_h5()
    frame = driver._load_frame(base_path)

    if subsample is not None:
        frame = _subsample_households(frame, subsample, subsample_seed)

    # The ACA source refresh is only valid when an APTC-recipient target exists;
    # the driver raises otherwise. Partial facts files routinely omit it, so guard.
    aca_tables = driver._aca_source_target_tables(target_specs)
    aca_applied = driver.US_ACA_APTC_TARGET_TABLE in aca_tables
    if aca_applied:
        frame = driver._with_aca_marketplace_source_outputs(
            frame, target_specs, seed=aca_seed
        )

    target_frame, registry, compilation = driver._materialize_target_frame(
        frame, target_specs
    )

    if reset_weights == "uniform":
        target_frame = _reset_uniform(target_frame, weight_entity)
    elif reset_weights != "keep":
        raise ValueError(f"reset_weights must be 'uniform' or 'keep', got {reset_weights!r}.")

    out = Path(out_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    with (out / FRAME_PICKLE).open("wb") as handle:
        pickle.dump(target_frame, handle, protocol=pickle.HIGHEST_PROTOCOL)
    registry.to_json(out / REGISTRY_JSON)

    dropped = list(compilation.get("dropped_target_names", []) or [])
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "populace_commit": _populace_commit(),
        "period": period,
        "weight_entity": weight_entity,
        "reset_weights": reset_weights,
        "subsample": subsample,
        "subsample_seed": subsample_seed if subsample is not None else None,
        "allow_partial_facts": allow_partial_facts,
        "drop_unsupported_filters": drop_unsupported_filters,
        "unsupported_filter_dropped_count": len(dropped_unsupported),
        "unsupported_filter_dropped": dropped_unsupported,
        "base_h5_path": str(base_path),
        "base_h5_sha256": _sha256(base_path),
        "ledger_facts_path": str(facts_path),
        "ledger_facts_sha256": _sha256(facts_path),
        "n_ledger_facts": len(facts),
        "registry_version": registry.version,
        "n_records": target_frame.n(weight_entity),
        "n_targets": len(registry),
        "target_families": sorted({spec.family for spec in registry.specs}),
        "aca_marketplace_applied": aca_applied,
        "dropped_target_count": len(dropped),
        "dropped_target_names": dropped,
        "artifacts": {
            "frame": FRAME_PICKLE,
            "registry": REGISTRY_JSON,
        },
    }
    with (out / MANIFEST_JSON).open("w") as handle:
        json.dump(manifest, handle, indent=2, default=str)

    return PreCalibrationArtifact(
        directory=out, frame=target_frame, registry=registry, manifest=manifest
    )


def load_precalibration_dataset(directory: str | Path) -> tuple[Frame, TargetRegistry]:
    """Reload a frozen pre-calibration ``(frame, registry)`` from ``directory``."""
    directory = Path(directory).expanduser().resolve()
    with (directory / FRAME_PICKLE).open("rb") as handle:
        frame: Frame = pickle.load(handle)
    registry_path = directory / REGISTRY_JSON
    try:
        registry = TargetRegistry.from_json(registry_path)
    except ValueError as exc:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
        if payload.get("populace_target_registry") != 1:
            raise exc
        specs = []
        for raw in payload["specs"]:
            spec_raw = dict(raw)
            spec_raw.pop("aggregation", None)
            specs.append(TargetSpec(**spec_raw))
        registry = TargetRegistry(specs, country=payload["country"])
    return frame, registry
