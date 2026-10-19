import React from "react";
import { Interactive, interpolate, useCurrentFrame } from "remotion";
import { LangProps, useCopy } from "../copy";
import { clamp, color, easeOut, mono } from "../theme";
import { appear, Backdrop, Logo } from "../ui";

const tools = ["Codex", "Claude Code", "Qwen Code", "OpenCode"];

export const OutroScene: React.FC<LangProps> = ({ lang }) => {
  const t = useCopy(lang);
  const frame = useCurrentFrame();
  return (
    <Backdrop>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 30, textAlign: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 30, opacity: appear(frame, 0, 16), scale: interpolate(frame, [0, 22], [0.94, 1], { ...clamp, easing: easeOut }) }}>
          <Logo size={104} />
          <Interactive.Div name="Outro name" style={{ fontSize: 112, fontWeight: 700, letterSpacing: "-0.035em" }}>
            {t.outroTitle}
          </Interactive.Div>
        </div>
        <Interactive.Div name="Outro sub" style={{ fontSize: 50, fontWeight: 550, opacity: appear(frame, 12, 16) }}>
          {t.outroSub}
        </Interactive.Div>
        <div style={{ display: "flex", alignItems: "center", gap: 16, marginTop: 18, opacity: appear(frame, 26, 16) }}>
          <span style={{ fontSize: 26, color: color.text2, marginRight: 8 }}>{t.outroTools}</span>
          {tools.map((tool, index) => (
            <span
              key={tool}
              style={{
                padding: "10px 22px",
                borderRadius: 999,
                border: `1px solid ${color.lineStrong}`,
                background: color.surface1,
                fontSize: 26,
                fontWeight: 550,
                opacity: appear(frame, 28 + index * 5, 12),
              }}
            >
              {tool}
            </span>
          ))}
        </div>
        <div style={{ marginTop: 34, display: "flex", flexDirection: "column", gap: 14, alignItems: "center", opacity: appear(frame, 50, 16) }}>
          <span style={{ fontFamily: mono, fontSize: 30, padding: "12px 26px", borderRadius: 12, background: "#0f1012", border: `1px solid ${color.line}` }}>
            <span style={{ color: color.accentText }}>$ </span>python3 server.py
          </span>
          <span style={{ fontSize: 24, color: color.text3 }}>{t.outroLocal}</span>
        </div>
      </div>
    </Backdrop>
  );
};
