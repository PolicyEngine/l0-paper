interface StatNumberProps {
  value: string;
  label: string;
  sublabel?: string;
}

export default function StatNumber({ value, label, sublabel }: StatNumberProps) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-7 text-center shadow-sm">
      <div className="text-5xl font-extrabold tracking-tight text-pe-teal">{value}</div>
      <div className="mt-3 text-xl font-bold text-pe-dark">{label}</div>
      {sublabel && <div className="mt-2 text-base text-slate-500">{sublabel}</div>}
    </div>
  );
}
