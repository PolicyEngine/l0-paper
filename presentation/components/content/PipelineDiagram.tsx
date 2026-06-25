const stages = [
  ["Sources", "surveys", "administrative facts"],
  ["Combine", "entity tables", "typed weights"],
  ["Impute", "fill support gaps", "preserve uncertainty"],
  ["Geography", "attach areas", "respect hierarchy"],
  ["Compose targets", "source-backed facts", "model mappings"],
  ["Represent", "calibrate weights", "prune to budget"],
];

export default function PipelineDiagram() {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-7 shadow-sm">
      <div className="mb-7 flex items-center justify-between text-sm font-bold uppercase tracking-[0.16em]">
        <span className="text-pe-teal">candidate universe grows</span>
        <span className="text-pe-amber">pruned to budget</span>
      </div>
      <div className="grid grid-cols-6 gap-4">
        {stages.map(([title, line1, line2], index) => (
          <div key={title} className="relative">
            {index < stages.length - 1 && (
              <div className="absolute left-[calc(100%+0.2rem)] top-1/2 h-0.5 w-4 bg-slate-300" />
            )}
            <div
              className={[
                "min-h-44 rounded-lg border-2 p-4 text-center",
                index === stages.length - 1
                  ? "border-pe-amber bg-amber-50"
                  : "border-blue-700/80 bg-slate-50",
              ].join(" ")}
            >
              <div
                className={[
                  "mx-auto mb-4 flex h-8 w-8 items-center justify-center rounded-full text-sm font-bold text-white",
                  index === stages.length - 1 ? "bg-pe-amber" : "bg-blue-700",
                ].join(" ")}
              >
                {index + 1}
              </div>
              <div className="text-xl font-extrabold text-pe-dark">{title}</div>
              <div className="mt-5 space-y-2 text-sm font-medium text-slate-600">
                <div>{line1}</div>
                <div>{line2}</div>
              </div>
            </div>
          </div>
        ))}
      </div>
      <div className="mt-7 rounded-lg border border-slate-300 bg-slate-100 px-6 py-4 text-center">
        <span className="font-bold text-pe-dark">One weighted sampling frame</span>
        <span className="text-slate-500"> carried through every stage</span>
      </div>
    </div>
  );
}
