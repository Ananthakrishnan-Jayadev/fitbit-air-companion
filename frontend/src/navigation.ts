export interface NavItem {
  path: string;
  label: string;
  // Phase in development-plan.md that builds this page.
  phase: number;
  description: string;
}

export const NAV_ITEMS: readonly NavItem[] = [
  { path: "/", label: "Today", phase: 3, description: "Recovery, sleep and strain at a glance." },
  { path: "/heart", label: "Heart", phase: 3, description: "Intraday heart rate, HRV and resting HR." },
  { path: "/sleep", label: "Sleep", phase: 3, description: "Stages, SpO2 and skin temperature overnight." },
  { path: "/activity", label: "Activity", phase: 3, description: "Steps, zones, stress and workouts." },
  { path: "/body", label: "Body", phase: 6, description: "Weight and body fat from your smart scale." },
  { path: "/trends", label: "Trends", phase: 3, description: "Any metric against your personal baseline." },
  { path: "/journal", label: "Journal", phase: 5, description: "Daily tags and what affects you." },
  { path: "/coach", label: "Coach", phase: 4, description: "Chat with your local AI coach." },
  { path: "/settings", label: "Settings", phase: 2, description: "Connections, sync and profile." },
];
