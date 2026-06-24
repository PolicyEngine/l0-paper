interface EquationCardProps {
  title: string;
  equation: string;
  note: string;
}

export default function EquationCard({ title, equation, note }: EquationCardProps) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-8 shadow-sm">
      <div className="text-2xl font-bold text-pe-dark">{title}</div>
      <div className="math-text mt-8 rounded-md bg-slate-50 px-6 py-5 text-center text-2xl text-slate-800">
        {equation}
      </div>
      <p className="mt-6 text-xl leading-snug text-slate-600">{note}</p>
    </div>
  );
}
