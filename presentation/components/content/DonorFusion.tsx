interface DonorFusionProps {
  className?: string;
}

const donors = [
  { source: "SCF", vars: "wealth, net worth" },
  { source: "IRS PUF", vars: "tax detail, deductions" },
  { source: "SIPP", vars: "tips" },
  { source: "CPS ORG", vars: "wage, hours, union" },
  { source: "MEPS-IC", vars: "ESI premiums" },
  { source: "ACS", vars: "rent" },
];

export default function DonorFusion({ className = "" }: DonorFusionProps) {
  return (
    <div className={`rounded-lg border border-slate-200 bg-white p-7 shadow-sm ${className}`}>
      {/* Survey spine */}
      <div className="rounded-lg border-2 border-pe-teal bg-pe-light/60 px-5 py-4">
        <div className="text-xl font-extrabold text-pe-dark">CPS ASEC spine · 3 years pooled &amp; aged</div>
        <div className="mt-1 text-base text-slate-600">
          three CPS ASEC vintages aged to one period — more households &amp; variability, same survey design
        </div>
      </div>

      <div className="my-4 text-center text-base font-semibold text-pe-teal">
        ↑ borrow the conditional from the best donor for each domain ↑
      </div>

      {/* Donor sources */}
      <div className="grid grid-cols-3 gap-3">
        {donors.map((d) => (
          <div key={d.source} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3">
            <div className="text-base font-bold text-pe-dark">{d.source}</div>
            <div className="mt-0.5 text-sm leading-snug text-slate-500">{d.vars}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
