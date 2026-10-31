// Links into the Coach page and suggested follow-up questions (pure helpers).

/** The Coach page with `question` prefilled in the input (never auto-sent). */
export function askHref(question: string): string {
  return `/coach?q=${encodeURIComponent(question)}`;
}

const FOLLOW_UPS: { match: RegExp; questions: string[] }[] = [
  {
    match: /sleep|bed|rem|deep|night/i,
    questions: [
      "What would most improve my deep sleep?",
      "How consistent has my bedtime been lately?",
      "How did this week's sleep compare with last week?",
    ],
  },
  {
    match: /heart|hrv|resting|pulse/i,
    questions: [
      "How has my resting heart rate trended this month?",
      "What tends to lower my HRV?",
      "Is today's HRV unusual for me?",
    ],
  },
  {
    match: /strain|train|workout|exercise|run|active|steps/i,
    questions: [
      "How hard should I train tomorrow?",
      "How has my training load changed this month?",
      "Which workouts raise my strain the most?",
    ],
  },
  {
    match: /stress|calm|relax/i,
    questions: [
      "When in the day is my stress usually highest?",
      "Does my stress affect my sleep?",
      "What helps my stress come down?",
    ],
  },
];

const DEFAULT_FOLLOW_UPS = [
  "What affects my recovery the most?",
  "How did this week compare with last week?",
  "What should I focus on tomorrow?",
];

/** Three follow-up questions related to the user's last question. */
export function followUpsFor(question: string): string[] {
  return FOLLOW_UPS.find((group) => group.match.test(question))?.questions ?? DEFAULT_FOLLOW_UPS;
}
