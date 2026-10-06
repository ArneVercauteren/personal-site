import "server-only";
import fs from "node:fs";
import path from "node:path";
import matter from "gray-matter";

export type ContentType = "essays" | "projects";

export interface Frontmatter {
  title: string;
  summary: string;
  /** ISO date, YYYY-MM-DD. */
  date: string;
  tags?: string[];
  /** Drafts are excluded from listings and from static params. */
  draft?: boolean;
}

export interface ContentMeta {
  slug: string;
  frontmatter: Frontmatter;
}

export interface ContentDoc extends ContentMeta {
  /** Raw MDX body (frontmatter stripped). */
  body: string;
}

function contentDir(type: ContentType): string {
  return path.join(process.cwd(), "content", type);
}

function readSlugs(type: ContentType): string[] {
  const dir = contentDir(type);
  if (!fs.existsSync(dir)) return [];
  return fs
    .readdirSync(dir)
    .filter((f) => f.endsWith(".mdx"))
    .map((f) => f.replace(/\.mdx$/, ""));
}

/** All non-draft entries of a type, newest first. */
export function getAllContent(type: ContentType): ContentMeta[] {
  return readSlugs(type)
    .map((slug) => {
      const raw = fs.readFileSync(
        path.join(contentDir(type), `${slug}.mdx`),
        "utf8",
      );
      const { data } = matter(raw);
      return { slug, frontmatter: data as Frontmatter };
    })
    .filter((c) => !c.frontmatter.draft)
    .sort((a, b) => b.frontmatter.date.localeCompare(a.frontmatter.date));
}

/** A single doc by slug, or null if missing. */
export function getContentBySlug(
  type: ContentType,
  slug: string,
): ContentDoc | null {
  const file = path.join(contentDir(type), `${slug}.mdx`);
  if (!fs.existsSync(file)) return null;
  const { data, content } = matter(fs.readFileSync(file, "utf8"));
  return { slug, frontmatter: data as Frontmatter, body: content };
}

export interface StrategyNote {
  title: string;
  /** ISO date, YYYY-MM-DD. */
  date: string;
  /** Plain-text paragraphs, split on blank lines. */
  paragraphs: string[];
}

/**
 * Editorial commentary on a deployed strategy, from
 * `content/strategy-notes/<id>.md`. Kept outside the strategy spec because the
 * spec is covered by the deployment bundle hash.
 */
export function getStrategyNote(id: string): StrategyNote | null {
  const file = path.join(process.cwd(), "content", "strategy-notes", `${id}.md`);
  if (!fs.existsSync(file)) return null;
  const { data, content } = matter(fs.readFileSync(file, "utf8"));
  const paragraphs = content
    .split(/\n\s*\n/)
    .map((p) => p.trim().replace(/\s+/g, " "))
    .filter(Boolean);
  // YAML parses bare dates into Date objects; normalize back to YYYY-MM-DD.
  const date =
    data.date instanceof Date ? data.date.toISOString().slice(0, 10) : String(data.date);
  return { title: data.title, date, paragraphs };
}
