# Workflow Studio 0.6.0

一个零依赖的本地 Agent 工作台。它把 Agent、Action、Skill 与 Workflow 草稿持久化在独立的 Studio 数据库中，并且只在用户明确点击“同步到 Codex”时修改所选项目。

**一句话理解**：如果把 Codex、Claude Code 这类 AI 编码工具看成一支能干活的“AI 团队”，Workflow Studio 就是这支团队的**组织架构图和排班表编辑器**：谁负责什么、谁能用哪些工具、活儿按什么顺序交接，都画在一张图上；真正干活的仍然是你已经在用的 AI 工具。

## 和同类产品有什么不同

市面上能“搭 AI 工作流”的产品不少，但它们解决的问题不一样：

| 你可能见过的 | 它们擅长什么 | Workflow Studio 的不同 |
|---|---|---|
| **在线智能体平台**（如扣子 Coze、Dify） | 在它们的平台上搭建并运行聊天机器人、AI 应用 | 不需要搬家到新平台。直接给你**已经在用的** Codex、Claude Code 等工具配置团队，工作流在你自己的项目里运行 |
| **自动化流程工具**（如 n8n、Zapier） | 把各种软件按固定步骤串起来，“收到邮件就存表格” | 编排的是会**思考和判断**的 AI 角色，并且明确规定每个角色能动哪些工具，而不只是死板的步骤 |
| **AI 开发框架 / 可视化搭建器**（如 LangGraph、LangFlow） | 帮开发者从零写出自己的 AI 程序，需要写代码、部署上线 | 不用写代码、不用部署服务器。在画布上连连线，就能变成 AI 工具看得懂的配置 |
| **直接手改 AI 工具的配置文件** | 最灵活，什么都能改 | 不用在一堆文字文件里翻找。所有角色和关系一张图看清，改错了也有提示 |

### 用大白话说，它的好处是

- **不用换工具，也不用多付一份钱**：工作流交给你已有的 Codex、Claude Code、Qwen Code、OpenCode 来跑，用的是你本来就有的工具和套餐。配置好一次，可以同时同步给多个工具。
- **一句话开工**：给工作流设个启动词，比如“开始”。以后在 AI 工具里只说这两个字，它就会从第一步按顺序干完整套活儿。
- **一眼看懂“谁在干什么”**：每个 AI 角色负责什么、能用哪些工具、做完交给谁，都画成节点和连线，不再藏在文件里。
- **改动先给你过目，绝不偷偷写入**：所有编辑先存成草稿；只有你点了“同步”，并在预览里确认要改哪些文件，才会真正写进项目。
- **先授权，再干活**：某个 AI 角色要用某个工具（比如调接口、跑脚本），必须先给它授权；没授权的连线会被直接拦下。密码和密钥不会写进配置里，只写一个“用哪把钥匙”的名字。
- **数据留在你的电脑上**：它只在本机运行，没有自己的云端服务器；在你选择并授权某个项目之前，它不会读取项目内容。只有你主动使用内置 AI 助手时，你发的内容才会交给你自己选择的 AI 服务（Codex 或你填写的 API）。
- **不被它绑住**：它生成的是 AI 工具本来就认识的普通文件。哪天不用 Workflow Studio 了，这些配置照样能用。
- **装起来很轻**：有 Python 就能运行，不用装一堆依赖，也不用联网下载组件。

### 它不做什么

为了说清楚边界：Workflow Studio **不是**一个在线平台，也**不会自己运行**工作流或执行脚本。它负责“设计、检查、同步”，执行交给你电脑上的 AI 编码工具。如果你想要的是一个对外提供服务的聊天机器人，或者定时自动跑的云端流程，上面表格里的其他产品可能更合适。

## 运行

```bash
git clone https://github.com/wangyichuan0609-tech/workflow-studio.git
cd workflow-studio
python3 server.py
```

打开 [http://127.0.0.1:4173](http://127.0.0.1:4173)。服务只监听 localhost。

也可以把编辑器放在另一个目录，指向实际项目：

```bash
python3 server.py --project /absolute/path/to/your/project --port 4173
```

## Agent 发现规则

把从 GitHub 下载的 Agent 文件夹复制到项目任意非隐藏目录。每个 Agent 目录应包含以下任一入口文件：

- `AGENT.md` / `agent.md`
- `SKILL.md`
- `prompt.md`
- `agent.json` / `manifest.json`

Markdown 可使用 `name`、`description`、`model` frontmatter；JSON 可使用同名字段。点击界面左侧的刷新按钮后，新 Agent 会出现。

## 项目工作区与持久化

- **Agent**：编辑名称、描述、本地行为覆盖、允许调用的 Actions 和关联 Skills。同步后生成 `$agent-<id>` 项目 skill。
- **Action**：用表单（执行方式、命令或请求、输入输出、成功条件、超时、重试、凭据引用）或 JSON、API 预设、MCP 预设、AI 创建项目级确定性执行定义。编辑器可手动发起只读联通诊断：API 仅做 HEAD/GET 健康请求，MCP 仅做 `initialize` 握手，Studio 本身不执行 Action。
- **Workflow**：把 Agent 与已授权的 Action 加入画布、连线并编辑交接条件；在右侧“Workflow 设置”里填写描述和启动词（如“开始”）。同步后生成 `$workflow-<id>`，在项目的 Codex 对话里只说启动词即可从第 1 步运行。
- **Skills**：导入、编辑并同步所选项目中的 `SKILL.md`。
- **AI**：通过自然语言创建或调整 Agent、Skill、Action。AI 必要时会先反问，输出始终先进入未发布草稿区。

启动时左侧“项目库”通过 `/api/codex/projects` 只读取 Codex 项目标题，不读取项目文件；也可以点项目库右上角的“+”把任意本地文件夹加入项目库（macOS 会弹出系统文件夹选择器，否则输入完整路径），不必先在 Codex 中打开。用户选择项目并明确点击“授权并导入项目”后，才会只读扫描该项目内的 Agent、Action、Workflow 与 Skills；不会读取项目外对话内容。授权后，进入项目或窗口重新获得焦点时会自动执行只读刷新。

所有新建、编辑和 AI 生成内容都会自动保存到 Studio 的 SQLite 数据库；macOS 默认位置是 `~/Library/Application Support/Workflow Studio/state.sqlite3`。编辑采用约 500ms 防抖保存，切换页面前会立即刷新待写内容。完整 AI 对话和附件不会长期保存。

“发布到 Studio”只把当前资源标记为待同步，不写项目文件。资源页的主按钮“同步到 Codex”会在资源仍是草稿时先自动发布，再弹出写入预览；确认后才写入项目文件。已经发布或同步的资源再次编辑后会回到草稿状态。只有“同步到 Codex”接口可调用项目文件写入器；资源仅属于当前项目，不写入 Codex 全局目录。

每个项目资源请求都把项目 ID 编入 API 路径，由服务端为该请求单独解析项目根目录。服务端不保存跨标签共享的“当前项目”，因此多个浏览器标签可以同时操作不同项目而不会串读。资源保存采用 Studio revision（`If-Match`）做乐观并发控制。Codex 和 Studio 同时修改同一字段时，资源会进入冲突状态并要求用户选择保留哪一侧；不同字段会自动合并。Codex 文件在外部被删除时，Studio 仍保留可恢复记录并标记“源已缺失”。

Agent 的“一键测试”使用当前 Studio 草稿在后台运行：配置兼容 API 时发起一次无工具请求，否则使用 `codex exec --ephemeral --sandbox read-only`。启动接口立即返回，页面切换、刷新或关闭标签不会取消任务；完成后提示“测试通过”或“测试未通过”。它只验证 Agent 入口和指令能否加载并得到响应，不验证真实业务任务的最终结果，也不会保留测试对话。编辑草稿后，旧测试结果自动失效。

## 连接中心与 AI 助手

AI 助手可以使用两种连接：

- **Codex**：通过界面启动 `codex login --device-auth`，只展示 OpenAI 官方链接、一次性设备码与登录状态。Studio 不接触 ChatGPT 密码或访问令牌，调用使用 Codex 套餐额度。模型默认继承 Codex，高级用户可手填模型 ID。
- **自定义 API**：填写地址与 Key，从 `/models` 的真实返回值中选择模型，调用由 API 提供商计费。“保存到本机”默认关闭；不保存时 Key 只存活到当前服务进程结束。保存时写入 Studio 应用数据目录的 `connections.json`，权限设为 `0600`。

当 Codex 和 API 同时可用时，必须明确选择活动提供商；请求失败时不会自动切换。旧版项目根目录中的 `AI Assistant Info.json` 不会迁移、读取或删除。也可通过环境变量为当前进程提供 API 连接：

```bash
cd workflow-studio
OPENAI_API_KEY="你的密钥" OPENAI_MODEL="gpt-5-mini" python3 server.py
```

点击右上角连接状态或本地个人菜单中的“连接设置”打开连接中心。点击 **AI Assistant** 则打开应用使用助手，可直接询问如何创建、授权和编排资源。

AI Assistant 和 AI 创建工作台使用同一套输入交互：`Enter` 换行，`Cmd/Ctrl + Enter` 发送；支持图片、PDF 与常见文本/代码附件，可点击、拖放或粘贴添加；生成中发送按钮会切换为“停止生成”。附件只作为当前对话上下文，不会写入项目。PDF 需要兼容 Responses API 的连接；Codex 本地后备模式支持图片和文本/代码附件，但会对 PDF 给出明确提示。

网页会定时重新检测当前连接。API Key 始终只在本地 Python 服务中使用，不会返回给浏览器或写入项目。

授权并导入一个项目后，在 Agent、Skill、Action 编辑区点击 **AI 创建/调整**：

1. 用自然语言描述需求并回答必要的确认问题；
2. 在右侧直接修改 AI 生成的草稿；
3. 对 Agent 草稿输入样例任务，执行只读临时测试；
4. 点击“发布到 Studio”，把当前版本标记为待同步；
5. 需要写入项目时，再到资源页明确点击“同步到 Codex”。

AI 对话只收到当前项目的资源名称、用户输入和当前草稿，不会读取或带入项目外的 Codex 对话。模型不能指定写入路径，同步目标由服务端固定并校验。最近一份 AI 草稿会保存在 Studio 数据库中，因此切换页面或重启服务后可以恢复。

## A2A 新手教程

0.6.0 为全新状态库首次启动提供一次 8–10 分钟的邀请；升级现有数据库不会自动弹出，可从右上角本地个人菜单手动进入。教程会：

1. 在 Studio 应用数据目录中按需创建 `workflow-studio-tutorial` 隔离项目；
2. 让用户亲手授权只读导入，然后仅在 Studio 数据库预置“需求澄清员”、“方案审校员”和空白 A2A Workflow；
3. 用固定的 Python CLI CSV 导出任务做两次真实模型冒烟测试，完成连线、交接条件、Workflow Dry-run 与发布；
4. 在预览依赖和精确目标文件后，由用户再次确认批量同步。

测试失败不会自动重试，教程进度由后端根据资源、测试和同步的真实状态推进，中途可暂停。完成后可保留练习项目，也可二次确认彻底删除。清理只接受应用数据区内、路径和会话标记完全匹配的非符号链接目录；“教程已完成”状态会保留。

## Codex 同步

资源页可同步当前资源；Project 页可以先批量预览新增、修改、删除、依赖和目标文件，再确认同步。同步顺序为 Skill/Action → Agent → Workflow。缺少尚未同步的依赖时，当前资源会被阻止。

每个资源的多文件写入是独立原子事务：失败时回滚该资源的全部目标文件；批量同步中的其他资源仍可继续，成功项保留，失败项保持待同步。网页删除先进入 `pending_delete`，只有在同步预览中再次确认后才会删除已记录的 Codex 目标文件，Studio 仍保留可恢复记录。

同步 Workflow 时会写入：

- `.codex/workflows/<id>.json`：画布的规范数据源；
- `.agents/skills/workflow-<id>/SKILL.md`：Codex 可调用的 workflow skill；
- `.agents/skills/workflow-<id>/agents/openai.yaml`：skill UI 元数据；
- `AGENTS.md`：只更新两个 managed marker 之间的索引，保留其他手写内容。

Agent 编辑另外写入 `.workflow-studio/agents/<id>.json` 和 `.agents/skills/agent-<id>/`，原入口文件的主体内容会保留。
Action 写入 `.workflow-studio/actions/<id>.json`；Agent 配置只保存允许调用的 Action ID，不把 Action 步骤写进 Agent Prompt。

同步后可在当前项目的 Codex 任务中输入 `$workflow-<id> 你的任务`；设置了启动词的 Workflow 只需发送启动词本身（例如“开始”）。启动词写入 `AGENTS.md` 的 managed 区域和 workflow skill 的描述里；同一项目内的启动词不能重复。生成的 skill 是逐步执行协议：先列出步骤清单，Agent 步骤作为 sub-agent 运行并先读取入口文件，Action 步骤按声明执行，同层步骤可并行，最后逐步汇报 ✅/❌ 状态。

Agent 只有当前草稿版本测试通过后才能同步。Workflow 的“测试 Workflow”是只读 Dry-run：它检查 DAG、资源存在性、Action 授权、Runtime 绑定、拓扑层和交接计划，不运行 Agent 或 Action，也不写项目文件。Workflow 发布和同步时都会复检当前版本；warning 允许通过，error 会阻止操作。

Studio 自己不执行 Action。同步后由 Codex（或下面选择的其他 AI 工具）按 Action 的声明执行：`script` 只运行声明的命令和参数，输入按 stdin 传入；`api` 只请求声明的地址与路径，未配置地址时停止并报告 `endpoint-required`；`mcp` 调用当前会话里已配置的 MCP 工具，否则报告 `mcp-not-configured`。凭据引用只映射为环境变量（例如 `items-api` → `ITEMS_API`），密钥不会写进 Action、skill 或日志。

如果项目更希望用独立的外部 Adapter 执行 `script` Action，可以用 `.workflow-studio/action-runtime.json` 显式绑定，此时生成的 skill 会改为调用 Adapter：

```json
{
  "schemaVersion": 1,
  "id": "my-project-runtime",
  "contractVersion": 1,
  "supports": ["script/process.exec"],
  "argv": ["python3", ".workflow-runtime/action_runtime.py"]
}
```

Studio 只校验绑定版本、能力和项目内脚本路径，并把精确调用命令写入 workflow skill；它不会改写 Adapter 或把 Adapter/绑定配置计入 `syncedFiles`。

### 同步到其他 AI 工具

项目页的“同步到哪些 AI 工具”决定额外写入哪些位置（设置保存在 Studio，不写项目文件）：

- **Codex、OpenCode**：始终支持，读取 `AGENTS.md` 和 `.agents/skills/`；
- **Claude Code**：同步时把生成的 skill 镜像到 `.claude/skills/`；项目已有 `CLAUDE.md` 时在其中加入导入 `@AGENTS.md` 的 managed 区域（没有 `CLAUDE.md` 时 Claude Code 会直接读取 `AGENTS.md`）；
- **Qwen Code**：同步时镜像到 `.qwen/skills/`，并在 `QWEN.md` 写入同样的 managed 区域。

DeepSeek、Qwen 等模型通过上面这些工具使用。新勾选一个工具时，可以确认立即把已经同步的 Workflow 和 Agent 写入它的位置；之后每次同步都会一起更新，删除资源时也会一并删除镜像的 skill。

画布连接沿用常见节点编辑器交互：从节点右侧端口按住拖到目标节点左侧端口。点击已有连线会选中并显示“删除连线”，也可以使用 Delete 或 Backspace。

## 测试

```bash
studio_test_dir=$(mktemp -d)
WORKFLOW_STUDIO_STATE_PATH="$studio_test_dir/state.sqlite3" python3 -m unittest discover -s tests -v
```

使用隔离状态路径可以避免测试污染真实 Studio 数据库。导入的第三方 Agent 仍应在执行前由你审查；AI 草稿也应先测试和检查，再发布到 Studio 并显式同步到 Codex。

## License

[MIT](LICENSE)
