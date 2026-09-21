"use client";

import { useState } from "react";
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
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 border-b border-hair bg-base/95 backdrop-blur">
      <nav className="relative mx-auto flex w-full max-w-5xl items-center justify-between px-5 py-4 sm:px-6">
        <Link
          href="/"
          className="text-sm font-semibold tracking-tight text-ink hover:text-accent"
          onClick={() => setOpen(false)}
        >
          {site.name}
          <span className="text-accent">.</span>
        </Link>

        <button
          type="button"
          aria-expanded={open}
          aria-controls="primary-navigation"
          onClick={() => setOpen((current) => !current)}
          className="inline-flex items-center gap-2 text-sm text-ink-muted transition-colors hover:text-ink md:hidden"
        >
          Menu
          <span aria-hidden className="font-mono text-base leading-none">{open ? "−" : "+"}</span>
        </button>

        <ul
          id="primary-navigation"
          className={`${open ? "flex" : "hidden"} absolute inset-x-0 top-full flex-col border-b border-hair bg-base px-5 py-4 text-base shadow-2xl md:static md:flex md:flex-row md:items-center md:gap-x-5 md:gap-y-1 md:border-0 md:bg-transparent md:p-0 md:text-sm md:shadow-none`}
        >
          {site.nav.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  onClick={() => setOpen(false)}
                  className={
                    active
                      ? "block py-2 text-accent md:py-0"
                      : "block py-2 text-ink-muted transition-colors hover:text-ink md:py-0"
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
