// Central site config. Edit name/tagline once the domain + identity are settled.
const configuredSiteUrl = process.env.NEXT_PUBLIC_SITE_URL;

if (process.env.NODE_ENV === "production" && !configuredSiteUrl) {
  throw new Error(
    "NEXT_PUBLIC_SITE_URL must be set for production builds so canonical URLs, sitemap entries, and social metadata use the public domain.",
  );
}

export const site = {
  name: "astralanx",
  tagline: "Genetic programming for long-term investing",
  description:
    "A personal site for my work — astralanx, a system for evolving trading strategies and the simulated portfolio it runs — alongside essays and software projects.",
  // Public contact email.
  email: "arne.ffmeta@gmail.com",
  // Local development does not need a public origin; production builds do.
  url: configuredSiteUrl ?? "http://localhost:3000",
  // Birth date (ISO, YYYY-MM-DD). Age is derived from this and the build-time
  // date — see `age()` in lib/format.ts. TODO: set this to your real birth date.
  birthDate: "2007-05-09",
  nav: [
    { href: "/", label: "Home" },
    { href: "/about", label: "About" },
    { href: "/astralanx", label: "Astralanx" },
    { href: "/astralanx/live", label: "Live" },
    { href: "/projects", label: "Projects" },
    { href: "/writing", label: "Writing" },
    { href: "/reading", label: "Reading" },
    { href: "/contact", label: "Contact" },
  ],
} as const;

export type NavItem = (typeof site.nav)[number];
