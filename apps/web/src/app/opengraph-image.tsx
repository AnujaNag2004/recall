import { ImageResponse } from "next/og";
import { site } from "@/lib/site";

export const alt = `${site.name}: ${site.headline}`;
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        padding: 80,
        background: "#ffffff",
        color: "#09090b",
      }}
    >
      <div style={{ display: "flex", fontSize: 36, fontWeight: 600 }}>Recall</div>
      <div style={{ display: "flex", flexDirection: "column" }}>
        <div style={{ display: "flex", fontSize: 104, fontWeight: 600, letterSpacing: -4 }}>
          Stop saving.
        </div>
        <div style={{ display: "flex", fontSize: 104, fontWeight: 600, letterSpacing: -4, color: "#4744a8" }}>
          Start doing.
        </div>
        <div style={{ display: "flex", marginTop: 32, fontSize: 34, color: "#63636e" }}>
          {site.tagline}
        </div>
      </div>
    </div>,
    size,
  );
}
