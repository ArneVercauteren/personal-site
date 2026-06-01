// Central site config. Edit name/tagline once the domain + identity are settled.
export const site = {
  name: "Arne Vercauteren",
  tagline: "Software and quantitative research",
  description:
    "A personal site for my work — Darwin, a system for evolving trading strategies, and the simulated portfolio it runs — alongside some essays, music, and art.",
  // Top-level navigation, grouped to ~6 items (Studio = music + art).
  nav: [
    { href: "/", label: "Home" },
    { href: "/about", label: "About" },
    { href: "/darwin", label: "Darwin" },
    { href: "/darwin/live", label: "Live" },
    { href: "/writing", label: "Writing" },
    { href: "/studio", label: "Studio" },
    { href: "/projects", label: "Projects" },
  ],
} as const;

export type NavItem = (typeof site.nav)[number];
