import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PageHeader } from "@/components/PageHeader";
import { Mdx } from "@/components/Mdx";
import { getAllContent, getContentBySlug } from "@/lib/content";
import { shortDate } from "@/lib/format";

export function generateStaticParams() {
  return getAllContent("essays").map((c) => ({ slug: c.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const doc = getContentBySlug("essays", slug);
  if (!doc) return {};
  return { title: doc.frontmatter.title, description: doc.frontmatter.summary };
}

export default async function EssayPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const doc = getContentBySlug("essays", slug);
  if (!doc) notFound();

  return (
    <div>
      <PageHeader
        eyebrow={shortDate(doc.frontmatter.date)}
        title={doc.frontmatter.title}
        intro={doc.frontmatter.summary}
      />
      <Mdx source={doc.body} />
    </div>
  );
}
