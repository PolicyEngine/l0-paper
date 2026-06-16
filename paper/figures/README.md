# Figures

Final figures land here. The paper currently references three figures, drawn as `\fbox`
placeholders inline in the section sources until the experiments run:

- `fig:pipeline` (Data): Populace pipeline overview for this build's configuration.
- `fig:budget_frontier` (Results): out-of-sample calibration error vs. retained-record budget,
  informed L0 vs. random sampling.
- `fig:operability` (Results): the effect of sweeping the two penalties on dataset size, weight
  magnitude, and calibration error.
- `fig:convergence` (Results): calibration loss over training epochs.

The figure-generating code is not part of this content package (no `.py` here); it lives in the
Populace stack and emits artifacts that this directory will hold.
