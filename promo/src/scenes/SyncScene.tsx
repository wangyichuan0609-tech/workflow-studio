import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { LangProps, useCopy } from "../copy";
import { clamp, color, mono } from "../theme";
import { appear, Backdrop, Badge, Caption, KindIcon, Kind } from "../ui";

const CLICK = 96;

export const SyncScene: React.FC<LangProps> = ({ lang }) => {
  const t = useCopy(lang);
  const frame = useCurrentFrame();
  const press = interpolate(frame, [CLICK - 4, CLICK, CLICK + 6], [1, 0.95, 1], clamp);
  const items: [Kind, string, string][] = [
    ["agent", `agents-researcher · agent`, "modify · agents/researcher/AGENT.md, .agents/skills/agent-agents-researcher/SKILL.md, AGENTS.md"],
    ["action", `normalize-meeting-actions · action`, "modify · .workflow-studio/actions/normalize-meeting-actions.json"],
    ["workflow", `meeting-flow · workflow`, "add · .codex/workflows/meeting-flow.json, .agents/skills/workflow-meeting-flow/SKILL.md, AGENTS.md"],
  ];
  const dialog = appear(frame, 0, 18);
  return (
    <Backdrop>
      <Caption title={t.syncTitle} sub={t.syncSub} />
      <div
        style={{
          position: "absolute",
          left: 780,
          top: 200,
          width: 1060,
          padding: "32px 34px",
          borderRadius: 20,
          border: `1px solid ${color.lineStrong}`,
          background: color.raised,
          boxShadow: "0 40px 120px rgba(0,0,0,.55)",
          opacity: dialog,
          scale: interpolate(dialog, [0, 1], [0.96, 1]),
        }}
      >
        <div style={{ fontSize: 30, fontWeight: 650 }}>{t.syncPreview}</div>
        <div style={{ fontSize: 18, color: color.text2, marginTop: 10 }}>{t.syncExplain}</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 14, marginTop: 26 }}>
          {items.map(([kind, name, files], index) => {
            const synced = frame >= CLICK + 14 + index * 9;
            return (
              <div
                key={name}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 18,
                  padding: "18px 20px",
                  borderRadius: 14,
                  border: `1px solid ${color.line}`,
                  background: color.surface1,
                  opacity: appear(frame, 8 + index * 8, 16),
                }}
              >
                <KindIcon kind={kind} label={kind[0].toUpperCase()} size={44} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 20, fontWeight: 600 }}>
                    {index + 1}. {name}
                  </div>
                  <div style={{ fontFamily: mono, fontSize: 15, color: color.text3, marginTop: 6, lineHeight: 1.5 }}>{files}</div>
                </div>
                {synced ? <Badge tone="success">{t.synced}</Badge> : <Badge tone="accent">{t.ready}</Badge>}
              </div>
            );
          })}
        </div>
        <div style={{ marginTop: 22, padding: "14px 18px", borderRadius: 12, border: `1px solid ${color.line}`, fontSize: 18, color: color.text2, opacity: appear(frame, CLICK + 40, 14) }}>
          {t.syncDone}
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 22 }}>
          <div
            style={{
              padding: "14px 24px",
              borderRadius: 10,
              background: color.accent,
              color: "#fff",
              fontSize: 19,
              fontWeight: 600,
              scale: press,
              opacity: frame > CLICK + 10 ? 0.45 : 1,
              boxShadow: frame > CLICK - 22 && frame < CLICK + 4 ? `0 0 0 6px ${color.accentSoft}` : "none",
            }}
          >
            {t.confirmSync}
          </div>
        </div>
      </div>
    </Backdrop>
  );
};
