import { useState, type ReactNode } from "react";

export interface TableData {
  columns: string[];
  rows: (string | number)[][];
}

interface ChartCardProps {
  title: string;
  subtitle?: string;
  table?: TableData;
  children: ReactNode;
}

/** A chart with a title and a table-view twin (every value readable without the chart). */
export default function ChartCard({ title, subtitle, table, children }: ChartCardProps) {
  const [showTable, setShowTable] = useState(false);
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <header className="mb-2 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold">{title}</h2>
          {subtitle && <p className="text-xs text-slate-500 dark:text-slate-400">{subtitle}</p>}
        </div>
        {table && table.rows.length > 0 && (
          <button
            type="button"
            className="shrink-0 text-xs text-slate-500 underline hover:text-slate-800 dark:hover:text-slate-200"
            onClick={() => setShowTable((v) => !v)}
          >
            {showTable ? "Show chart" : "Show table"}
          </button>
        )}
      </header>
      {showTable && table ? <DataTable data={table} /> : children}
    </section>
  );
}

export function DataTable({ data }: { data: TableData }) {
  return (
    <div className="max-h-80 overflow-auto">
      <table className="w-full text-left text-sm tabular-nums">
        <thead className="sticky top-0 bg-white text-xs uppercase text-slate-500 dark:bg-slate-900">
          <tr>
            {data.columns.map((c) => (
              <th key={c} className="py-1 pr-4 font-medium">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
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
