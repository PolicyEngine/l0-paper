interface GeographyHierarchyProps {
  /** Show the "district totals -> state totals -> national totals" summation note. */
  showSummation?: boolean;
  className?: string;
}

const levels = [
  { label: "National", count: "1", note: "one country total" },
  { label: "State", count: "51", note: "50 states + DC" },
  { label: "Congressional district", count: "435", note: "local-area detail" },
];

export default function GeographyHierarchy({
  showSummation = false,
  className = "",
}: GeographyHierarchyProps) {
  return (
    <div className={`rounded-lg border border-slate-200 bg-white p-8 shadow-sm ${className}`}>
      {/* Concentric nesting: national contains state contains district. */}
      <div className="rounded-xl border-2 border-pe-amber bg-amber-50/60 p-5">
        <LevelHeader {...levels[0]} accent="amber" />
        <div className="mt-4 rounded-xl border-2 border-pe-teal bg-pe-light/60 p-5">
          <LevelHeader {...levels[1]} accent="teal" />
          <div className="mt-4 rounded-xl border-2 border-slate-400 bg-slate-50 p-5">
            <LevelHeader {...levels[2]} accent="slate" />
          </div>
        </div>
      </div>

      {showSummation && (
        <div className="mt-6 flex items-center gap-3 rounded-md bg-slate-50 px-5 py-4 text-lg text-slate-600">
          <span className="font-bold text-pe-dark">Nested totals:</span>
          <span>
            district&nbsp;→&nbsp;state&nbsp;→&nbsp;national totals must agree in one weighted dataset.
          </span>
        </div>
      )}
    </div>
  );
}

function LevelHeader({
  label,
  count,
  note,
  accent,
}: {
  label: string;
  count: string;
  note: string;
  accent: "amber" | "teal" | "slate";
}) {
  const dot =
    accent === "amber" ? "bg-pe-amber" : accent === "teal" ? "bg-pe-teal" : "bg-slate-400";
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <span className={`h-3 w-3 rounded-full ${dot}`} />
        <span className="text-xl font-extrabold text-pe-dark">{label}</span>
        <span className="text-base text-slate-500">{note}</span>
      </div>
      <span className="text-2xl font-extrabold tracking-tight text-pe-dark">{count}</span>
    </div>
  );
}
