// Captioned figure for MDX writeups. Put the image in public/ and use:
// <Figure src="/figures/fig1.png" alt="…" caption="Figure 1. …" />
export function Figure({
  src,
  alt,
  caption,
}: {
  src: string;
  alt?: string;
  caption?: string;
}) {
  return (
    <figure className="not-prose my-8">
      {/* White matte so light/transparent charts stay legible on the dark page. */}
      {/* eslint-disable-next-line @next/next/no-img-element -- arbitrary content image, dimensions unknown */}
      <img
        src={src}
        alt={alt ?? caption ?? ""}
        className="w-full rounded-lg border border-hair bg-white"
      />
      {caption ? (
        <figcaption className="mt-2 text-sm text-ink-muted">
          {caption}
        </figcaption>
      ) : null}
    </figure>
  );
}
