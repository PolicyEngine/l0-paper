interface RegimeQuantileVizProps {
  className?: string;
}

// Heights (%) sketching a spread of quantile draws vs a single mean.
const draws = [22, 40, 33, 58, 47, 71, 52, 64];

export default function RegimeQuantileViz({ className = "" }: RegimeQuantileVizProps) {
  return (
    <div className={`rounded-lg border border-slate-200 bg-white p-7 shadow-sm ${className}`}>
      <div className="grid grid-cols-2 gap-5">
        {/* Predict the mean */}
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <div className="text-base font-bold text-slate-500">Predict the mean</div>
          <div className="mt-4 flex h-28 items-end justify-center gap-1">
            <div className="w-6 rounded-t bg-slate-400" style={{ height: "46%" }} />
          </div>
          <div className="mt-3 text-sm leading-snug text-slate-500">
            collapses everyone to one value — spread is lost
          </div>
        </div>

        {/* Sample the conditional */}
        <div className="rounded-lg border border-pe-teal/40 bg-pe-light/50 p-4">
          <div className="text-base font-bold text-pe-teal">Sample the conditional</div>
          <div className="mt-4 flex h-28 items-end justify-center gap-1">
            {draws.map((h, i) => (
              <div
                key={i}
                className="w-3 rounded-t bg-pe-teal"
                style={{ height: `${h}%` }}
              />
            ))}
          </div>
          <div className="mt-3 text-sm leading-snug text-slate-600">
            q ~ U(0,1) per record reproduces the full distribution
          </div>
        </div>
      </div>

      {/* Sign regimes (e.g. capital gains) */}
      <div className="mt-5">
        <div className="mb-2 text-base font-semibold text-slate-500">
          Regime gate picks the sign, a forest draws the magnitude — e.g. capital gains
        </div>
        <div className="grid grid-cols-3 overflow-hidden rounded-md border border-slate-200 text-center text-base font-semibold">
          <span className="bg-amber-50 py-2.5 text-pe-amber">negative</span>
          <span className="bg-slate-100 py-2.5 text-slate-500">zero</span>
          <span className="bg-pe-light py-2.5 text-pe-dark">positive</span>
        </div>
      </div>
    </div>
  );
}
