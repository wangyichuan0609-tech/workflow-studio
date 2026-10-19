import React from "react";
import { Interactive, interpolate, useCurrentFrame } from "remotion";
import { LangProps, useCopy } from "../copy";
import { clamp, color, easeOut, mono } from "../theme";
import { appear, Backdrop } from "../ui";

// The real places a coding agent project keeps this structure today.
const files: [string, number, number, number][] = [
  ["AGENTS.md", 180, 170, 0],
  [".agents/skills/agent-reviewer/SKILL.md", 1080, 130, 6],
  [".codex/workflows/delivery-flow.json", 240, 840, 10],
  ["agents/researcher/AGENT.md", 1180, 860, 3],
  [".workflow-studio/actions/api-request.json", 90, 740, 14],
  ["agents/builder/AGENT.md", 1440, 740, 8],
  [".claude/skills/workflow-review/SKILL.md", 700, 960, 12],
  ["QWEN.md", 1580, 300, 5],
  [".agents/skills/meeting-action-extractor/SKILL.md", 560, 60, 16],
];

export const HookScene: React.FC<LangProps> = ({ lang }) => {
  const t = useCopy(lang);
  const frame = useCurrentFrame();
  const dim = interpolate(frame, [36, 60], [1, 0.28], { ...clamp, easing: easeOut });
  return (
    <Backdrop>
      {files.map(([path, x, y, delay]) => (
        <div
          key={path}
          style={{
            position: "absolute",
            left: x,
            top: y,
            fontFamily: mono,
            fontSize: 26,
            color: color.text3,
            padding: "8px 16px",
            borderRadius: 10,
            border: `1px solid ${color.line}`,
            background: color.surface1,
            opacity: appear(frame, delay, 20) * dim,
            translate: `${interpolate(frame, [0, 135], [0, delay % 2 ? 18 : -18])}px ${interpolate(appear(frame, delay, 20), [0, 1], [16, 0])}px`,
          }}
        >
          {path}
        </div>
      ))}
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 30, padding: "0 120px", textAlign: "center" }}>
        <Interactive.Div
          name="Hook title"
          style={{
            fontSize: 88,
            fontWeight: 650,
            wordBreak: "keep-all",
            textWrap: "balance",
            letterSpacing: "-0.03em",
            lineHeight: 1.1,
            opacity: appear(frame, 40, 20),
            translate: `0px ${interpolate(appear(frame, 40, 20), [0, 1], [28, 0])}px`,
          }}
        >
          {t.hookTitle}
        </Interactive.Div>
        <Interactive.Div
          name="Hook sub"
          style={{ fontSize: 40, lineHeight: 1.45, color: color.text2, maxWidth: 1300, textWrap: "balance", opacity: appear(frame, 54, 20) }}
        >
          {t.hookSub}
        </Interactive.Div>
      </div>
    </Backdrop>
  );
};
