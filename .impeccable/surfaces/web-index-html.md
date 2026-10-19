---
version: 1
slug: "web-index-html"
primary_target: "web/index.html"
related_targets: ["web/styles.css","web/app.js"]
---

## Scope

Workflow Studio 整个本地 Web 应用（`web/index.html` + `web/styles.css` + `web/app.js`）：项目库、Workflow 画布、Agent / Action / Skill 编辑器、AI 创建工作台、连接中心、新手教程与全部对话框。Mode: Operate。Build path: code-led（Operate 表面固定 code-led；本机无图像生成）。

## Audience, job, constraints

会用 Codex 的个人用户；任务是导入项目 → 编辑资源 → 编排 Workflow → 发布到 Studio → 同步到 Codex。必须保留全部现有功能、交互与文案；零依赖、离线、不得引入 CDN 字体或脚本。用户要“简单高效”，品质参照 Linear、Figma、飞书 / Lark；不要花哨幼稚、不要信息过密、不要千篇一律的 AI SaaS（紫蓝渐变、卡片套卡片）。

## Direction contract

THESIS: 同类工作台的标准形态，按 Linear / Figma / 飞书的工艺执行：每一屏只回答“我在哪、它处于什么状态、下一步做什么”。拒绝品类默认的近黑底 + 霓虹绿节点编辑器、紫色 AI 光晕、英文大写眉标和 6–9px 小字。

OWN-WORLD: 浅色为主，跟随系统切换深色。Restrained 色彩策略：冷中性灰阶三层表面（内容/画布白、侧栏与工具条浅灰、1px 发丝边界），一个明确的蓝色强调只用于主操作、选中、焦点与当前路径；资源类型色（Agent 青绿、Action 琥珀、Skill 紫、Workflow 蓝）只出现在 20–28px 的类型图标块里；状态色（成功绿、提醒琥珀、危险红）只在承载含义处出现。系统字体栈（SF Pro / PingFang SC / 微软雅黑），rem 字号阶梯 12 / 13 / 14 / 16 / 20 / 24，正文与输入 14，等宽数字用于计数、ID、路径。统一 1.5px 描边线性 SVG 图标；圆角 6 / 8 / 12；柔和偏移阴影只用于浮层。

STORY: 用户打开即知道当前项目与页面；每个资源的状态（草稿 / 待同步 / 已同步 / 冲突）在列表、标题和操作区用同一套词汇与标记；永远只有一个主按钮代表下一步（草稿时是“发布到 Studio”，已发布时是“同步到 Codex”）；删除等危险操作与其他按钮隔开；窄窗口里任何操作都不会消失，只会收成图标按钮。

FIRST VIEWPORT: 以 1440×900 的 Workflow 页为准。52px 顶栏：左侧标志 + “Workflow Studio” + 当前页面标题；右侧本页操作组（删除隔离在最左、测试与复制调用方式为次级、发布或同步为唯一主按钮）+ AI 助手 + 连接状态 + 头像。左侧 64px 图标导航（图标 + 12px 中文/英文标签）。260px 资源库：搜索、分组列表（已保存的 Workflow、Agents、已授权 Actions），每项为类型图标 + 名称 + 路径 + 状态标记。中间画布：44px 工具条（名称 + 保存状态 | 选择 / 连接 | 排列 / 适应 | 校验状态），浅灰点阵网格上 190×92 节点卡（类型色图标、标题、路径、两行职责、左右端口），带方向箭头的连线，交接条件以小标签显示在连线中点。右侧 300px 检查器：选中节点的字段表单与 Codex 同步说明。签名交互：交接连线——从端口拖出的连线带箭头与条件标签，选中时以强调色高亮并显示删除；资源生命周期标记（三段点）跟随状态。运动语法：150–200ms ease-out 只用于悬停、按下、状态变化与浮层出现，无页面载入编排，尊重减少动态效果。

FORM: canon — 用户选择的“品类标准”（standing exit），以 Linear、Figma、飞书 / Lark 的工艺为标准；不在排序候选列表内。seed:66130f48b9255377

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Unresolved

- 无。画布平移 / 缩放已于 2026-10-18 补上（滚轮平移、⌘/Ctrl+滚轮与双指捏合缩放、拖动空白处 / 空格拖动 / 中键拖动平移、左下角缩放坞），视图变化不保存、不改变同步状态。
