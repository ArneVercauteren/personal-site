import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";

export const metadata: Metadata = { title: "Studio" };

export default function StudioPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Studio"
        title="Music & art"
        intro="Music and art."
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="panel p-5">
          <h2 className="font-mono text-sm font-semibold text-ink">Music</h2>
          <p className="mt-2 text-sm text-ink-muted">Recordings will go here.</p>
        </div>
        <div className="panel p-5">
          <h2 className="font-mono text-sm font-semibold text-ink">Art</h2>
          <p className="mt-2 text-sm text-ink-muted">Images will go here.</p>
        </div>
      </div>
    </div>
  );
}
