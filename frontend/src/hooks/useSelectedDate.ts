import { useSearchParams } from "react-router-dom";

/** The `?date=YYYY-MM-DD` shared by all day pages; undefined means "latest". */
export function useSelectedDate(): [string | undefined, (date: string) => void] {
  const [params, setParams] = useSearchParams();
  const date = params.get("date") ?? undefined;
  return [date, (next: string) => setParams({ date: next })];
}
