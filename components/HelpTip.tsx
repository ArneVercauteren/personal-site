// A tiny "?" affordance that exposes an explanation on hover/focus via the
// native title tooltip — no client JS. The analytics data ships its own
// `metric_explanations`, so most call sites pass those strings straight in.
// Renders nothing when there's no text, so callers can pass an optional lookup.
export function HelpTip({ text }: { text?: string }) {
  if (!text) return null;
  return (
    <span
      title={text}
      tabIndex={0}
      role="note"
      aria-label={text}
      className="ml-1 inline-flex h-3.5 w-3.5 cursor-help items-center justify-center rounded-full border border-hair text-[8px] font-semibold leading-none text-ink-muted align-middle"
    >
      ?
    </span>
  );
}
