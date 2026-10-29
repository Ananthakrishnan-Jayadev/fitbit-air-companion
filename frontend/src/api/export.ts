/** Download links (plain navigation; the browser saves the ZIP). */
export function exportUrl(intraday: boolean): string {
  return `/api/export${intraday ? "?intraday=true" : ""}`;
}
