import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { LangProps, useCopy } from "../copy";
import { clamp, color, easeInOut, easeOut } from "../theme";
import { appear, Backdrop, Caption, KindIcon, Kind, Window } from "../ui";

const W = 250;
const H = 116;
type NodeSpec = { x: number; y: number; kind: Kind; title: string; role: string; at: number };

const Node: React.FC<NodeSpec & { frame: number; highlight?: number }> = ({ x, y, kind, title, role, at, frame, highlight = 0 }) => {
  const show = appear(frame, at, 16);
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        width: W,
        height: H,
        borderRadius: 14,
        background: color.raised,
        border: `1px solid ${highlight ? color.dangerLine : color.lineStrong}`,
        boxShadow: "0 10px 30px rgba(0,0,0,.35)",
        padding: "16px 18px",
        opacity: show,
        scale: interpolate(show, [0, 1], [0.9, 1]),
      }}
    >
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <KindIcon kind={kind} label={title[0]} size={36} />
        <div style={{ fontSize: 19, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{title}</div>
      </div>
      <div style={{ fontSize: 15, color: color.text2, marginTop: 12, lineHeight: 1.4 }}>{role}</div>
      <Port x={-7} y={H / 2 - 7} />
      <Port x={W - 7} y={H / 2 - 7} />
    </div>
  );
};

const Port: React.FC<{ x: number; y: number }> = ({ x, y }) => (
  <span style={{ position: "absolute", left: x, top: y, width: 14, height: 14, borderRadius: 14, background: color.surface1, border: `2px solid ${color.edge}` }} />
);

const Cursor: React.FC<{ x: number; y: number; opacity: number }> = ({ x, y, opacity }) => (
  <svg width="30" height="36" viewBox="0 0 20 24" style={{ position: "absolute", left: x - 3, top: y - 2, opacity }}>
    <path d="M2 2 L2 19 L6.5 15 L9.5 22 L12.5 20.7 L9.6 14 L16 14 Z" fill="#fff" stroke="#111" strokeWidth="1.3" strokeLinejoin="round" />
  </svg>
);

export const CanvasScene: React.FC<LangProps> = ({ lang }) => {
  const t = useCopy(lang);
  const frame = useCurrentFrame();
  const nodes: NodeSpec[] = [
    { x: 30, y: 70, kind: "agent", title: t.nodeResearcher, role: t.nodeResearcherRole, at: 14 },
    { x: 400, y: 400, kind: "action", title: t.nodeAction, role: t.nodeActionRole, at: 30 },
    { x: 770, y: 70, kind: "agent", title: t.nodeReviewer, role: t.nodeReviewerRole, at: 46 },
  ];
  const port = (node: NodeSpec, side: "in" | "out") => [node.x + (side === "out" ? W : 0), node.y + H / 2] as const;
  const edges = [
    { from: nodes[0], to: nodes[1], label: t.handoff1, at: 70 },
    { from: nodes[1], to: nodes[2], label: t.handoff2, at: 100 },
  ];

  // The loop attempt: drag from the last node back to the first, then get refused.
  const dragStart = 160;
  const dragEnd = 200;
  const drag = interpolate(frame, [dragStart, dragEnd], [0, 1], { ...clamp, easing: easeInOut });
  const [sx, sy] = port(nodes[2], "out");
  const [tx, ty] = port(nodes[0], "in");
  const ex = interpolate(drag, [0, 1], [sx + 20, tx]);
  const ey = interpolate(drag, [0, 0.5, 1], [sy, 18, ty]);
  const loopOpacity = interpolate(frame, [dragStart, dragStart + 4, dragEnd + 18, dragEnd + 30], [0, 1, 1, 0], clamp);
  const refused = frame >= dragEnd && frame < dragEnd + 30;
  const shake = refused ? Math.sin((frame - dragEnd) * 1.6) * interpolate(frame, [dragEnd, dragEnd + 18], [6, 0], clamp) : 0;
  const toast = interpolate(frame, [dragEnd, dragEnd + 10, dragEnd + 60, dragEnd + 72], [0, 1, 1, 0], clamp);

  return (
    <Backdrop>
      <Caption title={t.canvasTitle} sub={t.canvasSub} />
      <Window
        title={t.workflowName}
        width={1060}
        height={720}
        style={{ left: 780, top: 180, opacity: appear(frame, 0, 16), translate: `${interpolate(appear(frame, 0, 20), [0, 1], [40, 0])}px 0px` }}
      >
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: "#141518",
            backgroundImage: `radial-gradient(${color.dot} 1.2px, transparent 1.2px)`,
            backgroundSize: "22px 22px",
            translate: `${shake}px 0px`,
          }}
        >
          <svg width="1060" height="663" style={{ position: "absolute", inset: 0, overflow: "visible" }}>
            {edges.map(edge => {
              const [ax, ay] = port(edge.from, "out");
              const [bx, by] = port(edge.to, "in");
              const d = `M ${ax} ${ay} C ${ax + 110} ${ay}, ${bx - 110} ${by}, ${bx} ${by}`;
              const progress = interpolate(frame, [edge.at, edge.at + 24], [0, 1], { ...clamp, easing: easeOut });
              return (
                <path key={edge.label} d={d} fill="none" stroke={color.edge} strokeWidth={2.5} pathLength={1} strokeDasharray="1 1" strokeDashoffset={1 - progress} />
              );
            })}
            <path
              d={`M ${sx} ${sy} C ${sx + 80} ${sy - 140}, ${ex + (tx - sx) * 0.1} ${ey - 120}, ${ex} ${ey}`}
              fill="none"
              stroke={color.danger}
              strokeWidth={2.5}
              strokeDasharray="8 7"
              opacity={loopOpacity}
            />
          </svg>
          {edges.map(edge => {
            const [ax, ay] = port(edge.from, "out");
            const [bx, by] = port(edge.to, "in");
            return (
              <div
                key={edge.label}
                style={{
                  position: "absolute",
                  left: (ax + bx) / 2,
                  top: (ay + by) / 2,
                  translate: "-50% -50%",
                  padding: "5px 14px",
                  borderRadius: 999,
                  border: `1px solid ${color.lineStrong}`,
                  background: color.raised,
                  color: color.text2,
                  fontSize: 16,
                  whiteSpace: "nowrap",
                  opacity: appear(frame, edge.at + 18, 14),
                }}
              >
                {edge.label}
              </div>
            );
          })}
          {nodes.map((node, index) => (
            <Node key={node.title} {...node} frame={frame} highlight={refused && (index === 0 || index === 2) ? 1 : 0} />
          ))}
          <Cursor x={ex} y={ey} opacity={interpolate(frame, [dragStart - 6, dragStart, dragEnd + 8, dragEnd + 16], [0, 1, 1, 0], clamp)} />
          <div
            style={{
              position: "absolute",
              left: "50%",
              bottom: 36,
              translate: `-50% ${interpolate(toast, [0, 1], [16, 0])}px`,
              opacity: toast,
              padding: "14px 22px",
              borderRadius: 12,
              background: color.raised,
              border: `1px solid ${color.dangerLine}`,
              color: color.danger,
              fontSize: 20,
              fontWeight: 500,
              boxShadow: "0 12px 30px rgba(0,0,0,.4)",
              whiteSpace: "nowrap",
            }}
          >
            {t.cycleToast}
          </div>
        </div>
      </Window>
    </Backdrop>
  );
};
