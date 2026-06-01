import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PageHeader } from "@/components/PageHeader";
import { Mdx } from "@/components/Mdx";
import { getAllContent, getContentBySlug } from "@/lib/content";

export function generateStaticParams() {
  return getAllContent("projects").map((c) => ({ slug: c.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const doc = getContentBySlug("projects", slug);
  if (!doc) return {};
  return { title: doc.frontmatter.title, description: doc.frontmatter.summary };
}

export default async function ProjectPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const doc = getContentBySlug("projects", slug);
  if (!doc) notFound();

  return (
    <div>
      <PageHeader
        eyebrow="Project"
        title={doc.frontmatter.title}
        intro={doc.frontmatter.summary}
      />
      <Mdx source={doc.body} />
    </div>
  );
}
