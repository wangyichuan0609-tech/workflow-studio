import { Easing } from "remotion";

// Dark tokens from the product's DESIGN.md, so the film looks like the app.
export const color = {
  bg: "#141518",
  raised: "#1f2125",
  surface1: "#1c1e21",
  surface2: "#26292e",
  surface3: "#2f3238",
  dot: "#2b2e34",
  line: "#2a2d32",
  lineStrong: "#353940",
  text: "#e9ebee",
  text2: "#aab0b9",
  text3: "#8d939d",
  edge: "#737b87",
  accent: "#3d6af0",
  accentText: "#93adff",
  accentSoft: "rgba(91, 132, 255, .15)",
  accentLine: "rgba(122, 156, 255, .45)",
  success: "#43c98d",
  successSoft: "rgba(67, 201, 141, .13)",
  successLine: "rgba(67, 201, 141, .38)",
  warning: "#efb45a",
  warningSoft: "rgba(239, 180, 90, .13)",
  danger: "#ff7b73",
  dangerSoft: "rgba(255, 123, 115, .12)",
  dangerLine: "rgba(255, 123, 115, .40)",
  agent: "#45c7b7",
  agentSoft: "rgba(69, 199, 183, .14)",
  action: "#f0a65a",
  actionSoft: "rgba(240, 166, 90, .14)",
  skill: "#ad92ff",
  workflow: "#86a3ff",
  workflowSoft: "rgba(134, 163, 255, .15)",
};

export const font =
  '-apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", "Hiragino Sans GB", "Noto Sans SC", "Helvetica Neue", Arial, sans-serif';
export const mono = '"SF Mono", ui-monospace, Menlo, Consolas, monospace';

export const easeOut = Easing.bezier(0.16, 1, 0.3, 1);
export const easeInOut = Easing.bezier(0.65, 0, 0.35, 1);

export const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
