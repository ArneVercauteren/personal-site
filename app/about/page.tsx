import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { PageHeader } from "@/components/PageHeader";
import { site } from "@/lib/site";
import { age } from "@/lib/format";

export const metadata: Metadata = { title: "About" };

const capabilities = [
  { title: "Quantitative strategy R&D", body: "Development of strategies using GP algorithms, realistic backtesting, cost modeling, and out-of-sample validation." },
  { title: "High-performance systems", body: "Optimizing high-performance engines." },
  { title: "Conceptual and abstract reasoning", body: "Reasoning about complex systems, identifying their core principles and using those insights to design better solutions." },
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

      <section className="grid gap-8 border-b border-hair pb-10 sm:grid-cols-[11rem_1fr] sm:items-center sm:gap-12">
        {/* eslint-disable-next-line @next/next/no-img-element -- local static asset, fixed size */}
        <img src="/profile.png" alt="Profile photo" width={200} height={200} className="aspect-square w-36 rounded-full object-cover ring-1 ring-hair sm:w-44" />
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.16em] text-accent">Quantitative research · Systems engineering</p>
          <h2 className="mt-3 font-serif text-4xl font-medium tracking-tight text-ink">Arne Vercauteren</h2>
          <p className="mt-1 text-sm text-ink-muted">{age(site.birthDate)} years old</p>
          <p className="mt-4 max-w-prose leading-relaxed text-ink-muted">Developer with a focus on systematic strategy development and high-performance software.</p>
          <div className="mt-5 flex flex-wrap gap-x-5 gap-y-2 text-sm text-ink-muted">
            <span>Strategy research</span><span>Python · C# · Java</span>
          </div>
          <div className="mt-6 flex flex-wrap gap-x-6 gap-y-3 text-sm font-medium">
            <Link href="/contact" className="text-ink underline decoration-accent decoration-2 underline-offset-4 hover:text-accent">Get in touch</Link>
            <Link href="/astralanx" className="text-ink-muted hover:text-ink">Explore Astralanx</Link>
          </div>
        </div>
      </section>

      <section className="mt-10">
        <h2 className="text-xs font-medium uppercase tracking-[0.16em] text-accent">What I do</h2>
        <div className="mt-4 divide-y divide-hair border-y border-hair">
          {capabilities.map((capability) => (
            <div key={capability.title} className="grid gap-2 py-5 sm:grid-cols-[15rem_1fr] sm:gap-8">
              <h3 className="font-semibold text-ink">{capability.title}</h3>
              <p className="max-w-xl leading-relaxed text-ink-muted">{capability.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-10">
        <h2 className="text-xs font-medium uppercase tracking-[0.16em] text-accent">At a glance</h2>
        <dl className="mt-4 divide-y divide-hair border-y border-hair sm:grid sm:grid-cols-2 sm:divide-x sm:divide-y-0">
          {specs.map((spec) => (
            <div key={spec.label} className="flex items-baseline justify-between gap-4 px-0 py-4 sm:px-5">
              <dt className="text-xs font-medium uppercase tracking-[0.14em] text-ink-muted">{spec.label}</dt>
              <dd className="text-right text-sm text-ink">{spec.value}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="mt-10 border-t border-hair pt-8">
        <h2 className="font-serif text-2xl font-medium text-ink">Get in touch</h2>
        <p className="mt-2 max-w-prose text-sm leading-relaxed text-ink-muted">For inquiries about Astralanx or other work, email is the best way to reach me.</p>
        <div className="mt-5 flex flex-wrap gap-x-6 gap-y-3 text-sm font-medium">
          <a href={`mailto:${site.email}`} className="text-ink underline decoration-accent decoration-2 underline-offset-4 hover:text-accent">Send an email</a>
          <Link href="/contact" className="text-ink-muted hover:text-ink">Contact page</Link>
        </div>
      </section>
    </div>
  );
}
