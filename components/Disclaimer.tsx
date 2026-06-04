// The standing paper-only disclaimer. Required on every page that shows
// portfolio data. See docs/concepts/paper-trading-only.md.
export function Disclaimer() {
  return (
    <div className="panel border-accent/30 bg-accent/5 p-4 text-sm text-ink-muted">
      <span className="font-mono text-xs uppercase tracking-widest text-accent">
        Disclaimer
      </span>
      <p className="mt-1">
        This is a <span className="text-ink">simulated paper portfolio</span> —
        no real money is being traded here. <span className="text-ink">This is not investment advice.</span>
      </p>
    </div>
  );
}
