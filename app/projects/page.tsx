import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";
import { ContentList } from "@/components/ContentList";
import { getAllContent } from "@/lib/content";

export const metadata: Metadata = { title: "Projects" };

export default function ProjectsPage() {
  const projects = getAllContent("projects");
  return (
    <div>
      <PageHeader
        eyebrow="Projects"
        title="Portfolio"
        intro="Other software and non-software work."
      />
      <ContentList
        items={projects}
        basePath="/projects"
        empty="No projects yet."
      />
    </div>
  );
}
