import { exportUrl } from "../../api/export.ts";
import { BUTTON_SECONDARY, Card } from "./Card.tsx";

export default function DataCard() {
  return (
    <Card title="Your data">
      <p className="mb-3 text-sm text-slate-600 dark:text-slate-400">
        Download everything as CSV files in a ZIP: daily values, scores, sleep, workouts, journal,
        profile and AI notes. Google credentials are never included.
      </p>
      <div className="flex flex-wrap gap-2">
        <a className={BUTTON_SECONDARY} href={exportUrl(false)} download>
          Download daily data
        </a>
        <a className={BUTTON_SECONDARY} href={exportUrl(true)} download>
          Download with intraday data (large)
        </a>
      </div>
      <p className="mt-3 text-xs text-slate-500">
        Backups: run <code>fitbit db backup</code> for a full copy of the database in <code>data/backups</code>.
      </p>
    </Card>
  );
}
