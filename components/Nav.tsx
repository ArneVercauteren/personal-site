"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { site } from "@/lib/site";

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  // "/astralanx" should not light up when on "/astralanx/live" (Live is its own item).
  if (href === "/astralanx") return pathname === "/astralanx";
  return pathname === href || pathname.startsWith(href + "/");
}

export function Nav() {
  const pathname = usePathname() ?? "/";

  return (
    <header className="sticky top-0 z-40 border-b border-hair bg-base/80 backdrop-blur">
      <nav className="mx-auto flex w-full max-w-5xl items-center justify-between gap-6 px-6 py-4">
        <Link
          href="/"
          className="font-mono text-sm font-semibold tracking-tight text-ink hover:text-accent"
        >
          {site.name}
          <span className="text-accent">.</span>
        </Link>

        <ul className="flex flex-wrap items-center gap-x-5 gap-y-1 text-sm">
          {site.nav.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={
                    active
                      ? "text-accent"
                      : "text-ink-muted transition-colors hover:text-ink"
                  }
                >
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </header>
  );
}
