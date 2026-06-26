interface FactAnatomyProps {
  className?: string;
}

const dimensions = [
  { key: "Geography", value: "state · California" },
  { key: "Entity", value: "tax unit" },
  { key: "Measure", value: "adjusted gross income" },
  { key: "Aggregation", value: "sum" },
  { key: "Provenance", value: "IRS SOI, Historic Table 2, 2022" },
];

const classes = [
  {
    label: "Hard target",
    note: "fit the calibration to it",
    accent: "border-t-pe-teal",
    text: "text-pe-teal",
  },
  {
    label: "Validation-only",
    note: "scored, never fit (e.g. SPM poverty)",
    accent: "border-t-pe-amber",
    text: "text-pe-amber",
  },
  {
    label: "Not yet estimable",
    note: "no source in the support universe",
    accent: "border-t-slate-400",
    text: "text-slate-500",
  },
];

export default function FactAnatomy({ className = "" }: FactAnatomyProps) {
  return (
    <div className={className}>
      {/* One fact, exploded into its dimensions. */}
      <div className="rounded-lg border border-slate-200 bg-white p-7 shadow-sm">
        <div className="mb-4 text-sm font-bold uppercase tracking-[0.16em] text-pe-teal">
          One source-backed fact
        </div>
        <div className="space-y-2.5">
          {dimensions.map((d) => (
            <div key={d.key} className="flex items-baseline gap-4">
              <span className="w-44 flex-none text-base font-semibold text-slate-500">{d.key}</span>
              <span className="math-text text-lg text-pe-dark">{d.value}</span>
            </div>
          ))}
        </div>
        <div className="mt-5 rounded-md bg-slate-50 px-4 py-3 text-base text-slate-600">
          Provenance and value are preserved exactly; Arch re-expresses, it does not reconcile or impute.
        </div>
      </div>

      {/* Three-way classification. */}
      <div className="mt-5 grid grid-cols-3 gap-4">
        {classes.map((c) => (
          <div
            key={c.label}
            className={`rounded-lg border border-slate-200 border-t-4 ${c.accent} bg-white p-4 shadow-sm`}
          >
            <div className={`text-lg font-bold ${c.text}`}>{c.label}</div>
            <div className="mt-1 text-sm leading-snug text-slate-500">{c.note}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
