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
    <header className="mb-8 border-b border-hair pb-6 sm:mb-10">
      {eyebrow ? (
        <p className="mb-3 text-xs font-medium uppercase tracking-[0.16em] text-accent">
          {eyebrow}
        </p>
      ) : null}
      <h1 className="max-w-3xl font-serif text-3xl font-medium tracking-tight text-ink sm:text-5xl">{title}</h1>
      {intro ? (
        <p className="mt-4 max-w-2xl leading-relaxed text-ink-muted">{intro}</p>
      ) : null}
    </header>
  );
}
