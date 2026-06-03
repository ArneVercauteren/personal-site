// Central site config. Edit name/tagline once the domain + identity are settled.
export const site = {
  name: "astralanx",
  tagline: "Software and quantitative research",
  description:
    "A personal site for my work — astralanx, a system for evolving trading strategies, and the simulated portfolio it runs — alongside some essays, music, and art.",
  // Public contact email.
  email: "arne.ffmeta@gmail.com",
  // Birth date (ISO, YYYY-MM-DD). Age is derived from this and the build-time
  // date — see `age()` in lib/format.ts. TODO: set this to your real birth date.
  birthDate: "2007-05-09",
  // Top-level navigation. Studio and Projects are hidden for now — re-add
  // { href: "/studio", label: "Studio" } and { href: "/projects", label: "Projects" }
  // here (and their home-page tiles) when those sections are ready.
  nav: [
    { href: "/", label: "Home" },
    { href: "/about", label: "About" },
    { href: "/astralanx", label: "Astralanx" },
    { href: "/astralanx/live", label: "Live" },
    { href: "/writing", label: "Writing" },
    { href: "/reading", label: "Reading list" },
    { href: "/contact", label: "Contact" },
  ],
} as const;

export type NavItem = (typeof site.nav)[number];
