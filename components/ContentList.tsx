import Link from "next/link";
import type { ContentMeta } from "@/lib/content";
import { shortDate } from "@/lib/format";

export function ContentList({
  items,
  basePath,
  empty: _empty,
}: {
  items: ContentMeta[];
  basePath: string;
  empty: string;
}) {
  if (items.length === 0) {
    return null;
  }

  return (
    <ul className="divide-y divide-hair border-y border-hair">
      {items.map(({ slug, frontmatter }) => (
        <li key={slug}>
          <Link
            href={`${basePath}/${slug}`}
            className="group block py-6 transition-colors hover:bg-panel sm:px-4"
          >
            <div className="flex items-baseline justify-between gap-4">
              <h2 className="max-w-2xl text-lg font-semibold tracking-tight text-ink group-hover:text-accent">
                {frontmatter.title}
              </h2>
              <time className="num shrink-0 text-xs text-ink-muted">
                {shortDate(frontmatter.date)}
              </time>
            </div>
            <p className="mt-2 max-w-2xl leading-relaxed text-ink-muted">{frontmatter.summary}</p>
            {frontmatter.tags && frontmatter.tags.length > 0 ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {frontmatter.tags.map((t) => (
                  <span
                    key={t}
                    className="text-xs text-ink-muted"
                  >
                    {t}
                  </span>
                ))}
              </div>
            ) : null}
          </Link>
        </li>
      ))}
    </ul>
  );
}
