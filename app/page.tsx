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

// Secondary — essays, then bio.
const secondary = [
  {
    href: "/writing",
    label: "Writing",
    blurb: "Occasional essays and notes.",
    wide: true,
  },
  {
    href: "/about",
    label: "About",
    blurb: "A short bio and a résumé.",
    wide: false,
  },
];

// Tertiary — the rest.
const tertiary = [
  { href: "/studio", label: "Studio", blurb: "Music and art." },
  { href: "/projects", label: "Projects", blurb: "Other things I've worked on." },
];

export default function HomePage() {
  return (
    <div>
      <section className="border-b border-hair pb-12">
        <h1 className="max-w-prose text-3xl font-semibold leading-tight tracking-tight text-ink sm:text-4xl">
          {site.tagline}
        </h1>
        <p className="mt-5 max-w-prose text-lg text-ink-muted">
          This site documents my software projects, essays, and other
          non-software projects. These include{" "}
          <span className="text-ink">Darwin</span>, a system for synthesizing
          stock-picking strategies, and the simulated paper portfolio it runs.
        </p>
      </section>

      {/* Featured: Darwin + Live carry the most weight. */}
      <section className="mt-12 grid gap-4 sm:grid-cols-2">
        {featured.map((s) => (
          <Link
            key={s.href}
            href={s.href}
            className="panel panel-hover group flex flex-col gap-3 p-8 ring-1 ring-inset ring-accent/20"
          >
            <span className="font-mono text-[10px] uppercase tracking-widest text-accent">
              {s.eyebrow}
            </span>
            <span className="text-2xl font-semibold text-ink group-hover:text-accent">
              {s.label}
            </span>
            <span className="text-ink-muted">{s.blurb}</span>
            <span className="mt-auto pt-2 font-mono text-sm text-ink-muted group-hover:text-accent">
              →
            </span>
          </Link>
        ))}
      </section>

      {/* Secondary: essays (wider), then bio. */}
      <section className="mt-4 grid gap-4 sm:grid-cols-3">
        {secondary.map((s) => (
          <Link
            key={s.href}
            href={s.href}
            className={`panel panel-hover group flex flex-col gap-2 p-6 ${
              s.wide ? "sm:col-span-2" : ""
            }`}
          >
            <span className="text-base font-semibold text-ink group-hover:text-accent">
              {s.label}
            </span>
            <span className="text-sm text-ink-muted">{s.blurb}</span>
          </Link>
        ))}
      </section>

      {/* Tertiary: quietest. */}
      <section className="mt-4 grid gap-4 sm:grid-cols-2">
        {tertiary.map((s) => (
          <Link
            key={s.href}
            href={s.href}
            className="panel panel-hover group flex items-baseline justify-between gap-3 p-4"
          >
            <span className="text-sm font-medium text-ink-muted group-hover:text-ink">
              {s.label}
            </span>
            <span className="text-xs text-ink-muted">{s.blurb}</span>
          </Link>
        ))}
      </section>
    </div>
  );
}
