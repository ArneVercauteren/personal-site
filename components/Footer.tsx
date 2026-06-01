import { site } from "@/lib/site";

export function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer className="border-t border-hair">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-2 px-6 py-8 text-xs text-ink-muted sm:flex-row sm:items-center sm:justify-between">
        <p>
          © {year} {site.name}
        </p>
        <p className="text-ink-muted/80">
          Live figures are a{" "}
          <span className="text-ink-muted">simulated paper portfolio</span> — not
          investment advice.
        </p>
      </div>
    </footer>
  );
}
