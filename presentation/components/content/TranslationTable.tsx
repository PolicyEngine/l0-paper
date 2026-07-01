import Math from "@/components/content/Math";
import { ReactNode } from "react";

interface TranslationTableProps {
  className?: string;
}

const rows: { from: ReactNode; to: ReactNode }[] = [
  { from: "a weight in a neural network", to: "a candidate microdata record" },
  { from: "zero a weight (prune it)", to: "drop a record from the dataset" },
  { from: <>stochastic gate <Math tex="z_i" /> on a weight</>, to: <>stochastic gate <Math tex="z_i" /> on a record</> },
  {
    from: <><Math tex="\sum_i \Pr(z_i\neq 0)" /> = expected active weights</>,
    to: "= expected retained-record count",
  },
  { from: "a sparser network", to: "a dataset pruned to a budget" },
];

export default function TranslationTable({ className = "" }: TranslationTableProps) {
  return (
    <div className={`overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm ${className}`}>
      <div className="grid grid-cols-[1fr_auto_1fr] bg-pe-dark text-center text-lg font-bold text-white">
        <div className="px-5 py-3">Louizos et al. — neural network</div>
        <div className="px-2 py-3" aria-hidden />
        <div className="px-5 py-3">Our setting — microsimulation</div>
      </div>
      {rows.map((r, i) => (
        <div
          key={i}
          className={`grid grid-cols-[1fr_auto_1fr] items-center ${i % 2 ? "bg-slate-50" : "bg-white"}`}
        >
          <div className="px-5 py-3.5 text-lg text-slate-600">{r.from}</div>
          <div className="px-2 py-3.5 text-xl font-bold text-pe-teal">→</div>
          <div className="px-5 py-3.5 text-lg font-medium text-pe-dark">{r.to}</div>
        </div>
      ))}
    </div>
  );
}
