# Figures

Final figures land here. Regenerate experiment figures with:

```bash
uv run --extra viz l0 figures --sweep runs/weighted-loss-3seed --paper-figures
```

Or run the current-paper wrapper:

```bash
uv run --extra data --extra viz l0 paper \
    --consumer-facts data/targets/consumer_facts.jsonl
```

The manuscript currently references:

- `fig:pipeline` (Data): Populace pipeline overview for this build's configuration.
- `fig:budget_frontier` (Results): out-of-sample calibration error vs. retained-record budget,
  informed L0 vs. random sampling.
- `fig:generalization_gap` (Results): in-sample vs. out-of-sample calibration error.
- `fig:by_family` (Results): out-of-sample error by held-out target family.
- `fig:usability` (Results): weight concentration and effective-sample-size diagnostics.
- `fig:operability` (Results): the L2 concentration-control contrast.
- `fig:cost_accuracy` (Appendix): runtime and accuracy tradeoff.

The pipeline overview is generated separately:

```bash
uv run python paper/figures/populace_pipeline.py
```
