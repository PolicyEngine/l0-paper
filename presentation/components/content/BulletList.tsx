interface BulletListProps {
  items: string[];
  className?: string;
}

export default function BulletList({ items, className = "" }: BulletListProps) {
  return (
    <ul className={`space-y-5 ${className}`}>
      {items.map((item) => (
        <li key={item} className="flex gap-4 text-2xl leading-snug text-slate-700">
          <span className="mt-3 h-2.5 w-2.5 flex-none rounded-full bg-pe-teal" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}
