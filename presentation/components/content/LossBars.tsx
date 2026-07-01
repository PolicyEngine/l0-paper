interface LossBarsProps {
  /** Method keys to draw; the axis, ticks and all x-labels are always shown. */
  revealed: string[];
  className?: string;
}

interface Method {
  key: string;
  label: string;
  loss: number;
  color: string;
}

// Same bars, order and colours as the paper's objective-frontier figure
// (paper/figures/f0_objective_frontier.png). Bars are revealed in narrative
// order into these fixed, labelled slots; all five = the paper figure.
const METHODS: Method[] = [
  { key: "l0_gated", label: "L0 gated", loss: 9.86, color: "#6B7280" },
  { key: "l0_refit", label: "L0 + refit", loss: 4.74, color: "#14B8A6" },
  { key: "dense_full", label: "Dense full", loss: 5.07, color: "#0F766E" },
  { key: "random_reweight", label: "Random + reweight", loss: 7.55, color: "#64748B" },
  { key: "dense_scaled", label: "Dense sample scaled", loss: 24.24, color: "#F59E0B" },
];

const TICKS = [0, 5, 10, 15, 20, 25];
const AXIS_MAX = 26.5; // headroom above the 25 tick, as in the paper figure
const PLOT_H = 340; // px

export default function LossBars({ revealed, className = "" }: LossBarsProps) {
  return (
    <div className={`px-8 py-7 ${className}`}>
      <div className="mb-5 text-center text-xl font-bold text-pe-dark">
        Full-surface non-L0 loss after 1,500-epoch fits
      </div>
      <div className="flex">
        {/* y-axis title */}
        <div className="flex w-6 items-center justify-center">
          <span
            className="whitespace-nowrap text-sm font-semibold text-black"
            style={{ transform: "rotate(-90deg)" }}
          >
            Populace objective loss (%)
          </span>
        </div>

        {/* y tick labels gutter */}
        <div className="relative w-8" style={{ height: PLOT_H }}>
          {TICKS.map((t) => (
            <span
              key={t}
              className="absolute right-2 -translate-y-1/2 text-sm text-black"
              style={{ bottom: (t / AXIS_MAX) * PLOT_H }}
            >
              {t}
            </span>
          ))}
        </div>

        {/* plot column */}
        <div className="flex-1">
          <div
            className="relative border-b-2 border-l-2 border-black"
            style={{ height: PLOT_H }}
          >
            {/* gridlines */}
            {TICKS.filter((t) => t > 0).map((t) => (
              <div
                key={t}
                className="absolute left-0 right-0 h-px bg-slate-100"
                style={{ bottom: (t / AXIS_MAX) * PLOT_H }}
              />
            ))}

            {/* bars */}
            <div className="absolute inset-0 flex items-end">
              {METHODS.map((m) => {
                const on = revealed.includes(m.key);
                return (
                  <div
                    key={m.key}
                    className="flex flex-1 flex-col items-center justify-end"
                    style={{ height: PLOT_H }}
                  >
                    {on && (
                      <div className="mb-1.5 text-base font-bold text-slate-800">
                        {m.loss.toFixed(2)}%
                      </div>
                    )}
                    {on && (
                      <div
                        style={{
                          height: (m.loss / AXIS_MAX) * PLOT_H,
                          width: "62%",
                          backgroundColor: m.color,
                        }}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* x-axis tick marks: a short vertical line centred under each bar */}
          <div className="flex">
            {METHODS.map((m) => (
              <div key={`tick-${m.key}`} className="flex flex-1 justify-center">
                <div className="h-2 w-px bg-black" />
              </div>
            ))}
          </div>

          {/* x-axis labels: right end anchored at each bar centre, hanging
              down-left at 30deg so they never overlap the bars (matplotlib
              rotation=30, ha='right'). */}
          <div className="flex" style={{ height: 96 }}>
            {METHODS.map((m) => (
              <div key={m.key} className="relative flex-1">
                <span
                  className="absolute right-1/2 top-2 whitespace-nowrap text-sm text-black"
                  style={{ transformOrigin: "top right", transform: "rotate(-30deg)" }}
                >
                  {m.label}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <p className="mt-2 text-center text-xs text-slate-400">
        337,704 candidate households; 32,633 targets; L0-selected and sampled baselines retain 57,240
        records
      </p>
    </div>
  );
}
