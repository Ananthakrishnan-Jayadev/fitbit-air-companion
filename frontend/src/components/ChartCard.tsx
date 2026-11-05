import { useState, type ReactNode } from "react";
import AskLink from "./AskLink.tsx";

export interface TableData {
  columns: string[];
  rows: (string | number)[][];
}

interface ChartCardProps {
  title: string;
  subtitle?: string;
  table?: TableData;
  /** Question prefilled on the Coach page by the "Ask the coach" link. */
  ask?: string;
  /** Extra controls in the header (e.g. "Show whole day" on a zoomed chart). */
  actions?: ReactNode;
  children: ReactNode;
}

/** A chart with a title and a table-view twin (every value readable without the chart). */
export default function ChartCard({ title, subtitle, table, ask, actions, children }: ChartCardProps) {
  const [showTable, setShowTable] = useState(false);
  return (
    <section className="rounded-lg border border-stone-200 bg-white p-4 dark:border-stone-800 dark:bg-stone-900">
      <header className="mb-2 flex items-start justify-between gap-4">
        <div>
          <h2 className="font-condensed text-[1.35rem] font-extrabold uppercase leading-none">{title}</h2>
          {subtitle && <p className="text-xs text-stone-500 dark:text-stone-400">{subtitle}</p>}
        </div>
        <div className="flex shrink-0 items-center gap-3">
          {actions}
          {ask && <AskLink question={ask} />}
          {table && table.rows.length > 0 && (
            <button
              type="button"
              className="text-xs text-stone-500 underline hover:text-stone-800 dark:hover:text-stone-200"
              onClick={() => setShowTable((v) => !v)}
            >
              {showTable ? "Show chart" : "Show table"}
            </button>
          )}
        </div>
      </header>
      {showTable && table ? <DataTable data={table} /> : children}
    </section>
  );
}

export function DataTable({ data }: { data: TableData }) {
  return (
    <div className="max-h-80 overflow-auto">
      <table className="w-full text-left text-sm tabular-nums">
        <thead className="sticky top-0 bg-white text-xs uppercase text-stone-500 dark:bg-stone-900">
          <tr>
            {data.columns.map((c) => (
              <th key={c} className="py-1 pr-4 font-medium">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-stone-100 dark:divide-stone-800">
          {data.rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j} className="py-1 pr-4">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
