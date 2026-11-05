import type { NavItem } from "../navigation.ts";

export default function PlaceholderPage({ item }: { item: NavItem }) {
  return (
    <section>
      <h1 className="page-title">{item.label}</h1>
      <p className="mt-1 text-stone-600 dark:text-stone-400">{item.description}</p>
      <div className="mt-6 rounded-lg border border-dashed border-stone-300 p-8 text-center text-sm text-stone-500 dark:border-stone-700 dark:text-stone-400">
        Coming in Phase {item.phase}.
      </div>
    </section>
  );
}
