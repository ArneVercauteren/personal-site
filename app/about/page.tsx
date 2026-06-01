import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";

export const metadata: Metadata = { title: "About" };

export default function AboutPage() {
  return (
    <div>
      <PageHeader
        eyebrow="About"
        title="Bio & résumé"
        intro="A short bio and a résumé."
      />
      <p className="max-w-prose text-ink-muted">
        A fuller bio and a downloadable résumé will go here.
      </p>
    </div>
  );
}
