import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { LangProps, useCopy } from "../copy";
import { clamp, color } from "../theme";
import { appear, Backdrop, Badge, Caption, KindIcon, Window } from "../ui";

const CLICK = 22;
const PASS = 78;

export const TestScene: React.FC<LangProps> = ({ lang }) => {
  const t = useCopy(lang);
  const frame = useCurrentFrame();
  const running = frame >= CLICK && frame < PASS;
  const press = interpolate(frame, [CLICK - 4, CLICK, CLICK + 6], [1, 0.95, 1], clamp);
  const panel = appear(frame, PASS + 14, 18);
  const spinner = (frame * 14) % 360;
  return (
    <Backdrop>
      <Caption title={t.testTitle} sub={t.testSub} />
      <Window
        title="Agent"
        width={1060}
        height={620}
        style={{ left: 780, top: 230, opacity: appear(frame, 0, 16), translate: `${interpolate(appear(frame, 0, 20), [0, 1], [40, 0])}px 0px` }}
      >
        <div style={{ position: "absolute", left: 40, right: 40, top: 36 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
            <KindIcon kind="agent" label={t.nodeResearcher[0]} size={52} />
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                <span style={{ fontSize: 30, fontWeight: 650 }}>{t.nodeResearcher}</span>
                {frame < CLICK ? null : running ? <Badge tone="accent">{t.testing}</Badge> : <Badge tone="success">{t.passed}</Badge>}
              </div>
              <div style={{ fontSize: 16, color: color.text3, marginTop: 6 }}>agents/researcher/AGENT.md</div>
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "13px 22px",
                borderRadius: 10,
                border: `1px solid ${color.lineStrong}`,
                background: color.surface2,
                fontSize: 19,
                fontWeight: 600,
                scale: press,
                opacity: running ? 0.55 : 1,
              }}
            >
              {running ? (
                <span style={{ width: 16, height: 16, borderRadius: 16, border: `2.5px solid ${color.text3}`, borderTopColor: color.accentText, rotate: `${spinner}deg` }} />
              ) : (
                <span style={{ fontSize: 15 }}>▶</span>
              )}
              {t.smokeTest}
            </div>
          </div>
          <div style={{ marginTop: 34, fontSize: 17, color: color.text3 }}>{t.fieldDescription}</div>
          <div style={{ marginTop: 10, padding: "16px 20px", borderRadius: 12, border: `1px solid ${color.line}`, background: color.raised, fontSize: 19, color: color.text2 }}>
            {t.nodeResearcherRole}
          </div>
          <div style={{ marginTop: 22, fontSize: 17, color: color.text3 }}>{t.fieldActions}</div>
          <div style={{ marginTop: 10, display: "inline-flex", alignItems: "center", gap: 12, padding: "12px 18px", borderRadius: 12, border: `1px solid ${color.accentLine}`, background: color.accentSoft, fontSize: 18 }}>
            <span style={{ width: 20, height: 20, borderRadius: 5, background: color.accent, color: "#fff", fontSize: 14, display: "inline-flex", alignItems: "center", justifyContent: "center" }}>✓</span>
            Normalize Meeting Actions
            <span style={{ color: color.text3, fontSize: 15 }}>script</span>
          </div>
          <div
            style={{
              marginTop: 34,
              padding: "24px 26px",
              borderRadius: 16,
              border: `1px solid ${color.successLine}`,
              background: color.raised,
              boxShadow: "0 18px 40px rgba(0,0,0,.4)",
              opacity: panel,
              translate: `0px ${interpolate(panel, [0, 1], [24, 0])}px`,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 24, fontWeight: 650 }}>
              <span style={{ color: color.success }}>✓</span>
              {t.dryRunPassed}
            </div>
            <div style={{ fontSize: 17, color: color.text2, marginTop: 10, lineHeight: 1.5 }}>{t.dryRunNote}</div>
            <div style={{ display: "flex", gap: 12, marginTop: 18 }}>
              {[t.layers, t.handoffs, t.runtime].map(chip => (
                <span key={chip} style={{ padding: "6px 14px", borderRadius: 999, border: `1px solid ${color.lineStrong}`, fontSize: 16, color: color.text2 }}>
                  {chip}
                </span>
              ))}
            </div>
          </div>
        </div>
      </Window>
    </Backdrop>
  );
};
