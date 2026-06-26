interface ScaleLadderProps {
  className?: string;
}

// Generation grows the record count; heights are illustrative (log-ish), not to scale.
const grow = [
  { value: "~75k", label: "survey spine", height: 18 },
  { value: "300k", label: "matched pool", height: 36 },
  { value: "3M", label: "generate-big", height: 60 },
  { value: "30M", label: "one per person", height: 80 },
];

// The shipped, pruned file must sit clearly below the generate-big peak.
const pruneHeight = 30;

export default function ScaleLadder({ className = "" }: ScaleLadderProps) {
  return (
    <div className={`rounded-lg border border-slate-200 bg-white p-7 shadow-sm ${className}`}>
      <div className="flex items-center justify-between text-sm font-bold uppercase tracking-[0.14em]">
        <span className="text-pe-teal">candidate universe grows</span>
        <span className="text-pe-amber">prune to budget</span>
      </div>

      <div className="mt-6 grid grid-cols-5 items-end gap-3" style={{ height: 210 }}>
        {grow.map((s) => (
          <div key={s.label} className="flex h-full flex-col justify-end">
            <div className="rounded-t-md bg-pe-teal" style={{ height: `${s.height}%` }} />
            <div className="mt-2 text-center">
              <div className="text-lg font-extrabold tracking-tight text-pe-dark">{s.value}</div>
              <div className="text-xs leading-tight text-slate-500">{s.label}</div>
            </div>
          </div>
        ))}

        {/* Prune step: lower than generate-big, and visually marked as a step down. */}
        <div className="flex h-full flex-col justify-end">
          <div className="mb-1 text-center text-base font-bold text-pe-amber">↓ prune</div>
          <div className="rounded-t-md bg-pe-amber" style={{ height: `${pruneHeight}%` }} />
          <div className="mt-2 text-center">
            <div className="text-lg font-extrabold tracking-tight text-pe-dark">budget</div>
            <div className="text-xs leading-tight text-slate-500">shipped dataset</div>
          </div>
        </div>
      </div>

      <div className="mt-6 rounded-md bg-slate-50 px-5 py-4 text-base text-slate-600">
        <span className="font-bold text-pe-dark">Why prune:</span> calibration memory ≈ targets ×
        records, and the shipped file must stay cheap to store, load, and simulate.
      </div>
    </div>
  );
}
