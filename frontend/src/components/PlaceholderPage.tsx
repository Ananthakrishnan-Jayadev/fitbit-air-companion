import type { NavItem } from "../navigation.ts";

export default function PlaceholderPage({ item }: { item: NavItem }) {
  return (
    <section>
      <h1 className="text-2xl font-semibold tracking-tight">{item.label}</h1>
      <p className="mt-1 text-slate-600 dark:text-slate-400">{item.description}</p>
      <div className="mt-6 rounded-lg border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
        Coming in Phase {item.phase}.
      </div>
    </section>
  );
}
