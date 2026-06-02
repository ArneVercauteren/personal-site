import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Contact",
  description: `Get in touch with ${site.name} by email.`,
};

export default function ContactPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Contact"
        title="Get in touch"
        intro="For inquiries about Darwin or other work, email is the best way to reach me."
      />

      <section className="panel border-accent/25 bg-accent/[0.06] p-8">
        <h2 className="font-mono text-xs uppercase tracking-widest text-accent">
          Email
        </h2>
        <p className="mt-2 max-w-prose text-sm leading-relaxed text-ink-muted">
          The quickest way to reach me. The button below opens a draft in your
          mail client.
        </p>

        <div className="mt-6">
          <a
            href={`mailto:${site.email}`}
            className="inline-flex items-center gap-2 rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-[#0a0c10] transition-transform hover:-translate-y-0.5"
          >
            Send an email
            <span aria-hidden>→</span>
          </a>
        </div>
      </section>
    </div>
  );
}
