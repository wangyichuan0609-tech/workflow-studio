import React from "react";
import { Composition, Folder } from "remotion";
import { LangProps } from "./copy";
import { Promo, PROMO_DURATION, sceneDurations } from "./Promo";
import { HookScene } from "./scenes/HookScene";
import { TitleScene } from "./scenes/TitleScene";
import { ImportScene } from "./scenes/ImportScene";
import { CanvasScene } from "./scenes/CanvasScene";
import { TestScene } from "./scenes/TestScene";
import { SyncScene } from "./scenes/SyncScene";
import { RunScene } from "./scenes/RunScene";
import { OutroScene } from "./scenes/OutroScene";

const size = { width: 1920, height: 1080, fps: 30 };
const zh: LangProps = { lang: "zh" };

export const RemotionRoot: React.FC = () => (
  <>
    <Composition id="PromoZh" component={Promo} durationInFrames={PROMO_DURATION} defaultProps={zh} {...size} />
    <Composition id="PromoEn" component={Promo} durationInFrames={PROMO_DURATION} defaultProps={{ lang: "en" } as LangProps} {...size} />
    <Folder name="Promo-Scenes">
      <Composition id="Hook" component={HookScene} durationInFrames={sceneDurations.hook} defaultProps={zh} {...size} />
      <Composition id="Title" component={TitleScene} durationInFrames={sceneDurations.title} defaultProps={zh} {...size} />
      <Composition id="Import" component={ImportScene} durationInFrames={sceneDurations.import} defaultProps={zh} {...size} />
      <Composition id="Canvas" component={CanvasScene} durationInFrames={sceneDurations.canvas} defaultProps={zh} {...size} />
      <Composition id="Test" component={TestScene} durationInFrames={sceneDurations.test} defaultProps={zh} {...size} />
      <Composition id="Sync" component={SyncScene} durationInFrames={sceneDurations.sync} defaultProps={zh} {...size} />
      <Composition id="Run" component={RunScene} durationInFrames={sceneDurations.run} defaultProps={zh} {...size} />
      <Composition id="Outro" component={OutroScene} durationInFrames={sceneDurations.outro} defaultProps={zh} {...size} />
    </Folder>
  </>
);
