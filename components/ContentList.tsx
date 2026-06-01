import Link from "next/link";
import type { ContentMeta } from "@/lib/content";
import { shortDate } from "@/lib/format";

export function ContentList({
  items,
  basePath,
  empty,
}: {
  items: ContentMeta[];
  basePath: string;
  empty: string;
}) {
  if (items.length === 0) {
    return <p className="text-ink-muted">{empty}</p>;
  }

  return (
    <ul className="flex flex-col gap-3">
      {items.map(({ slug, frontmatter }) => (
        <li key={slug}>
          <Link
            href={`${basePath}/${slug}`}
            className="panel panel-hover group block p-5"
          >
            <div className="flex items-baseline justify-between gap-4">
              <h2 className="font-medium text-ink group-hover:text-accent">
                {frontmatter.title}
              </h2>
              <time className="num shrink-0 text-xs text-ink-muted">
                {shortDate(frontmatter.date)}
              </time>
            </div>
            <p className="mt-1 text-sm text-ink-muted">{frontmatter.summary}</p>
            {frontmatter.tags && frontmatter.tags.length > 0 ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {frontmatter.tags.map((t) => (
                  <span
                    key={t}
                    className="rounded border border-hair px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-ink-muted"
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
