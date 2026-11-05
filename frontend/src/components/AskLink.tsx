import { Link } from "react-router-dom";
import { askHref } from "../coach.ts";
import { ArrowRight } from "./icons.tsx";

/** "Ask about this" → the Coach page with a prepared question. */
export default function AskLink({ question, label = "Ask the coach" }: { question: string; label?: string }) {
  return (
    <Link
      to={askHref(question)}
      className="inline-flex shrink-0 items-center gap-1 text-xs text-stone-600 hover:text-stone-900 hover:underline dark:text-stone-400 dark:hover:text-stone-100"
    >
      {label}
      <ArrowRight className="h-3.5 w-3.5" />
    </Link>
  );
}
