import type { ReactNode } from "react";

/*
 * Page width and the context side panel (design.md "Layout"). Pages grow to 100rem (1600px),
 * which fills a 1920px monitor beside the nav rail. From xl (1280px) a side panel sits to the
 * right of the main column and stays in view while the main column scrolls; below that it
 * stacks under the main content, so laptops and phones keep one column.
 */

export const PAGE_WIDTH = "max-w-[100rem]";

/** Shared look of side-panel blocks: a hairline box with a condensed heading. */
export const PANEL = "border border-stone-200 bg-white p-4 dark:border-stone-800 dark:bg-stone-900";
export const PANEL_TITLE = "mb-3 font-condensed text-[1.35rem] font-extrabold uppercase leading-none";

export function Page({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`${PAGE_WIDTH} ${className}`}>{children}</div>;
}

export function WithAside({
  children,
  aside,
  label,
}: {
  children: ReactNode;
  aside: ReactNode;
  /** Accessible name of the side panel, e.g. "Sleep history". */
  label: string;
}) {
  return (
    <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_22rem] 2xl:grid-cols-[minmax(0,1fr)_25rem]">
      <div className="min-w-0">{children}</div>
      <aside aria-label={label} className="grid min-w-0 content-start gap-6 xl:sticky xl:top-6 xl:self-start">
        {aside}
      </aside>
    </div>
  );
}

export function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className={PANEL}>
      <h2 className={PANEL_TITLE}>{title}</h2>
      {children}
    </section>
  );
}
