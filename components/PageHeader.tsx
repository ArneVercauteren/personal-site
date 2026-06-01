export function PageHeader({
  eyebrow,
  title,
  intro,
}: {
  eyebrow?: string;
  title: string;
  intro?: string;
}) {
  return (
    <header className="mb-10 border-b border-hair pb-6">
      {eyebrow ? (
        <p className="mb-2 font-mono text-xs uppercase tracking-widest text-accent">
          {eyebrow}
        </p>
      ) : null}
      <h1 className="text-3xl font-semibold tracking-tight text-ink">{title}</h1>
      {intro ? (
        <p className="mt-3 max-w-prose text-ink-muted">{intro}</p>
      ) : null}
    </header>
  );
}
