import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";
import { ContentList } from "@/components/ContentList";
import { getAllContent } from "@/lib/content";

export const metadata: Metadata = { title: "Writing" };

export default function WritingPage() {
  const essays = getAllContent("essays");
  return (
    <div>
      <PageHeader
        eyebrow="Writing"
        title="Essays"
        intro="Essays and notes on various topics."
      />
      <ContentList
        items={essays}
        basePath="/writing"
        empty="No essays yet."
      />
    </div>
  );
}
