import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "astralanx",
    short_name: "astralanx",
    description: "Auditable research and forward paper-strategy tracking.",
    start_url: "/",
    display: "standalone",
    background_color: "#0d0c0a",
    theme_color: "#0d0c0a",
    icons: [
      { src: "/icon.svg", sizes: "any", type: "image/svg+xml" },
      { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
  };
}
