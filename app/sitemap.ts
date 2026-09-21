import type { MetadataRoute } from "next";
import { getAllContent } from "@/lib/content";
import { loadStrategyIndex } from "@/lib/data";
import { site } from "@/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  const routes = ["", "/about", "/astralanx", "/astralanx/live", "/projects", "/writing", "/reading", "/contact"];
  const content = [
    ...getAllContent("essays").map(({ slug, frontmatter }) => ({
      route: `/writing/${slug}`,
      lastModified: frontmatter.date,
    })),
    ...getAllContent("projects").map(({ slug, frontmatter }) => ({
      route: `/projects/${slug}`,
      lastModified: frontmatter.date,
    })),
  ];
  const strategies = loadStrategyIndex().strategies.flatMap((strategy) => [
    { route: `/astralanx/live/${strategy.id}`, changeFrequency: "daily" as const },
    { route: `/astralanx/live/${strategy.id}/analytics`, changeFrequency: "daily" as const },
  ]);

  const pages: {
    route: string;
    lastModified?: string;
    changeFrequency: "daily" | "monthly";
  }[] = [
    ...routes.map((route) => ({ route, changeFrequency: "monthly" as const })),
    ...content.map(({ route, lastModified }) => ({ route, lastModified, changeFrequency: "monthly" as const })),
    ...strategies,
  ];

  return pages.map(({ route, lastModified, changeFrequency }) => ({
    url: new URL(route || "/", site.url).toString(),
    lastModified,
    changeFrequency,
  }));
}
