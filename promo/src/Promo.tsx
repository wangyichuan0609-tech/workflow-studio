import React from "react";
import { linearTiming, TransitionSeries } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { LangProps } from "./copy";
import { HookScene } from "./scenes/HookScene";
import { TitleScene } from "./scenes/TitleScene";
import { ImportScene } from "./scenes/ImportScene";
import { CanvasScene } from "./scenes/CanvasScene";
import { TestScene } from "./scenes/TestScene";
import { SyncScene } from "./scenes/SyncScene";
import { RunScene } from "./scenes/RunScene";
import { OutroScene } from "./scenes/OutroScene";

export const FADE = 12;

// Scene lengths in frames at 30fps; Root.tsx registers the same values per scene.
export const sceneDurations = {
  hook: 135,
  title: 105,
  import: 180,
  canvas: 285,
  test: 150,
  sync: 180,
  run: 150,
  outro: 150,
};

export const PROMO_DURATION =
  Object.values(sceneDurations).reduce((sum, value) => sum + value, 0) - FADE * (Object.keys(sceneDurations).length - 1);

export const Promo: React.FC<LangProps> = ({ lang }) => (
  <TransitionSeries>
    <TransitionSeries.Sequence name="Hook" durationInFrames={135}>
      <HookScene lang={lang} />
    </TransitionSeries.Sequence>
    <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: FADE })} />
    <TransitionSeries.Sequence name="Title" durationInFrames={105}>
      <TitleScene lang={lang} />
    </TransitionSeries.Sequence>
    <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: FADE })} />
    <TransitionSeries.Sequence name="Import" durationInFrames={180}>
      <ImportScene lang={lang} />
    </TransitionSeries.Sequence>
    <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: FADE })} />
    <TransitionSeries.Sequence name="Canvas" durationInFrames={285}>
      <CanvasScene lang={lang} />
    </TransitionSeries.Sequence>
    <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: FADE })} />
    <TransitionSeries.Sequence name="Test" durationInFrames={150}>
      <TestScene lang={lang} />
    </TransitionSeries.Sequence>
    <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: FADE })} />
    <TransitionSeries.Sequence name="Sync" durationInFrames={180}>
      <SyncScene lang={lang} />
    </TransitionSeries.Sequence>
    <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: FADE })} />
    <TransitionSeries.Sequence name="Run" durationInFrames={150}>
      <RunScene lang={lang} />
    </TransitionSeries.Sequence>
    <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: FADE })} />
    <TransitionSeries.Sequence name="Outro" durationInFrames={150}>
      <OutroScene lang={lang} />
    </TransitionSeries.Sequence>
  </TransitionSeries>
);
