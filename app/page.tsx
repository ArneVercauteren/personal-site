import type { Metadata } from "next";
import Link from "next/link";
import { site } from "@/lib/site";

export const metadata: Metadata = { alternates: { canonical: "/" } };

const featured = [
  {
    href: "/astralanx",
    eyebrow: "Project",
    label: "Astralanx",
    blurb: "A GP system for synthesizing long-term stock-picking strategies.",
  },
  {
    href: "/astralanx/live",
    eyebrow: "Live · simulated",
    label: "Live",
    blurb: "A simulated portfolio running strategies from Astralanx.",
  },
];

const secondary = [
  { href: "/writing", label: "Writing", blurb: "Occasional essays and notes." },
  { href: "/reading", label: "Reading list", blurb: "Books I recommend." },
  { href: "/about", label: "About", blurb: "A short bio." },
];

export default function HomePage() {
  return (
    <div>
      <section className="border-b border-hair pb-12 pt-3 sm:pb-16 sm:pt-8">
        <p className="mb-5 text-xs font-medium uppercase tracking-[0.16em] text-accent">
          Software · Quantitative research
        </p>
        <h1 className="max-w-4xl text-4xl font-semibold leading-[1.04] tracking-[-0.045em] text-ink sm:text-6xl">
          {site.tagline}
          <span className="text-accent">.</span>
        </h1>
        <p className="mt-6 max-w-2xl text-lg leading-relaxed text-ink-muted sm:text-xl">
          This site documents my software projects, essays, and other non-software work. My main project is{" "}
          <span className="text-ink">Astralanx</span>, a system for synthesizing long-term stock-picking strategies.
        </p>
        <div className="mt-8 flex flex-wrap gap-x-6 gap-y-3 text-sm font-medium">
          <Link href="/astralanx" className="text-ink underline decoration-accent decoration-2 underline-offset-4 hover:text-accent">
            Explore Astralanx
          </Link>
          <Link href="/astralanx/live" className="text-ink-muted transition-colors hover:text-ink">
            View the live portfolio <span aria-hidden>→</span>
          </Link>
        </div>
      </section>

      <section className="mt-10 sm:mt-14" aria-label="Featured work">
        <div className="divide-y divide-hair border-y border-hair">
          {featured.map((item) => (
            <Link key={item.href} href={item.href} className="group grid gap-2 py-6 transition-colors hover:bg-panel sm:grid-cols-[10rem_1fr_auto] sm:items-baseline sm:gap-6 sm:px-4">
              <span className="text-xs font-medium uppercase tracking-[0.14em] text-accent">{item.eyebrow}</span>
              <span>
                <span className="text-xl font-semibold tracking-tight text-ink group-hover:text-accent">{item.label}</span>
                <span className="mt-1 block max-w-xl leading-relaxed text-ink-muted">{item.blurb}</span>
              </span>
              <span className="hidden text-sm text-ink-muted transition-transform group-hover:translate-x-1 sm:block">Open <span aria-hidden>→</span></span>
            </Link>
          ))}
        </div>
      </section>

      <section className="mt-8 grid gap-0 divide-y divide-hair border-y border-hair sm:grid-cols-3 sm:divide-x sm:divide-y-0">
        {secondary.map((item) => (
          <Link key={item.href} href={item.href} className="group px-0 py-5 transition-colors hover:bg-panel sm:px-5">
            <span className="text-base font-semibold tracking-tight text-ink group-hover:text-accent">{item.label}</span>
            <span className="mt-1 block text-sm leading-relaxed text-ink-muted">{item.blurb}</span>
          </Link>
        ))}
      </section>
    </div>
  );
}
