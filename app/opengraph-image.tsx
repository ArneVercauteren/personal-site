import { ImageResponse } from "next/og";

export const alt = "astralanx — auditable strategy research and live paper tracking";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    <div
      style={{
        alignItems: "flex-start", background: "#0b0d10", color: "#f2f0e9",
        display: "flex", flexDirection: "column", height: "100%", justifyContent: "center",
        padding: "84px", width: "100%",
      }}
    >
      <div style={{ color: "#77d6a1", display: "flex", fontSize: 28, letterSpacing: 4 }}>
        RESEARCH · PAPER TRACKING
      </div>
      <div style={{ display: "flex", fontSize: 88, fontWeight: 700, marginTop: 28 }}>
        astralanx<span style={{ color: "#77d6a1" }}>.</span>
      </div>
      <div style={{ color: "#b9b7af", display: "flex", fontSize: 34, marginTop: 24 }}>
        Genetic programming for long-term investing
      </div>
    </div>,
    size,
  );
}
