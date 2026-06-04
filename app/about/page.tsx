import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { PageHeader } from "@/components/PageHeader";
import { site } from "@/lib/site";
import { age } from "@/lib/format";

export const metadata: Metadata = { title: "About" };

const capabilities = [
  {
    title: "Quantitative strategy R&D",
    body: "Development of strategies using GP algorithms, realistic backtesting, cost modeling, and out-of-sample validation.",
  },
  {
    title: "High-performance systems",
    body: "Optimizing high-performance engines.",
  },
  {
    title: "Conceptual and abstract reasoning",
    body: "Reasoning about complex systems, identifying their core principles and using those insights to design better solutions.",
  },
];

const specs: { label: string; value: ReactNode }[] = [
  { label: "Focus", value: "Quantitative work & software" },
  { label: "Based in", value: "Belgium" },
  { label: "Status", value: "Open to opportunities" },
  { label: "Flagship", value: <Link href="/astralanx" className="text-accent hover:underline">Astralanx</Link> },
];

export default function AboutPage() {
  return (
    <div>
      <PageHeader eyebrow="About" title="Bio & Skills" />

      {/* Hero — framed like a product header: photo, positioning, CTAs. */}
      <section className="panel p-8">
        <div className="grid gap-8 sm:grid-cols-[200px_1fr] sm:items-center">
          {/* Profile photo — circular, with a soft accent glow behind it.
              Replace public/profile.png with a real square photo (same path). */}
          <div className="relative mx-auto w-44 sm:mx-0 sm:w-full">
            <div
              aria-hidden
              className="absolute -inset-3 rounded-full bg-gradient-to-br from-accent/40 via-accent/10 to-transparent blur-2xl"
            />
            {/* eslint-disable-next-line @next/next/no-img-element -- local static asset, fixed size */}
            <img
              src="/profile.png"
              alt="Profile photo"
              width={200}
              height={200}
              className="relative aspect-square w-full rounded-full object-cover ring-2 ring-accent/60 ring-offset-4 ring-offset-panel"
            />
          </div>

          <div>
            <p className="font-mono text-xs uppercase tracking-widest text-accent">
              Quantitative research · Systems engineering
            </p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight">
              <span className="bg-gradient-to-r from-accent to-ink bg-clip-text text-transparent">
                Arne Vercauteren
              </span>
            </h2>
            <p className="mt-1 text-sm text-ink-muted">
              {age(site.birthDate)} years old
            </p>
            <p className="mt-3 max-w-prose leading-relaxed text-ink-muted">
              Developer with a focus on systematic strategy development and high-performance software.
            </p>

            <div className="mt-5 flex flex-wrap gap-2">
              {["Strategy research", "Python · C# · Java" ].map(
                (tag) => (
                  <span
                    key={tag}
                    className="rounded-full border border-accent/30 bg-accent/[0.06] px-3 py-1 font-mono text-[11px] uppercase tracking-wider text-ink-muted"
                  >
                    {tag}
                  </span>
                ),
              )}
            </div>

            <div className="mt-6 flex flex-wrap gap-3">
              <Link
                href="/contact"
                className="inline-flex items-center gap-2 rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-[#0a0c10] transition-transform hover:-translate-y-0.5"
              >
                Get in touch
                <span aria-hidden>→</span>
              </Link>
              <Link
                href="/astralanx"
                className="inline-flex items-center gap-2 rounded-lg border border-hair px-5 py-2.5 text-sm font-medium text-ink-muted transition-colors hover:border-accent/60 hover:text-ink"
              >
                Explore Astralanx
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Capabilities — the "what's on offer" feature grid. */}
      <section className="mt-10">
        <h2 className="font-mono text-xs uppercase tracking-widest text-accent">
          What I do
        </h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {capabilities.map((c) => (
            <div key={c.title} className="panel panel-hover p-6">
              <h3 className="font-semibold text-ink">{c.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-ink-muted">
                {c.body}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* At a glance — a product spec sheet. */}
      <section className="mt-10">
        <h2 className="font-mono text-xs uppercase tracking-widest text-accent">
          At a glance
        </h2>
        <dl className="mt-4 grid grid-cols-1 gap-px overflow-hidden rounded-lg border border-hair bg-hair sm:grid-cols-2">
          {specs.map((s) => (
            <div
              key={s.label}
              className="flex items-baseline justify-between gap-4 bg-panel px-5 py-4"
            >
              <dt className="font-mono text-xs uppercase tracking-wider text-ink-muted">
                {s.label}
              </dt>
              <dd className="text-right text-sm text-ink">{s.value}</dd>
            </div>
          ))}
        </dl>
      </section>

      {/* Contact — the call to action. */}
      <section className="mt-10 panel border-accent/25 bg-accent/[0.06] p-8">
        <h2 className="text-xl font-semibold text-ink">Get in touch</h2>
        <p className="mt-2 max-w-prose text-sm leading-relaxed text-ink-muted">
          For inquiries about Astralanx or other work, email is the best way to
          reach me.
        </p>
        <div className="mt-5 flex flex-wrap gap-3">
          <a
            href={`mailto:${site.email}`}
            className="inline-flex items-center gap-2 rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-[#0a0c10] transition-transform hover:-translate-y-0.5"
          >
            Send an email
            <span aria-hidden>→</span>
          </a>
          <Link
            href="/contact"
            className="inline-flex items-center gap-2 rounded-lg border border-hair px-5 py-2.5 text-sm font-medium text-ink-muted transition-colors hover:border-accent/60 hover:text-ink"
          >
            Contact page
          </Link>
        </div>
      </section>
    </div>
  );
}
