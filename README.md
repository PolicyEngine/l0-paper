# L0 paper

Paper and experiment workspace for PolicyEngine's L0 dataset-reduction work on
the Populace stack.

This work is being prepared for presentation at IMA 2026 (Brussels),
July 1, 2026: <https://ima26.brussels/blog/presentation_maria_juaristi/>.

The initial manuscript narrative was built in relation to the old
`PolicyEngine/policyengine-us-data` paper draft. It remains LaTeX-first for now, 
with a Quarto entry point that includes the existing section files so the paper 
can be rendered and revised incrementally while the implementation moves to
`PolicyEngine/populace`.

## Layout

- `paper/index.qmd` - Quarto entry point for the paper.
- `paper/main.tex` - legacy LaTeX root copied from the prior draft.
- `paper/sections/` - manuscript sections.
- `paper/tables/` - generated/result tables included by the paper.
- `paper/figures/` - figure outputs.
- `paper/bibliography/references.bib` - references.
- `src/l0_paper/` - Python helpers for Populace-backed experiments.
- `tests/` - tests that exercise the active Populace API surface.
- `experiments/` - notebooks/configs/result scripts for paper experiments.

## Development

This repo expects to be cloned next to `PolicyEngine/populace`:

```text
PolicyEngine/
  l0-paper/
  populace/
```

The `pyproject.toml` points `uv` at the sibling Populace packages, so local
tests use the active checkout rather than archived Microplex internals.

```bash
uv sync --all-extras --dev
uv run pytest
uv run ruff check .
```

The smoke test runs a tiny `populace.calibrate.calibrate(...,
target_records=...)` L0 calibration to verify the experiment repo is wired to
Populace's implementation.

## Render

Install Quarto, then run:

```bash
quarto render
```

The current local machine does not have Quarto installed. The legacy LaTeX
source can still be checked with:

```bash
cd paper
latexmk -pdf main.tex
```

## Compatibility Direction

New code in this repository should target active Populace APIs rather than
archived `microplex` or `microplex-us` internals. The manuscript narrative has
been migrated from the old Microplex wording to Populace; the archived
repositories are referenced only as a migration reference.
