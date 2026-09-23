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
    icons: [{ src: "/icon.svg", sizes: "any", type: "image/svg+xml" }],
  };
}
