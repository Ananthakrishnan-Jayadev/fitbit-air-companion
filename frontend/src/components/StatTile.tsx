import type { ReactNode } from "react";

interface StatTileProps {
  label: string;
  value: string;
  unit?: string;
  detail?: ReactNode;
}

export default function StatTile({ label, value, unit, detail }: StatTileProps) {
  return (
    <div className="rounded-lg border border-stone-200 bg-white p-4 dark:border-stone-800 dark:bg-stone-900">
      <div className="text-sm text-stone-600 dark:text-stone-400">{label}</div>
      <div className="mt-1 text-2xl font-semibold">
        {value}
        {unit && <span className="ml-1 text-sm font-normal text-stone-500">{unit}</span>}
      </div>
      {detail && <div className="mt-1 text-xs text-stone-500 dark:text-stone-400">{detail}</div>}
    </div>
  );
}
