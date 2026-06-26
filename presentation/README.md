# L0 paper presentation

Standalone draft slide app for the IMA 2026 L0 calibration presentation.

This directory is intentionally independent from the rest of the paper repo for
now. It does not import paper figures, experiment outputs, or root-level build
configuration. Final figures and numeric claims can be wired in later once the
manuscript outputs are stable.

## Commands

Install dependencies from this directory:

```bash
npm install
```

Run the local deck:

```bash
npm run dev
```

Check the app:

```bash
npm run typecheck
npm run lint
npm run build
```

The deck is defined in `slides/config.ts` and `slides/l0-ima-2026.tsx`.
