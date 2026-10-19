import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { LangProps, useCopy } from "../copy";
import { clamp, color, mono } from "../theme";
import { appear, Backdrop, Caption } from "../ui";

const TYPE_START = 14;
const PLAN = 44;

// A plain terminal: the workflow runs in the user's coding tool, not in Studio.
export const RunScene: React.FC<LangProps> = ({ lang }) => {
  const t = useCopy(lang);
  const frame = useCurrentFrame();
  const typed = Math.round(interpolate(frame, [TYPE_START, TYPE_START + 6 * t.startPhrase.length], [0, t.startPhrase.length], clamp));
  const caretOn = Math.floor(frame / 15) % 2 === 0;
  const steps = [t.nodeResearcher, t.nodeAction, t.nodeReviewer];
  return (
    <Backdrop>
      <Caption title={t.runTitle} sub={t.runSub} />
      <div
        style={{
          position: "absolute",
          left: 780,
          top: 290,
          width: 1060,
          height: 500,
          borderRadius: 18,
          border: `1px solid ${color.lineStrong}`,
          background: "#0f1012",
          boxShadow: "0 40px 120px rgba(0,0,0,.55)",
          overflow: "hidden",
          fontFamily: mono,
          opacity: appear(frame, 0, 16),
          translate: `${interpolate(appear(frame, 0, 20), [0, 1], [40, 0])}px 0px`,
        }}
      >
        <div style={{ height: 52, display: "flex", alignItems: "center", gap: 10, padding: "0 20px", borderBottom: `1px solid ${color.line}`, background: color.surface1 }}>
          {["#ff5f57", "#febc2e", "#28c840"].map(dot => (
            <span key={dot} style={{ width: 14, height: 14, borderRadius: 14, background: dot, opacity: 0.85 }} />
          ))}
          <span style={{ marginLeft: 16, fontSize: 18, color: color.text3 }}>~/code/meeting-notes — codex</span>
        </div>
        <div style={{ padding: "34px 38px", fontSize: 26, lineHeight: 1.7 }}>
          <div>
            <span style={{ color: color.accentText }}>› </span>
            <span>{t.startPhrase.slice(0, typed)}</span>
            {frame < PLAN && <span style={{ opacity: caretOn ? 1 : 0, color: color.text2 }}>▍</span>}
          </div>
          <div style={{ marginTop: 26, color: color.text2, opacity: appear(frame, PLAN, 12) }}>
            $workflow-meeting-flow · {t.runPlan}
          </div>
          {steps.map((step, index) => {
            const at = PLAN + 18 + index * 18;
            const done = frame >= at + 12;
            return (
              <div key={step} style={{ display: "flex", gap: 18, alignItems: "center", marginTop: 12, opacity: appear(frame, at - 6, 10) }}>
                <span
                  style={{
                    width: 30,
                    height: 30,
                    borderRadius: 8,
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 20,
                    color: done ? color.bg : color.text3,
                    background: done ? color.success : "transparent",
                    border: `2px solid ${done ? color.success : color.lineStrong}`,
                  }}
                >
                  {done ? "✓" : ""}
                </span>
                <span>
                  {index + 1}. {step}
                </span>
                {done && <span style={{ color: color.success, fontSize: 22 }}>{t.stepDone}</span>}
              </div>
            );
          })}
        </div>
      </div>
    </Backdrop>
  );
};
