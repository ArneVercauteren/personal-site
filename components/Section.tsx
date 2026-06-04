import type { ReactNode } from "react";

// A titled content block with an eyebrow label, separated by a hairline rule.
// Shared by the strategy detail and analytics pages so their rhythm matches.
export function Section({
  eyebrow,
  title,
  id,
  intro,
  children,
}: {
  eyebrow: string;
  title: string;
  id?: string;
  intro?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section id={id} className="mt-10 scroll-mt-24 border-t border-hair pt-8">
      <p className="mb-1 font-mono text-xs uppercase tracking-widest text-accent">
        {eyebrow}
      </p>
      <h2 className="text-xl font-semibold tracking-tight text-ink">{title}</h2>
      {intro ? (
        <p className="mt-2 max-w-prose text-sm text-ink-muted">{intro}</p>
      ) : null}
      <div className="mt-4">{children}</div>
    </section>
  );
}
