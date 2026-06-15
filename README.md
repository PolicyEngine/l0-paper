# L0 paper

Paper and experiment workspace for PolicyEngine's L0 dataset-reduction work on
the Populace stack.

The initial manuscript narrative was imported from the archived
`PolicyEngine/microplex-us` paper draft. It remains LaTeX-first for now, with a
Quarto entry point that includes the existing section files so the paper can be
rendered and revised incrementally while the implementation moves to
`PolicyEngine/populace`.

## Layout

- `paper/index.qmd` - Quarto entry point for the paper.
- `paper/main.tex` - legacy LaTeX root copied from the prior draft.
- `paper/sections/` - manuscript sections.
- `paper/tables/` - generated/result tables included by the paper.
- `paper/figures/` - figure outputs.
- `paper/bibliography/references.bib` - references.
- `experiments/` - Populace-compatible experiment code will live here.

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
archived `microplex` or `microplex-us` internals. The imported manuscript still
contains old Microplex wording in places; updating the narrative to Populace is
part of the next migration pass.

