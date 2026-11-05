import { Link } from "react-router-dom";
import { askHref } from "../coach.ts";
import { ArrowRight } from "./icons.tsx";

const PLAIN =
  "text-stone-600 hover:text-stone-900 hover:underline dark:text-stone-400 dark:hover:text-stone-100";
// On a coloured field (a sleeve) the link takes the field's own text colour.
const ON_FIELD = "underline decoration-1 hover:decoration-2";

/** "Ask about this" → the Coach page with a prepared question. */
export default function AskLink({
  question,
  label = "Ask the coach",
  onField = false,
}: {
  question: string;
  label?: string;
  onField?: boolean;
}) {
  return (
    <Link
      to={askHref(question)}
      className={`inline-flex shrink-0 items-center gap-1 text-xs font-medium ${onField ? ON_FIELD : PLAIN}`}
    >
      {label}
      <ArrowRight className="h-3.5 w-3.5" />
    </Link>
  );
}
