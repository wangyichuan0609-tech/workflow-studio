import React from "react";
import { Interactive, interpolate, useCurrentFrame } from "remotion";
import { LangProps, useCopy } from "../copy";
import { clamp, color, easeOut } from "../theme";
import { appear, Backdrop, Logo } from "../ui";

export const TitleScene: React.FC<LangProps> = ({ lang }) => {
  const t = useCopy(lang);
  const frame = useCurrentFrame();
  return (
    <Backdrop>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 34, textAlign: "center" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 36,
            opacity: appear(frame, 0, 16),
            scale: interpolate(frame, [0, 22], [0.92, 1], { ...clamp, easing: easeOut }),
          }}
        >
          <Logo size={128} />
          <Interactive.Div name="Product name" style={{ fontSize: 132, fontWeight: 700, letterSpacing: "-0.035em" }}>
            Workflow Studio
          </Interactive.Div>
        </div>
        <Interactive.Div
          name="Tagline"
          style={{ fontSize: 54, fontWeight: 550, letterSpacing: "-0.015em", maxWidth: 1500, opacity: appear(frame, 18, 18) }}
        >
          {t.tagline}
        </Interactive.Div>
        <Interactive.Div name="Tagline sub" style={{ fontSize: 32, color: color.text2, maxWidth: 1500, opacity: appear(frame, 30, 18) }}>
          {t.taglineSub}
        </Interactive.Div>
      </div>
    </Backdrop>
  );
};
