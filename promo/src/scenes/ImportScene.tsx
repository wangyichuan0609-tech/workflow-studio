import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { LangProps, useCopy } from "../copy";
import { clamp, color, easeOut, mono } from "../theme";
import { appear, Backdrop, Badge, Caption, KindIcon, Kind, Window } from "../ui";

const CLICK = 62;

export const ImportScene: React.FC<LangProps> = ({ lang }) => {
  const t = useCopy(lang);
  const frame = useCurrentFrame();
  const done = appear(frame, CLICK + 10, 16);
  const press = interpolate(frame, [CLICK - 4, CLICK, CLICK + 6], [1, 0.95, 1], clamp);
  const rows: [Kind, string, string, number][] = [
    ["agent", "Agent", t.agentHint, 3],
    ["action", "Action", t.actionHint, 4],
    ["workflow", "Workflow", t.workflowHint, 1],
    ["skill", "Skill", t.skillHint, 2],
  ];
  const projects = ["docs-site", "meeting-notes", "api-gateway", "mobile-app"];
  return (
    <Backdrop>
      <Caption title={t.importTitle} sub={t.importSub} />
      <Window
        title={t.projectLibrary}
        width={1060}
        height={700}
        style={{ left: 780, top: 190, opacity: appear(frame, 0, 16), translate: `${interpolate(appear(frame, 0, 20), [0, 1], [40, 0])}px 0px` }}
      >
        <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 280, borderRight: `1px solid ${color.line}`, padding: 18, display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={{ fontSize: 20, fontWeight: 600, padding: "6px 8px 12px" }}>{t.projectLibrary}</div>
          {projects.map(name => {
            const selected = name === "meeting-notes";
            return (
              <div key={name} style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 10px", borderRadius: 10, background: selected ? "#26304a" : "transparent" }}>
                <KindIcon kind="project" label={name[0].toUpperCase()} size={36} />
                <span style={{ fontSize: 19, color: selected ? color.text : color.text2 }}>{name}</span>
              </div>
            );
          })}
        </div>
        <div style={{ position: "absolute", left: 312, right: 32, top: 30 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <span style={{ fontSize: 32, fontWeight: 650 }}>meeting-notes</span>
            <span style={{ opacity: done }}>
              <Badge tone="success">{t.imported}</Badge>
            </span>
          </div>
          <div style={{ marginTop: 22, padding: 24, borderRadius: 14, border: `1px solid ${color.line}`, background: color.raised, display: "flex", gap: 24, alignItems: "center" }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 21, fontWeight: 600 }}>{t.authorizeImport}</div>
              <div style={{ fontSize: 17, color: color.text2, marginTop: 8, lineHeight: 1.5 }}>{t.importExplain}</div>
              <div style={{ fontFamily: mono, fontSize: 15, color: color.text3, marginTop: 10 }}>~/code/meeting-notes</div>
            </div>
            <div
              style={{
                padding: "14px 22px",
                borderRadius: 10,
                background: color.accent,
                color: "#fff",
                fontSize: 19,
                fontWeight: 600,
                scale: press,
                boxShadow: frame > CLICK - 20 && frame < CLICK + 4 ? `0 0 0 6px ${color.accentSoft}` : "none",
                whiteSpace: "nowrap",
              }}
            >
              {t.authorizeImport}
            </div>
          </div>
          <div style={{ marginTop: 18, borderRadius: 14, border: `1px solid ${color.line}`, overflow: "hidden" }}>
            {rows.map(([kind, label, hint, count], index) => {
              const show = appear(frame, CLICK + 16 + index * 7, 16);
              const value = Math.round(interpolate(frame, [CLICK + 20 + index * 7, CLICK + 44 + index * 7], [0, count], { ...clamp, easing: easeOut }));
              return (
                <div key={kind} style={{ display: "flex", alignItems: "center", gap: 18, padding: "16px 22px", borderTop: index ? `1px solid ${color.line}` : "none", background: color.raised, opacity: 0.25 + 0.75 * show }}>
                  <KindIcon kind={kind} label={label[0]} size={42} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 21, fontWeight: 600 }}>{label}</div>
                    <div style={{ fontSize: 16, color: color.text2, marginTop: 2 }}>{hint}</div>
                  </div>
                  <span style={{ fontSize: 30, fontWeight: 650, fontVariantNumeric: "tabular-nums", opacity: show }}>{value}</span>
                </div>
              );
            })}
          </div>
        </div>
      </Window>
    </Backdrop>
  );
};
