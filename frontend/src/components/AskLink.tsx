import { Link } from "react-router-dom";
import { askHref } from "../coach.ts";

/** "Ask about this" → the Coach page with a prepared question. */
export default function AskLink({ question, label = "Ask the coach" }: { question: string; label?: string }) {
  return (
    <Link
      to={askHref(question)}
      className="shrink-0 text-xs text-slate-500 underline-offset-2 hover:text-slate-800 hover:underline dark:hover:text-slate-200"
    >
      {label} →
    </Link>
  );
}
