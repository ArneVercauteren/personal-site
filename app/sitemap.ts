import type { MetadataRoute } from "next";
import { loadStrategyIndex } from "@/lib/data";
import { site } from "@/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  const routes = ["", "/about", "/astralanx", "/astralanx/live", "/writing", "/reading", "/contact"];
  const strategies = loadStrategyIndex().strategies.flatMap((strategy) => [
    `/astralanx/live/${strategy.id}`,
    `/astralanx/live/${strategy.id}/analytics`,
  ]);
  return [...routes, ...strategies].map((route) => ({
    url: new URL(route || "/", site.url).toString(),
    changeFrequency: route.includes("/live") ? "daily" : "monthly",
  }));
}
