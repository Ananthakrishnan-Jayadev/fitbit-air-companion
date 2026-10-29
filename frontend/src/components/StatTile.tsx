import type { ReactNode } from "react";

interface StatTileProps {
  label: string;
  value: string;
  unit?: string;
  detail?: ReactNode;
}

export default function StatTile({ label, value, unit, detail }: StatTileProps) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <div className="text-sm text-slate-600 dark:text-slate-400">{label}</div>
      <div className="mt-1 text-2xl font-semibold">
        {value}
        {unit && <span className="ml-1 text-sm font-normal text-slate-500">{unit}</span>}
      </div>
      {detail && <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">{detail}</div>}
    </div>
  );
}
