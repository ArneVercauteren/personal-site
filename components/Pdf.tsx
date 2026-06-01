// Inline PDF embed for MDX writeups. Drop a PDF in public/ and use it in an
// .mdx file: <Pdf src="/papers/my-paper.pdf" title="My paper" />
//
// Renders the browser's native PDF viewer (chrome hidden for a clean look),
// with graceful fallbacks for browsers/devices that won't embed PDFs.
export function Pdf({
  src,
  title = "PDF",
  className = "h-[80vh]",
}: {
  src: string;
  title?: string;
  /** Tailwind height class for the viewer; defaults to 80% of the viewport. */
  className?: string;
}) {
  const embed = `${src}#toolbar=0&navpanes=0`;
  return (
    <figure className="not-prose my-8">
      <div
        className={`w-full overflow-hidden rounded-lg border border-hair bg-panel ${className}`}
      >
        <object data={embed} type="application/pdf" className="h-full w-full">
          <iframe src={embed} title={title} className="h-full w-full" />
          <div className="p-6 text-sm text-ink-muted">
            Your browser can&rsquo;t display PDFs inline.{" "}
            <a href={src} className="text-accent hover:underline">
              Download {title}
            </a>
            .
          </div>
        </object>
      </div>
      <figcaption className="mt-2 flex items-center justify-between gap-4 text-sm text-ink-muted">
        <span>{title}</span>
        <a
          href={src}
          target="_blank"
          rel="noopener noreferrer"
          className="text-accent hover:underline"
        >
          Open / download &rarr;
        </a>
      </figcaption>
    </figure>
  );
}
