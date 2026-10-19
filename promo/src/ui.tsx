import React from "react";
import { AbsoluteFill, Interactive, interpolate, useCurrentFrame } from "remotion";
import { clamp, color, easeOut, font, mono } from "./theme";

// Shared building blocks. Kept deliberately plain: the product's look is
// "standard tool form, high craft", not decoration.

export const appear = (frame: number, start: number, length = 18) =>
  interpolate(frame, [start, start + length], [0, 1], { ...clamp, easing: easeOut });

export const Backdrop: React.FC<{ children?: React.ReactNode }> = ({ children }) => (
  <AbsoluteFill
    style={{
      backgroundColor: color.bg,
      backgroundImage: `radial-gradient(${color.dot} 1.4px, transparent 1.4px)`,
      backgroundSize: "28px 28px",
      fontFamily: font,
      color: color.text,
    }}
  >
    {children}
  </AbsoluteFill>
);

// The film's single message per scene sits on the left; the product shows on the right.
export const Caption: React.FC<{ title: string; sub: string; start?: number }> = ({ title, sub, start = 0 }) => {
  const frame = useCurrentFrame();
  return (
    <div style={{ position: "absolute", left: 120, top: 0, bottom: 0, width: 620, display: "flex", flexDirection: "column", justifyContent: "center", gap: 28 }}>
      <Interactive.Div
        name="Caption title"
        style={{
          fontSize: 66,
          fontWeight: 650,
          // Break Chinese only at punctuation, and balance lines so nothing is orphaned.
          wordBreak: "keep-all",
          textWrap: "balance",
          lineHeight: 1.12,
          letterSpacing: "-0.025em",
          opacity: appear(frame, start),
          translate: `0px ${interpolate(appear(frame, start), [0, 1], [24, 0])}px`,
        }}
      >
        {title}
      </Interactive.Div>
      <Interactive.Div
        name="Caption sub"
        style={{
          fontSize: 34,
          lineHeight: 1.5,
          textWrap: "pretty",
          color: color.text2,
          opacity: appear(frame, start + 8),
          translate: `0px ${interpolate(appear(frame, start + 8), [0, 1], [18, 0])}px`,
        }}
      >
        {sub}
      </Interactive.Div>
    </div>
  );
};

export const Window: React.FC<{ title: string; width: number; height: number; children?: React.ReactNode; style?: React.CSSProperties }> = ({ title, width, height, children, style }) => (
  <div
    style={{
      position: "absolute",
      width,
      height,
      borderRadius: 18,
      border: `1px solid ${color.lineStrong}`,
      background: color.surface1,
      boxShadow: "0 40px 120px rgba(0,0,0,.55), 0 8px 24px rgba(0,0,0,.35)",
      overflow: "hidden",
      ...style,
    }}
  >
    <div style={{ height: 56, display: "flex", alignItems: "center", gap: 14, padding: "0 22px", borderBottom: `1px solid ${color.line}`, background: color.raised }}>
      <Logo size={30} />
      <span style={{ fontSize: 20, fontWeight: 600 }}>Workflow Studio</span>
      <span style={{ width: 1, height: 20, background: color.lineStrong }} />
      <span style={{ fontSize: 20, color: color.text2 }}>{title}</span>
    </div>
    <div style={{ position: "relative", height: height - 57 }}>{children}</div>
  </div>
);

export const Logo: React.FC<{ size: number }> = ({ size }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <rect width="24" height="24" rx="6.5" fill={color.accent} />
    <circle cx="8" cy="8.25" r="2.1" stroke="#fff" strokeWidth="1.8" />
    <circle cx="16" cy="15.75" r="2.1" stroke="#fff" strokeWidth="1.8" />
    <path d="M10.1 8.25h1.4a3 3 0 0 1 3 3v2.4" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" />
  </svg>
);

type Tone = "neutral" | "accent" | "success" | "warning" | "danger";
const tones: Record<Tone, { fg: string; bg: string; line: string }> = {
  neutral: { fg: color.text2, bg: color.surface2, line: color.lineStrong },
  accent: { fg: color.accentText, bg: color.accentSoft, line: color.accentLine },
  success: { fg: color.success, bg: color.successSoft, line: color.successLine },
  warning: { fg: color.warning, bg: color.warningSoft, line: "rgba(239,180,90,.38)" },
  danger: { fg: color.danger, bg: color.dangerSoft, line: color.dangerLine },
};

export const Badge: React.FC<{ tone: Tone; children: React.ReactNode; size?: number }> = ({ tone, children, size = 18 }) => (
  <span
    style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 8,
      padding: "4px 12px",
      borderRadius: 999,
      fontSize: size,
      fontWeight: 500,
      color: tones[tone].fg,
      background: tones[tone].bg,
      border: `1px solid ${tones[tone].line}`,
      whiteSpace: "nowrap",
    }}
  >
    <span style={{ width: 7, height: 7, borderRadius: 7, background: tones[tone].fg }} />
    {children}
  </span>
);

export type Kind = "agent" | "action" | "workflow" | "skill" | "project";
const kindColors: Record<Kind, [string, string]> = {
  agent: [color.agent, color.agentSoft],
  action: [color.action, color.actionSoft],
  workflow: [color.workflow, color.workflowSoft],
  skill: [color.skill, "rgba(173,146,255,.15)"],
  project: [color.text2, color.surface2],
};

export const KindIcon: React.FC<{ kind: Kind; label: string; size?: number }> = ({ kind, label, size = 40 }) => (
  <span
    style={{
      width: size,
      height: size,
      borderRadius: size * 0.28,
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      flexShrink: 0,
      color: kindColors[kind][0],
      background: kindColors[kind][1],
      fontSize: size * 0.46,
      fontWeight: 600,
    }}
  >
    {label}
  </span>
);

export const Mono: React.FC<{ children: React.ReactNode; style?: React.CSSProperties }> = ({ children, style }) => (
  <span style={{ fontFamily: mono, ...style }}>{children}</span>
);
