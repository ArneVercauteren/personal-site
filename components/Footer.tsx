import { site } from "@/lib/site";

export function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer className="border-t border-hair">
      <div className="mx-auto w-full max-w-5xl px-6 py-8 text-xs text-ink-muted">
        <p>© {year} {site.name}</p>
      </div>
    </footer>
  );
}
