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
      <PageHeader eyebrow="Contact" title="Get in touch" intro="For inquiries about Astralanx or other work, email is the best way to reach me." />
      <section className="max-w-2xl border-y border-hair py-8">
        <h2 className="text-xs font-medium uppercase tracking-[0.16em] text-accent">Email</h2>
        <p className="mt-3 max-w-prose leading-relaxed text-ink-muted">The quickest way to reach me. The button below opens a draft in your mail client.</p>
        <div className="mt-6">
          <a href={`mailto:${site.email}`} className="text-sm font-medium text-ink underline decoration-accent decoration-2 underline-offset-4 hover:text-accent">
            Send an email
          </a>
        </div>
      </section>
    </div>
  );
}
