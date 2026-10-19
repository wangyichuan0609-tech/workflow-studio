# Workflow Studio 宣传片 / Promo video

Remotion 项目，中英文两版共用同一套场景（`src/copy.ts` 里是全部文案）。
A Remotion project; the Chinese and English cuts share every scene (all copy lives in `src/copy.ts`).

| Composition | 内容 |
|---|---|
| `PromoZh` | 中文版，1920×1080，30fps，约 42 秒 |
| `PromoEn` | English cut, same timing |
| `Promo-Scenes/*` | 各场景单独预览 / each scene on its own |

## 预览与渲染 / Preview and render

```bash
npm i
npm run dev
npx remotion render PromoZh out/workflow-studio-promo-zh.mp4 --codec=h264 --crf=18
npx remotion render PromoEn out/workflow-studio-promo-en.mp4 --codec=h264 --crf=18
```

注意：项目路径含空格或中文（例如 `ai workspace/workflow可视化`）时，Remotion 的渲染浏览器无法加载打包结果，会报 “Waiting for root component to load” 超时。请把本目录复制到纯 ASCII 路径再渲染。
Note: Remotion's render browser cannot load the bundle when the project path contains spaces or non-ASCII characters (it times out on "Waiting for root component to load"). Copy this folder to a plain ASCII path to render.

画面全部用 React 重建产品界面（配色取自根目录 `DESIGN.md` 的深色令牌），没有配乐与配音。
Every frame rebuilds the product UI in React using the dark tokens from the root `DESIGN.md`. There is no music or voiceover.
