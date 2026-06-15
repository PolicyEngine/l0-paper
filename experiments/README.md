# Experiments

This directory is reserved for Populace-compatible experiment code backing the
paper.

The migration target is to preserve the L0 paper experimental design while
using `populace.calibrate` and Populace build artifacts as the implementation
surface:

- L0/Hard Concrete runs through Populace `calibrate(..., target_records=...)`.
- Baselines use the same Populace target matrix/loss surface where possible.
- Result artifacts carry the Populace commit, target registry/build artifact
  identity, solver options, and random seeds.

