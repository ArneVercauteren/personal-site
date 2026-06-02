"use client";

import { useState } from "react";

/**
 * Book cover pulled from the Open Library Covers API by ISBN — no saved image
 * files. `?default=false` makes Open Library return a 404 (instead of a blank
 * 1x1) when it has no cover, which trips onError so we can show a placeholder.
 */
export function BookCover({ isbn, title }: { isbn?: string; title: string }) {
  const [failed, setFailed] = useState(false);
  // Open Library wants bare digits (+ trailing X), so strip dashes/spaces.
  const normalizedIsbn = isbn?.replace(/[^0-9Xx]/g, "");
  const showImage = normalizedIsbn && !failed;

  return (
    <div className="aspect-[2/3] w-16 shrink-0 overflow-hidden rounded border border-hair bg-elevated">
      {showImage ? (
        // eslint-disable-next-line @next/next/no-img-element -- remote cover from Open Library CDN; avoids next.config remotePatterns + image optimization cost
        <img
          src={`https://covers.openlibrary.org/b/isbn/${normalizedIsbn}-L.jpg?default=false`}
          alt={`Cover of ${title}`}
          width={64}
          height={96}
          loading="lazy"
          onError={() => setFailed(true)}
          className="h-full w-full object-cover"
        />
      ) : (
        <div
          aria-hidden
          className="flex h-full w-full items-center justify-center font-mono text-lg text-ink-muted/50"
        >
          {title.charAt(0)}
        </div>
      )}
    </div>
  );
}
