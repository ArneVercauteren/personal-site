import Link from "next/link";
import { site } from "@/lib/site";

// Featured — the core of the site.
const featured = [
  {
    href: "/darwin",
    eyebrow: "Project",
    label: "Darwin",
    blurb:
      "A system for evolving stock-picking strategies — how it works and what it has found.",
  },
  {
    href: "/darwin/live",
    eyebrow: "Live · simulated",
    label: "Live",
    blurb: "A simulated portfolio running a few of those strategies.",
  },
];

// Secondary — essays, reading recommendations, then bio.
const secondary = [
  {
    href: "/writing",
    label: "Writing",
    blurb: "Occasional essays and notes.",
  },
  {
    href: "/reading",
    label: "Reading",
    blurb: "Books I recommend.",
  },
  {
    href: "/about",
    label: "About",
    blurb: "A short bio.",
  },
];

export default function HomePage() {
  return (
    <div>
      {/* Hero — quant-terminal kicker, oversized identity line, two CTAs. */}
      <section className="relative border-b border-hair pb-14">
        <p className="mb-5 inline-flex items-center gap-2 font-mono text-xs uppercase tracking-widest text-accent">
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-75" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-accent" />
          </span>
          Software · Quantitative research
        </p>

        <h1 className="max-w-prose text-4xl font-semibold leading-[1.05] tracking-tight text-ink sm:text-5xl">
          {site.tagline}
          <span className="text-accent">.</span>
        </h1>

        <p className="mt-6 max-w-prose text-lg leading-relaxed text-ink-muted">
          This site documents my software projects, essays, and other
          non-software work. Chief among them is{" "}
          <span className="text-ink">Darwin</span>, a system for synthesizing
          stock-picking strategies — and the simulated paper portfolio it runs
          live.
        </p>

        <div className="mt-8 flex flex-wrap items-center gap-3">
          <Link
            href="/darwin"
            className="inline-flex items-center gap-2 rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-[#0a0c10] shadow-sm transition-transform hover:-translate-y-0.5"
          >
            Explore Darwin
            <span aria-hidden>→</span>
          </Link>
          <Link
            href="/darwin/live"
            className="inline-flex items-center gap-2 rounded-lg border border-hair px-5 py-2.5 text-sm font-semibold text-ink-muted transition-colors hover:border-accent/60 hover:text-ink"
          >
            View the live portfolio
          </Link>
        </div>
      </section>

      {/* Featured: Darwin + Live carry the most weight. */}
      <section className="mt-12 grid gap-4 sm:grid-cols-2">
        {featured.map((s, i) => (
          <Link
            key={s.href}
            href={s.href}
            className="panel panel-hover group relative flex flex-col gap-3 overflow-hidden p-8 ring-1 ring-inset ring-accent/20"
          >
            {/* Hairline accent that lights up on hover. */}
            <span
              aria-hidden
              className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent/40 to-transparent opacity-0 transition-opacity group-hover:opacity-100"
            />
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase tracking-widest text-accent">
                {s.eyebrow}
              </span>
              <span className="font-mono text-[10px] text-hair">
                0{i + 1}
              </span>
            </div>
            <span className="text-2xl font-semibold text-ink group-hover:text-accent">
              {s.label}
            </span>
            <span className="text-ink-muted">{s.blurb}</span>
            <span className="mt-auto inline-flex items-center gap-1 pt-2 font-mono text-sm text-ink-muted transition-all group-hover:gap-2 group-hover:text-accent">
              <span>Open</span>
              <span aria-hidden>→</span>
            </span>
          </Link>
        ))}
      </section>

      {/* Secondary: essays, reading, bio. */}
      <section className="mt-4 grid gap-4 sm:grid-cols-3">
        {secondary.map((s) => (
          <Link
            key={s.href}
            href={s.href}
            className="panel panel-hover group flex flex-col gap-2 p-6"
          >
            <span className="flex items-center justify-between text-base font-semibold text-ink group-hover:text-accent">
              {s.label}
              <span
                aria-hidden
                className="font-mono text-sm text-hair transition-all group-hover:translate-x-0.5 group-hover:text-accent"
              >
                →
              </span>
            </span>
            <span className="text-sm text-ink-muted">{s.blurb}</span>
          </Link>
        ))}
      </section>
    </div>
  );
}
