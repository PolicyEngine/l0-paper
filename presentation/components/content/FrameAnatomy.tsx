interface FrameAnatomyProps {
  className?: string;
}

const entities = ["person", "household", "tax unit", "SPM unit", "family", "marital unit"];

const weights = [
  { label: "design", note: "carried from the survey" },
  { label: "importance", note: "from pool assembly" },
  { label: "calibrated", note: "fit to the targets (final)" },
];

export default function FrameAnatomy({ className = "" }: FrameAnatomyProps) {
  return (
    <div className={`rounded-lg border border-slate-200 bg-white p-7 shadow-sm ${className}`}>
      <div className="mb-5 text-sm font-bold uppercase tracking-[0.16em] text-pe-teal">
        The frame
      </div>

      {/* Entity tables */}
      <div className="mb-5">
        <div className="mb-2 text-base font-semibold text-slate-500">Entity tables</div>
        <div className="flex flex-wrap gap-2">
          {entities.map((e) => (
            <span
              key={e}
              className="rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-base font-medium text-pe-dark"
            >
              {e}
            </span>
          ))}
        </div>
      </div>

      {/* Typed weights: one-way flow */}
      <div className="mb-5">
        <div className="mb-2 text-base font-semibold text-slate-500">Types of weights</div>
        <div className="flex flex-wrap items-center gap-2">
          {weights.map((w, i) => (
            <span key={w.label} className="flex items-center gap-2">
              <span className="rounded-md border border-pe-teal/40 bg-pe-light px-3 py-1.5 text-base font-semibold text-pe-dark">
                {w.label}
                <span className="ml-2 font-normal text-slate-500">{w.note}</span>
              </span>
              {i < weights.length - 1 && <span className="text-pe-teal">→</span>}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
