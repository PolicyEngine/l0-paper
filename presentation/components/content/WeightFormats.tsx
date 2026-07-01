import { ReactNode } from "react";

interface WeightFormatsProps {
  /** Reveal the long-format matrix beside the wide-format one. */
  showLong?: boolean;
  className?: string;
}

// Stylised illustrative records — the values are for layout, not real
// calibration weights. The point is the shape of each table, not the numbers.
const WIDE_AREAS = ["Area A", "Area B", "Area C"];
const WIDE_ROWS = [
  { rec: "Record 1", weights: ["1.2", "0.4", "3.4"] },
  { rec: "Record 2", weights: ["0.7", "2.1", "0.9"] },
  { rec: "Record 3", weights: ["0.5", "1.5", "0.8"] },
];

const LONG_ROWS = [
  { rec: "Record 1", geo: "Area A", w: "1.2" },
  { rec: "Record 2", geo: "Area B", w: "2.1" },
  { rec: "Record 3", geo: "Area C", w: "0.9" },
];

export default function WeightFormats({ showLong = true, className = "" }: WeightFormatsProps) {
  return (
    <div className={`grid grid-cols-2 gap-8 ${className}`}>
      {/* Wide format: one weight per area, so a record spans many columns. */}
      <FormatCard
        accent="slate"
        format="UK: Wide format"
        tagline="Each record carries one weight per subnational area."
        footer="Weight columns for overlapping areas can disagree."
      >
        <table className="w-full border-collapse text-center text-lg">
          <thead>
            <tr>
              <th
                rowSpan={2}
                className="border border-slate-300 bg-slate-100 px-3 py-2 text-left align-bottom text-sm font-semibold text-slate-600"
              >
                Record
              </th>
              <th
                colSpan={WIDE_AREAS.length}
                className="border border-slate-300 bg-slate-100 px-3 py-1 text-sm font-semibold text-slate-600"
              >
                Weights — one per area
              </th>
            </tr>
            <tr>
              {WIDE_AREAS.map((a) => (
                <th
                  key={a}
                  className="border border-slate-300 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-500"
                >
                  {a}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {WIDE_ROWS.map((r) => (
              <tr key={r.rec}>
                <td className="border border-slate-300 px-3 py-2 text-left font-medium text-pe-dark">
                  {r.rec}
                </td>
                {r.weights.map((w, i) => (
                  <td
                    key={i}
                    className="border border-slate-300 bg-slate-50/60 px-3 py-2 tabular-nums text-slate-700"
                  >
                    {w}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </FormatCard>

      {/* Long format: one weight per record, geography on the record. Revealed on click. */}
      {showLong && (
        <FormatCard
          accent="teal"
          format="US: Long format"
          tagline="Each record carries a single weight; geography lives on the record."
          footer="The same weights must reproduce nested totals: district → state → national."
        >
          <table className="w-full border-collapse text-center text-lg">
            <thead>
              <tr>
                <th className="border border-slate-300 bg-slate-100 px-3 py-2 text-left text-sm font-semibold text-slate-600">
                  Record
                </th>
                <th className="border border-slate-300 bg-slate-100 px-3 py-2 text-sm font-semibold text-slate-600">
                  Geography
                </th>
                <th className="border border-pe-teal bg-pe-light/60 px-3 py-2 text-sm font-semibold text-pe-dark">
                  Weight
                </th>
              </tr>
            </thead>
            <tbody>
              {LONG_ROWS.map((r) => (
                <tr key={r.rec}>
                  <td className="border border-slate-300 px-3 py-2 text-left font-medium text-pe-dark">
                    {r.rec}
                  </td>
                  <td className="border border-slate-300 px-3 py-2 text-slate-700">{r.geo}</td>
                  <td className="border border-pe-teal bg-pe-light/40 px-3 py-2 tabular-nums font-semibold text-pe-dark">
                    {r.w}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </FormatCard>
      )}
    </div>
  );
}

function FormatCard({
  accent,
  format,
  tagline,
  footer,
  children,
}: {
  accent: "teal" | "slate";
  format: string;
  tagline: string;
  footer: string;
  children: ReactNode;
}) {
  const ring = accent === "teal" ? "border-pe-teal" : "border-slate-300";
  const dot = accent === "teal" ? "bg-pe-teal" : "bg-slate-400";
  return (
    <div className={`flex flex-col rounded-lg border-2 ${ring} bg-white p-6 shadow-sm`}>
      <div className="mb-3 flex items-center gap-3">
        <span className={`h-3 w-3 rounded-full ${dot}`} />
        <span className="text-2xl font-extrabold text-pe-dark">{format}</span>
      </div>
      <p className="mb-4 text-base leading-snug text-slate-600">{tagline}</p>
      {children}
      <p className="mt-4 text-sm leading-snug text-slate-500">{footer}</p>
    </div>
  );
}
