const state = {
  language: localStorage.getItem("workflow-studio-language") || "zh",
  project: null,
  projects: [],
  selectedProjectId: null,
  syncingProject: false,
  projectEpoch: 0,
  projectSelectionToken: 0,
  projectImportToken: 0,
  authorizedProjectIds: new Set(readStoredArray("workflow-studio-authorized-projects")),
  resourceRevisions: { workflows: {}, agents: {}, actions: {}, skills: {} },
  agents: [],
  actions: [],
  skills: [],
  workflows: [],
  section: "projects",
  selectedAgent: null,
  selectedAction: null,
  selectedSkill: null,
  workflow: {
    id: "delivery-flow",
    name: "多 Agent 交付流",
    description: "研究、实现与审查的协作流程",
    nodes: [],
    edges: [],
    updatedAt: ""
  },
  selectedNodeId: null,
  selectedEdgeId: null,
  // Canvas view (pan + zoom) is presentation only: never persisted and never
  // marks the workflow dirty. Node positions always stay in graph space.
  view: { s: 1, tx: 0, ty: 0 },
  viewKey: null,
  viewFitPending: false,
  // True once the person pans or zooms by hand: automatic refits then stay out of the way.
  viewTouched: false,
  spaceHeld: false,
  mode: "select",
  connectSource: null,
  dirty: true,
  autosave: { timers: {}, dirty: new Set(), inFlight: {} },
  resourceLoadTokens: { workflows: 0, agents: 0, actions: 0, skills: 0 },
  workflowTest: null,
  syncPreview: null,
  syncPreviewHasDelete: false,
  conflictTarget: null,
  agentTests: { jobs: new Map(), polling: false, timer: null, notified: new Set(readStoredArray("workflow-studio-notified-agent-tests")) },
  dragging: null,
  connections: null,
  onboarding: { status: null, active: false, startedHere: false, preparedStep: "", pollTimer: null, completionShown: false },
  ai: { configured: false, provider: "", model: "", kind: "agent", messages: [], draft: null, studioResource: null, targetId: "", projectId: null, busy: false, attachments: [], request: null, returnSection: "projects", config: null, attachmentGeneration: 0, pendingAttachmentReads: 0, draftLoadGeneration: 0, sessions: Object.create(null) },
  guide: { messages: [], busy: false, attachments: [], request: null, attachmentGeneration: 0, pendingAttachmentReads: 0 },
  actionConnection: { sequence: 0, controller: null },
  actionEditorSourceId: null,
  connectionDrag: null
};

const translations = {
  zh: {
    railProjects: "项目", defaultModel: "默认模型", publishBeforeSync: "先发布到 Studio 后可同步", awaitingSyncConfirm: "等待用户确认同步", removeFromLibrary: "从项目库移除",
    syncTargetsTitle: "同步到哪些 AI 工具", syncTargetsBody: "Codex 和 OpenCode 始终读取 AGENTS.md 与 .agents/skills。勾选其他工具后，同步时会把 Workflow 和 Agent 也写到它们读取的位置；DeepSeek、Qwen 等模型通过这些工具使用。",
    targetAlways: "始终写入", targetOnSync: "同步时写入", targetDetected: "项目中已检测到",
    pendingSyncTitle: "待同步资源", pendingSyncBody: "发布只保存在 Studio；在这里预览并确认后才会修改 Codex 项目文件。", previewBatchSync: "预览批量同步", noPendingSync: "Studio 与 Codex 当前没有待确认的同步项。",
    projectsInLibrary: count => `项目库共 ${count} 个项目`, nodesAndConnections: (nodes, edges) => `${nodes} 个节点 · ${edges} 条连线`, refreshProjectDetails: "刷新项目资源",
    copyInvocation: "复制调用方式", syncCodex: "同步到 Codex", publishStudio: "发布到 Studio", draftSyncHint: "当前资源还是草稿，请先点击“发布到 Studio”", testWorkflow: "测试 Workflow", aiAssistant: "AI 助手", aiCreateAdjust: "AI 创建/调整",
    smokeTest: "一键测试", syncAgent: "同步 Agent", aiCreate: "AI 创建", newJson: "新建 JSON",
    saveAction: "保存 Action", syncSkill: "同步 Skill", selectProject: "选择一个项目",
    titlesOnly: "这里只自动读取项目名称，不会读取项目文件。", syncProjectDetails: "授权并导入项目",
    syncProjectExplain: "首次确认后只读导入所选项目内的 Agent、Action、Workflow 和 Skill；之后打开项目时自动刷新，不会读取项目外对话。",
    pathAfterSync: "授权导入后显示项目路径", selectTool: "选择", connectTool: "连接",
    layoutTool: "排列", fitTool: "适应", deleteConnection: "删除连线",
    zoomIn: "放大", zoomOut: "缩小", zoomLabel: percent => `缩放 ${percent}%，点击适应画布`,
    workflowSettings: "Workflow 设置", workflowDescription: "描述", startPhrases: "启动词", startPhrasePlaceholder: "例如：开始",
    startPhrasesHelp: "同步到 Codex 后，在这个项目的 Codex 对话里只说启动词，Codex 就会按这张图从第 1 步开始运行。多个启动词用逗号分隔。",
    useDefaultStart: "使用“开始”", publishOnly: "仅发布到 Studio（不写入项目）",
    addFirstNode: "从左侧加入 Agent 或 Action", dragConnectHelp: "从节点右侧端口拖到另一个节点左侧端口即可连接。",
    chooseLanguage: "选择语言", syncProjects: "读取 Codex 项目…", searchResources: "搜索名称或路径", waitingSync: "等待同步",
    configureAllowedResources: "配置允许调用的资源", editDeterministicAction: "编辑确定性执行单元",
    orchestrateResources: "编排 Agent 与 Action", editProjectKnowledge: "编辑项目知识能力",
    chooseAgent: "选择一个 Agent", enterAgentEditor: "从左侧 Agent 库进入编辑", agentName: "Agent 名称", modelPreference: "模型偏好",
    inheritModel: "继承当前模型", preferSpeed: "偏速度", balanced: "均衡", preferDepth: "偏深度", discoveryDescription: "发现描述",
    behaviorOverride: "本地行为覆盖", behaviorPlaceholder: "追加到原 Agent 入口之上的项目级约束", allowedActions: "允许调用的 Actions",
    allowedActionsHelp: "这里只授予调用权限；Action 的执行定义在项目 Action 库中维护。", linkedSkillsHelp: "选择这个 Agent 执行时可以调用的项目 Skill。",
    createOrChooseAction: "创建或选择 Action", actionDefinition: "项目级、可复用、可执行的 JSON 定义", actionJson: "Action JSON",
    actionJsonPlaceholder: "点击“新建 JSON”，或使用 AI 根据自然语言生成 Action。", requiredFields: "必填字段",
    credentialWarning: "凭据只能填写引用名称，不能把真实密码或 Token 写进 Action。", chooseSkill: "选择一个 Skill",
    skillDiscovery: "同步到 Codex 后，项目级 Skill 才会被发现", skillName: "Skill 名称", type: "类型", triggerDescription: "触发描述", skillInstructions: "Skill 指令",
    inspector: "配置", chooseNode: "选择一个节点", editNodeHelp: "编辑角色、指令和执行入口。", canvasName: "画布名称", responsibility: "职责",
    entrypoint: "执行入口", model: "模型", authorizedAgent: "授权调用 Agent", allowParallel: "允许同层并行", removeCanvas: "从画布移除",
    selectedConnection: "已选择连接", handoffCondition: "交接条件", removeConnection: "删除连接", codexSync: "Codex 同步",
    runInCodex: "在 Codex 中运行", runPrompt: "同步到 Codex 后，在当前项目对话中输入：", copy: "复制",
    runHelp: "Codex 会按依赖关系启动 sub-agent，并把上游结果传给下游节点。", done: "完成",
    testAgent: "测试 Agent", startingTest: "正在启动只读测试…", testBoundary: "仅验证入口、指令与 Codex 调用链能否跑通，不验证最终业务目标。",
    connectionSettings: "连接设置", apiConfigHelp: "API Key 默认只保留到服务进程结束；只有勾选“保存到本机”才会写入 Studio 应用数据目录。",
    apiUrl: "API 地址", apiKey: "API Key", savedKeyPlaceholder: "已保存时留空即可", fetchModelsFirst: "先获取模型", fetchModels: "获取模型",
    modelsHelp: "读取该 API 的 /models 返回的可选模型；API Key 不会暴露给网页。", saveAndConnect: "保存并连接", guidePlaceholder: "例如：我应该先创建 Agent 还是 Action？",
    guideHelp: "询问如何使用 Workflow Studio", send: "发送", stopGenerating: "停止生成",
    apiPreset: "API 预设", apiPresetHelp: "HTTP 请求 + 健康检测", mcpPreset: "MCP 预设", mcpPresetHelp: "Streamable HTTP 工具调用",
    localProfile: "本机个人菜单 · 无账户体系", beginnerTutorial: "新手教程", language: "语言", help: "帮助", about: "关于", close: "关闭",
    connectionCenterHelp: "选择 Codex 官方设备码登录，或连接自己的兼容 API。两者同时可用时，需要明确选择当前提供商。",
    codexBilling: "使用 Codex 套餐额度", apiBilling: "由 API 提供商计费", codexAuthHelp: "通过 OpenAI 官方设备码页登录。Studio 不接触账号密码。", codexModel: "Codex 模型（高级）", codexModelPlaceholder: "留空则继承 Codex 默认模型", openOfficialPage: "打开 OpenAI 官方页面", deviceLogin: "设备码登录", useCodex: "使用 Codex", customApi: "自定义 API", saveKeyLocally: "将 API Key 保存到本机（默认关闭）", forgetSavedKey: "删除已保存 Key", saveAndUseApi: "保存并使用 API",
    later: "稍后继续", startTutorial: "开始教程", restart: "重新开始", continue: "继续", cancel: "取消", retry: "手动重试", openConnections: "打开连接中心", keepTutorial: "保留练习项目", deleteTutorial: "删除全部教程数据", returnProjects: "返回项目库，导入我的项目", confirmDeleteTutorial: "确认彻底删除", aboutCopy: "本地 Codex 项目的可视化编辑、校验与显式同步层。Workflow 不在 Studio 内运行。",
    connectionDiagnostic: "联通诊断", connectionNotChecked: "尚未检测。只做健康请求或 MCP 握手，不执行 Action。", checkConnection: "检测联通",
    connected: "已连接", disconnected: "未连接", clickToConfigure: "点击配置", waitingDetection: "等待自动检测",
    lastChecked: "最近检测", unsaved: "正在编辑", synced: "已保存到 Studio", waitingValidation: "等待校验",
    syncingResources: "正在只读导入项目资源…", detailsSynced: "项目已授权；Studio 草稿与 Codex 文件彼此独立。",
    confirmManualSync: "目前只读取了项目名称；请先授权并导入项目。", syncing: "导入中…",
    resyncDetails: "刷新 Codex 导入", projectNameSynced: "项目名称已读取", projectDetailsSynced: "已授权导入",
    codexProjectsCount: count => `${count} 个 Codex 项目`, projectAgentsCount: count => `项目内 ${count} Agents`, projectActionsCount: count => `项目内 ${count} Actions`, projectSkillsCount: (count, generated = 0) => `项目内 ${count} Skills${generated ? `（另有 ${generated} 个 Studio 生成）` : ""}`,
    noMatchingAgent: "没有匹配的 Agent。\n把 agent 文件夹复制到项目后点击刷新。",
    noSavedWorkflow: "还没有已保存的 Workflow", noProjectAction: "还没有项目 Action",
    authorizedAgents: count => `${count} Agent 已授权`, notAuthorized: "尚未被 Agent 授权",
    savedWorkflowsLabel: "已保存的 Workflow", agentsLabel: "Agents", authorizedActionsLabel: "Agent 已授权的 Actions",
    lockedAction: "未授权", projectUnavailable: "项目文件夹不可用",
    nodeAriaLabel: (label, type) => `${label}，${type} 节点`, edgeAriaLabel: (from, to, condition) => `连接：${from} 到 ${to}${condition ? `（${condition}）` : ""}`,
    sections: {
      projects: ["", "项目库", "项目名称已自动读取；选中后可授权导入详情。", "Codex 项目库", "选择项目后导入详细资源"],
      workflow: ["", "画布资源", "点击加入画布，或直接拖拽。", "多 Agent Workflow", "编辑与同步本地编排"],
      agents: ["", "Agent 库", "点击 Agent 配置允许调用的 Actions 与关联 Skills。", "Agent 编辑器", "负责思考、判断与选择 Action"],
      actions: ["", "Action 库", "创建独立 JSON Action，或选择已有 Action 编辑。", "Action 编辑器", "定义确定性的项目执行单元"],
      skills: ["", "Skill 库", "编辑 Studio 草稿；同步后写入项目 SKILL.md。", "Skill 库", "编辑并显式同步项目级能力"],
      ai: ["", "AI 创建", "从自然语言生成可测试、可编辑的项目资源草稿。", "AI 创建工作台", "澄清需求、测试草稿、确认后发布"]
    }
  },
  en: {
    railProjects: "Projects", defaultModel: "default model", publishBeforeSync: "Publish to Studio before syncing", awaitingSyncConfirm: "Waiting for your sync confirmation", removeFromLibrary: "Remove from library",
    syncTargetsTitle: "Which AI tools to sync to", syncTargetsBody: "Codex and OpenCode always read AGENTS.md and .agents/skills. Tick another tool and syncing also writes Workflows and Agents where it reads them; models such as DeepSeek and Qwen are used through these tools.",
    targetAlways: "Always written", targetOnSync: "Written on sync", targetDetected: "Detected in project",
    pendingSyncTitle: "Pending sync", pendingSyncBody: "Publishing only saves in Studio. Codex project files change only after you preview and confirm here.", previewBatchSync: "Preview batch sync", noPendingSync: "Nothing is waiting to sync between Studio and Codex.",
    projectsInLibrary: count => `${count} ${count === 1 ? "project" : "projects"} in library`, nodesAndConnections: (nodes, edges) => `${nodes} ${nodes === 1 ? "node" : "nodes"} · ${edges} ${edges === 1 ? "connection" : "connections"}`, refreshProjectDetails: "Refresh project resources",
    copyInvocation: "Copy invocation", syncCodex: "Sync to Codex", publishStudio: "Publish to Studio", draftSyncHint: "This resource is still a draft. Publish to Studio first.", testWorkflow: "Test Workflow", aiAssistant: "AI Assistant", aiCreateAdjust: "Create / adjust with AI",
    smokeTest: "Smoke test", syncAgent: "Sync Agent", aiCreate: "Create with AI", newJson: "New JSON",
    saveAction: "Save Action", syncSkill: "Sync Skill", selectProject: "Select a project",
    titlesOnly: "Only project names are discovered automatically. Project files are not read.", syncProjectDetails: "Authorize & import",
    syncProjectExplain: "The first confirmation imports project Agents, Actions, Workflows, and Skills read-only. Authorized projects refresh when opened. Conversations outside the project are never read.",
    pathAfterSync: "The project path appears after authorization", selectTool: "Select", connectTool: "Connect",
    layoutTool: "Layout", fitTool: "Fit", deleteConnection: "Delete connection",
    zoomIn: "Zoom in", zoomOut: "Zoom out", zoomLabel: percent => `Zoom ${percent}%, click to fit`,
    workflowSettings: "Workflow settings", workflowDescription: "Description", startPhrases: "Start phrases", startPhrasePlaceholder: "e.g. start",
    startPhrasesHelp: "After syncing to Codex, sending only a start phrase in this project's Codex chat runs this workflow from step 1. Separate several phrases with commas.",
    useDefaultStart: "Use “开始”", publishOnly: "Publish to Studio only (no project files)",
    addFirstNode: "Add an Agent or Action from the left", dragConnectHelp: "Drag from a node's right port to another node's left port to connect them.",
    chooseLanguage: "Choose language", syncProjects: "Reading Codex projects…", searchResources: "Search names or paths", waitingSync: "Waiting to sync",
    configureAllowedResources: "Configure allowed resources", editDeterministicAction: "Edit a deterministic operation",
    orchestrateResources: "Orchestrate Agents and Actions", editProjectKnowledge: "Edit project knowledge",
    chooseAgent: "Select an Agent", enterAgentEditor: "Open an Agent from the library to edit it", agentName: "Agent name", modelPreference: "Model preference",
    inheritModel: "Inherit current model", preferSpeed: "Prefer speed", balanced: "Balanced", preferDepth: "Prefer depth", discoveryDescription: "Discovery description",
    behaviorOverride: "Local behavior override", behaviorPlaceholder: "Add project-level constraints above the original Agent entrypoint", allowedActions: "Allowed Actions",
    allowedActionsHelp: "This only grants permission. Executable definitions are maintained in the project Action Library.", linkedSkillsHelp: "Select the project Skills this Agent can use.",
    createOrChooseAction: "Create or select an Action", actionDefinition: "A project-level, reusable, executable JSON definition", actionJson: "Action JSON",
    actionJsonPlaceholder: "Select “New JSON” or use AI to generate an Action from natural language.", requiredFields: "Required fields",
    credentialWarning: "Use credential reference names only. Never put real passwords or tokens in an Action.", chooseSkill: "Select a Skill",
    skillDiscovery: "After syncing to Codex, project Skills can be discovered", skillName: "Skill name", type: "Type", triggerDescription: "Trigger description", skillInstructions: "Skill instructions",
    inspector: "Inspector", chooseNode: "Select a node", editNodeHelp: "Edit its role, instructions, and entrypoint.", canvasName: "Canvas name", responsibility: "Role",
    entrypoint: "Entrypoint", model: "Model", authorizedAgent: "Authorized calling Agent", allowParallel: "Allow same-level parallelism", removeCanvas: "Remove from canvas",
    selectedConnection: "Connection selected", handoffCondition: "Handoff condition", removeConnection: "Delete connection", codexSync: "Codex sync",
    runInCodex: "Run in Codex", runPrompt: "After syncing to Codex, enter this in a conversation for the current project:", copy: "Copy",
    runHelp: "Codex starts sub-agents by dependency and passes upstream results to downstream nodes.", done: "Done",
    testAgent: "Test Agent", startingTest: "Starting a read-only test…", testBoundary: "Only verifies that the entrypoint, instructions, and Codex call chain run. It does not validate the final business outcome.",
    connectionSettings: "Connection settings", apiConfigHelp: "The API key lasts only for this service process by default. It is written under Studio application data only when Save on this device is checked.",
    apiUrl: "API URL", apiKey: "API Key", savedKeyPlaceholder: "Leave blank to keep the saved key", fetchModelsFirst: "Fetch models first", fetchModels: "Fetch models",
    modelsHelp: "Reads the selectable models returned by this API's /models endpoint without exposing the API key to the page.", saveAndConnect: "Save and connect", guidePlaceholder: "For example: should I create an Agent or an Action first?",
    guideHelp: "Ask how to use Workflow Studio", send: "Send", stopGenerating: "Stop generating",
    apiPreset: "API preset", apiPresetHelp: "HTTP request + health check", mcpPreset: "MCP preset", mcpPresetHelp: "Streamable HTTP tool call",
    localProfile: "Local profile · no account", beginnerTutorial: "Beginner tutorial", language: "Language", help: "Help", about: "About", close: "Close",
    connectionCenterHelp: "Use official Codex device authorization or your own compatible API. When both are available, explicitly choose the active provider.",
    codexBilling: "Uses your Codex plan allowance", apiBilling: "Billed by your API provider", codexAuthHelp: "Sign in on OpenAI's official device page. Studio never sees your account password.", codexModel: "Codex model (advanced)", codexModelPlaceholder: "Leave blank to inherit the Codex default", openOfficialPage: "Open the official OpenAI page", deviceLogin: "Device-code login", useCodex: "Use Codex", customApi: "Custom API", saveKeyLocally: "Save the API key on this device (off by default)", forgetSavedKey: "Delete saved key", saveAndUseApi: "Save and use API",
    later: "Continue later", startTutorial: "Start tutorial", restart: "Start over", continue: "Continue", cancel: "Cancel", retry: "Retry manually", openConnections: "Open connection center", keepTutorial: "Keep practice project", deleteTutorial: "Delete all tutorial data", returnProjects: "Return to Projects and import mine", confirmDeleteTutorial: "Delete permanently", aboutCopy: "A local visual editing, validation, and explicit sync layer for Codex projects. Workflows do not run inside Studio.",
    connectionDiagnostic: "Connection diagnostic", connectionNotChecked: "Not checked. This only runs a health request or MCP handshake; it never executes the Action.", checkConnection: "Check connection",
    connected: "Connected", disconnected: "Disconnected", clickToConfigure: "Click to configure", waitingDetection: "Waiting for automatic check",
    lastChecked: "Last checked", unsaved: "Editing", synced: "Saved to Studio", waitingValidation: "Waiting for validation",
    syncingResources: "Importing project resources read-only…", detailsSynced: "This project is authorized. Studio drafts and Codex files remain separate.",
    confirmManualSync: "Only the project name is visible. Authorize the first read-only import.", syncing: "Importing…",
    resyncDetails: "Refresh Codex import", projectNameSynced: "Project name discovered", projectDetailsSynced: "Authorized import",
    codexProjectsCount: count => `${count} Codex project${count === 1 ? "" : "s"}`, projectAgentsCount: count => `${count} project Agent${count === 1 ? "" : "s"}`, projectActionsCount: count => `${count} project Action${count === 1 ? "" : "s"}`, projectSkillsCount: (count, generated = 0) => `${count} project Skill${count === 1 ? "" : "s"}${generated ? ` (+${generated} generated by Studio)` : ""}`,
    noMatchingAgent: "No matching Agent.\nCopy an agent folder into the project, then refresh.",
    noSavedWorkflow: "No saved Workflow yet", noProjectAction: "No project Action yet",
    authorizedAgents: count => `Allowed by ${count} Agent${count === 1 ? "" : "s"}`, notAuthorized: "Not allowed by an Agent",
    savedWorkflowsLabel: "Saved Workflows", agentsLabel: "Agents", authorizedActionsLabel: "Actions allowed by Agents",
    lockedAction: "Not authorized", projectUnavailable: "Project folder unavailable",
    nodeAriaLabel: (label, type) => `${label}, ${type} node`, edgeAriaLabel: (from, to, condition) => `Connection: ${from} to ${to}${condition ? ` (${condition})` : ""}`,
    sections: {
      projects: ["", "Projects", "Project names are discovered automatically; select one to authorize and import details.", "Codex Projects", "Select a project, then import its resources"],
      workflow: ["", "Canvas resources", "Click to add to the canvas, or drag directly.", "Multi-Agent Workflow", "Edit and sync local orchestration"],
      agents: ["", "Agent Library", "Select an Agent to configure allowed Actions and linked Skills.", "Agent Editor", "Think, decide, and choose Actions"],
      actions: ["", "Action Library", "Create an independent JSON Action or edit an existing one.", "Action Editor", "Define deterministic project operations"],
      skills: ["", "Skill Library", "Edit Studio drafts; syncing writes the project SKILL.md.", "Skill Library", "Edit and explicitly sync project guidance"],
      ai: ["", "AI Creation", "Generate testable, editable project resource drafts from natural language.", "AI Creation Studio", "Clarify, test, and publish when ready"]
    }
  }
};

// The server reports Codex's inherited model as the Chinese placeholder "默认模型".
function modelLabel(model) {
  return !model || model === "默认模型" ? tr("defaultModel") : model;
}

function tr(key, ...args) {
  const value = translations[state.language]?.[key] ?? translations.zh[key] ?? key;
  return typeof value === "function" ? value(...args) : value;
}

function closeProfileMenu() {
  $("#profile-menu")?.classList.add("hidden");
  $("#profile-toggle")?.setAttribute("aria-expanded", "false");
}

const closeLanguageMenu = closeProfileMenu;

function applyLanguage(language) {
  state.language = language === "en" ? "en" : "zh";
  localStorage.setItem("workflow-studio-language", state.language);
  document.documentElement.lang = state.language === "zh" ? "zh-CN" : "en";
  $("#profile-toggle").setAttribute("aria-label", state.language === "zh" ? "打开个人菜单" : "Open profile menu");
  $("#close-ai-config").setAttribute("aria-label", tr("close"));
  $("#codex-model-id").placeholder = tr("codexModelPlaceholder");
  $("#device-auth-link").textContent = tr("openOfficialPage");
  document.querySelectorAll("[data-i18n]").forEach(element => {
    element.textContent = tr(element.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach(element => {
    element.placeholder = tr(element.dataset.i18nPlaceholder);
  });
  document.querySelectorAll("[data-i18n-aria-label]").forEach(element => {
    element.setAttribute("aria-label", tr(element.dataset.i18nAriaLabel));
  });
  document.querySelectorAll("[data-language]").forEach(button => {
    const selected = button.dataset.language === state.language;
    button.classList.toggle("active", selected);
    button.setAttribute("aria-current", selected ? "true" : "false");
  });
  const badge = $("#save-state");
  if (badge) badge.innerHTML = `<i></i> ${state.dirty ? tr("unsaved") : tr("synced")}`;
  if (!state.selectedAgent) {
    $("#agent-editor-title").textContent = tr("chooseAgent");
    $("#agent-editor-path").textContent = tr("enterAgentEditor");
  }
  if (!state.selectedAction) {
    $("#action-editor-title").textContent = tr("createOrChooseAction");
    $("#action-editor-path").textContent = tr("actionDefinition");
  }
  if (!state.selectedSkill) {
    $("#skill-editor-title").textContent = tr("chooseSkill");
    $("#skill-editor-path").textContent = tr("skillDiscovery");
  }
  setSection(state.section);
  applyView();
  renderProjectList();
  renderSelectedProject();
  renderProjectTargets();
  setComposerBusy("guide", state.guide.busy);
  setComposerBusy("ai", state.ai.busy);
  renderOnboardingCopy();
  loadAIStatus();
}

const $ = selector => document.querySelector(selector);
const icon = name => `<svg class="i" aria-hidden="true"><use href="#i-${name}"></use></svg>`;
const statusDot = `<span class="status-dot" aria-hidden="true"></span>`;
const canvas = $("#canvas");
const nodeLayer = $("#node-layer");
const edgePaths = $("#edge-paths");
const draftEdge = $("#draft-edge");
const canvasViewport = $("#canvas-viewport");
const nodeWidth = 190;
// Room between columns for a full-width handoff label (.edge-label max-width 168px) plus breathing space.
const nodeColumnStep = nodeWidth + 200;
const nodeHeight = 92;
const viewPad = 24;
const minZoom = 0.25;
const maxZoom = 2;
const zoomStep = 1.2;
// Generous graph area a node may be carried into; the view pans to follow it.
const graphLimit = 8000;

function readStoredArray(key) {
  try {
    const value = JSON.parse(localStorage.getItem(key) || "[]");
    return Array.isArray(value) ? value : [];
  } catch (_) {
    return [];
  }
}

function persistStoredSet(key, values) {
  localStorage.setItem(key, JSON.stringify([...values]));
}

function uid(prefix) {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
}

function slugify(value) {
  return value.trim().toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fff_-]+/g, "-")
    .replace(/[-_]{2,}/g, "-")
    .replace(/^[-_]+|[-_]+$/g, "") || "workflow";
}

async function requestApi(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) }
  });
  const payload = await response.json();
  if (!response.ok) {
    const error = new Error(payload.error || `HTTP ${response.status}`);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return payload;
}

function globalApi(path, options = {}) {
  return requestApi(path, options);
}

async function projectApi(projectId, path, options = {}) {
  if (!projectId) throw new Error("缺少项目上下文，请重新打开当前项目。");
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const payload = await requestApi(`/api/projects/${encodeURIComponent(projectId)}${normalizedPath}`, {
    ...options,
    headers: { ...(options.headers || {}), "X-Workflow-Studio-Project-Id": projectId }
  });
  if (payload?.projectId && payload.projectId !== projectId) {
    throw new Error("项目响应上下文不一致，已忽略该响应。");
  }
  return payload;
}

function captureProjectContext() {
  const projectId = state.project?.id || null;
  const selectedProject = state.projects.find(project => project.id === state.selectedProjectId);
  if (!projectId || state.selectedProjectId !== projectId || !projectIsAuthorized(selectedProject)) return null;
  return { projectId, epoch: state.projectEpoch };
}

function isCurrentProjectContext(context) {
  return Boolean(context
    && state.project?.id === context.projectId
    && state.selectedProjectId === context.projectId
    && state.projectEpoch === context.epoch);
}

function requireProjectContext() {
  const context = captureProjectContext();
  if (!context || state.selectedProjectId !== context.projectId) {
    throw new Error("请先选择项目并完成首次授权导入。");
  }
  return context;
}

const aiCreationKinds = new Set(["agent", "skill", "action"]);

function cloneAIValue(value) {
  if (value === null || value === undefined) return value;
  try {
    return JSON.parse(JSON.stringify(value));
  } catch (_) {
    return null;
  }
}

function cacheAICreationSession(projectId) {
  if (!projectId || state.ai.projectId !== projectId) return false;
  const messages = state.ai.messages.filter(message => !message.loading);
  if (!messages.length && !state.ai.draft && !state.ai.studioResource) return false;
  state.ai.sessions[projectId] = {
    kind: aiCreationKinds.has(state.ai.kind) ? state.ai.kind : "agent",
    messages: cloneAIValue(messages) || [],
    draft: cloneAIValue(state.ai.draft),
    studioResource: cloneAIValue(state.ai.studioResource),
    targetId: state.ai.targetId || ""
  };
  return true;
}

function restoreAICreationSession(projectId) {
  const session = state.ai.sessions[projectId];
  if (!session) return false;
  state.ai.draftLoadGeneration += 1;
  state.ai.kind = aiCreationKinds.has(session.kind) ? session.kind : "agent";
  state.ai.projectId = projectId;
  state.ai.targetId = session.targetId || "";
  state.ai.studioResource = cloneAIValue(session.studioResource);
  state.ai.draft = cloneAIValue(session.draft);
  state.ai.messages = cloneAIValue(session.messages) || [];
  state.ai.attachments = [];
  state.ai.request = null;
  state.ai.busy = false;
  if (!state.ai.messages.length) state.ai.messages = [{ role: "assistant", content: aiWelcome(state.ai.kind, Boolean(state.ai.draft)) }];
  const collection = `${state.ai.kind}s`;
  if (state.ai.studioResource?.id) updateSummaryResource(collection, state.ai.studioResource);
  if (document.querySelector(composerConfig.ai.files)) $(composerConfig.ai.files).value = "";
  renderComposerAttachments("ai");
  updateComposerButton("ai");
  renderAIWorkspace();
  return true;
}

function resetAICreationClientState() {
  state.ai.attachmentGeneration += 1;
  state.ai.pendingAttachmentReads = 0;
  composerFileQueues.ai = Promise.resolve();
  state.ai.draftLoadGeneration += 1;
  state.ai.kind = "agent";
  state.ai.projectId = null;
  state.ai.targetId = "";
  state.ai.draft = null;
  state.ai.studioResource = null;
  state.ai.messages = [];
  state.ai.attachments = [];
  state.ai.request = null;
  state.ai.busy = false;
  if (document.querySelector(composerConfig.ai.files)) $(composerConfig.ai.files).value = "";
  setComposerStatus("ai", "");
  renderComposerAttachments("ai");
  renderAIMessages();
  renderAIDraft();
  updateComposerButton("ai");
  syncAIOrientation();
}

function emptyResourceRevisions() {
  return { workflows: {}, agents: {}, actions: {}, skills: {} };
}

function resourceFrom(payload, legacyKey) {
  const resource = payload?.resource ?? payload?.[legacyKey] ?? null;
  if (!resource || typeof resource !== "object") return resource;
  ["status", "resourceStatus", "studioRevision", "baselineHash", "conflicts", "testStatus"].forEach(key => {
    if (payload?.[key] !== undefined && resource[key] === undefined) resource[key] = payload[key];
  });
  return resource;
}

function revisionFrom(payload, resource = null) {
  return payload?.studioRevision ?? resource?.studioRevision ?? payload?.revision ?? null;
}

function resourceStatus(resource) {
  return String(resource?.status || resource?.resourceStatus || "synced").toLowerCase().replaceAll("-", "_");
}

function resourceHasDeleteIntent(resource) {
  return resourceStatus(resource) === "pending_delete"
    || (resource?.syncIntent || resource?.sync_intent) === "delete";
}

const statusCopies = {
  zh: {
    synced: "已同步", draft: "草稿", ready: "待同步", conflict: "有冲突",
    pending_delete: "待删除", source_missing: "源已缺失", sync_failed: "同步失败"
  },
  en: {
    synced: "Synced", draft: "Draft", ready: "Ready to sync", conflict: "Conflict",
    pending_delete: "Pending delete", source_missing: "Source missing", sync_failed: "Sync failed"
  }
};

function statusCopy(resource) {
  const status = resourceStatus(resource);
  return (statusCopies[state.language] || statusCopies.zh)[status] || status;
}

function statusBadge(resource, extraClass = "list-status-badge") {
  const status = resourceStatus(resource);
  const copy = escapeHtml(statusCopy(resource));
  return `<span class="${extraClass} ${escapeHtml(status)}" title="${copy}">${copy}</span>`;
}

function normalizeTestStatus(value) {
  const raw = typeof value === "object" && value ? (value.status || (value.passed === true ? "passed" : value.passed === false ? "failed" : "")) : value;
  const status = String(raw || "untested").toLowerCase().replaceAll("-", "_");
  if (["queued", "pending", "running", "started"].includes(status)) return "running";
  if (["success", "succeeded", "complete", "completed", "passed"].includes(status)) return "passed";
  if (["error", "failed", "failure", "timed_out", "timeout", "expired"].includes(status)) return "failed";
  if (["stale", "needs_retest", "outdated"].includes(status)) return "stale";
  if (["interrupted", "cancelled", "canceled"].includes(status)) return "interrupted";
  return "untested";
}

const testStatusCopies = {
  zh: { untested: "未测试", running: "测试中", passed: "已通过", failed: "未通过", stale: "需重测", interrupted: "已中断" },
  en: { untested: "Untested", running: "Testing", passed: "Passed", failed: "Failed", stale: "Retest needed", interrupted: "Interrupted" }
};

function updateEditorStatus(kind, resource) {
  const badge = $(`#${kind}-resource-status`);
  if (badge) {
    const status = resourceStatus(resource);
    badge.className = `resource-status-badge ${status}`;
    badge.textContent = statusCopy(resource);
  }
  if (kind === "agent") {
    const testBadge = $("#agent-test-status");
    const testStatus = normalizeTestStatus(resource?.testStatus);
    testBadge.className = `test-status-badge ${testStatus}`;
    testBadge.textContent = (testStatusCopies[state.language] || testStatusCopies.zh)[testStatus];
    // A second click would only queue a duplicate run of the same draft.
    const testButton = $("#test-agent");
    if (testButton) testButton.disabled = testStatus === "running";
  }
  updateResourceActionButtons(`${kind}s`, resource);
}

function updateResourceActionButtons(kind, resource) {
  const singular = kind.slice(0, -1);
  const resolveButton = $(`#resolve-${singular}`);
  const deleteButton = $(`#delete-${singular}`);
  const syncButton = $(`#save-${singular}`);
  const draftHint = $(`#draft-sync-${singular}`);
  const status = resourceStatus(resource);
  const isDraft = Boolean(resource) && status === "draft";
  if (resolveButton) resolveButton.classList.toggle("hidden", status !== "conflict");
  if (deleteButton) deleteButton.classList.toggle("hidden", !resource || ["conflict", "pending_delete", "source_missing"].includes(status));
  // Sync is the single next step even for drafts: it publishes first, then asks for confirmation.
  if (syncButton) syncButton.classList.toggle("hidden", !resource);
  if (draftHint) draftHint.classList.toggle("hidden", !isDraft);
}

function rememberResourceRevision(kind, resourceId, revision) {
  if (!resourceId || revision === undefined || revision === null || revision === "") return;
  state.resourceRevisions[kind][resourceId] = revision;
}

function revisionHeaders(revision, headers = {}) {
  return revision === undefined || revision === null || revision === ""
    ? headers
    : { ...headers, "If-Match": String(revision) };
}

function isRevisionConflict(error) {
  return error?.status === 409 && Boolean(error.payload?.revisionConflict);
}

function showRevisionConflict(label) {
  toast(`${label} 已在另一个窗口更新。请重新打开该资源，确认最新内容后再保存。`, true);
}

function markDirty() {
  state.dirty = true;
  state.workflow.updatedAt = new Date().toISOString();
  state.workflowTest = null;
  state.workflow.status = "draft";
  state.workflow.testStatus = "stale";
  updateSummaryResource("workflows", state.workflow);
  updateResourceActionButtons("workflows", state.workflow);
  const badge = $("#save-state");
  badge.className = "save-state";
  badge.innerHTML = `<i></i> ${tr("unsaved")}`;
  $("#validation-state").className = "validation-state";
  $("#validation-state").innerHTML = `${statusDot} ${tr("waitingValidation")}`;
  renderWorkflowTestPanel({ stale: true });
  scheduleAutosave("workflows");
}

function markSaved() {
  state.dirty = false;
  const badge = $("#save-state");
  badge.className = "save-state saved";
  badge.innerHTML = `<i></i> ${tr("synced")}`;
}

function selectedResource(kind) {
  return ({ agents: state.selectedAgent, actions: state.selectedAction, skills: state.selectedSkill, workflows: state.workflow })[kind] || null;
}

function updateSummaryResource(kind, resource) {
  if (!resource?.id || !Array.isArray(state[kind])) return;
  const index = state[kind].findIndex(item => item.id === resource.id);
  if (index >= 0) state[kind][index] = { ...state[kind][index], ...resource };
  else state[kind].push(resource);
}

function markEditorDraft(kind) {
  const resource = selectedResource(kind);
  if (!resource) return;
  resource.status = "draft";
  resource.resourceStatus = "draft";
  if (kind === "agents") resource.testStatus = "stale";
  if (kind === "workflows") {
    markDirty();
    return;
  }
  updateSummaryResource(kind, resource);
  updateEditorStatus(kind.slice(0, -1), resource);
  renderResources();
  renderSelectedProject();
  scheduleAutosave(kind);
}

function scheduleAutosave(kind) {
  if (!state.project) return;
  state.autosave.dirty.add(kind);
  clearTimeout(state.autosave.timers[kind]);
  state.autosave.timers[kind] = setTimeout(() => { void flushAutosaveKind(kind); }, 500);
}

async function flushAutosaveKind(kind) {
  const handlers = {
    agents: () => persistAgentDraft(false), actions: () => persistActionDraft(false),
    skills: () => persistSkillDraft(false), workflows: () => persistWorkflowDraft(false), ai: () => persistAIDraftToStudio()
  };
  while (true) {
    clearTimeout(state.autosave.timers[kind]);
    delete state.autosave.timers[kind];

    const active = state.autosave.inFlight[kind];
    if (active) {
      const succeeded = await active;
      if (!succeeded) {
        state.autosave.dirty.add(kind);
        return false;
      }
      continue;
    }
    if (!state.autosave.dirty.has(kind)) return true;

    state.autosave.dirty.delete(kind);
    const handler = handlers[kind];
    if (!handler) return true;
    const request = Promise.resolve()
      .then(handler)
      .then(result => result !== false, () => false);
    state.autosave.inFlight[kind] = request;
    const succeeded = await request;
    if (state.autosave.inFlight[kind] === request) delete state.autosave.inFlight[kind];
    if (!succeeded) {
      state.autosave.dirty.add(kind);
      return false;
    }
    // Editing can continue while a save request is in flight. Keep flushing
    // until no newer generation remains before publish, sync, test, or navigation.
  }
}

async function flushAutosaves() {
  const kinds = new Set([
    ...Object.keys(state.autosave.timers),
    ...state.autosave.dirty,
    ...Object.keys(state.autosave.inFlight)
  ]);
  if (!kinds.size) return true;
  const results = await Promise.all([...kinds].map(kind => flushAutosaveKind(kind)));
  return results.every(Boolean);
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
  })[char]);
}

function initials(name) {
  const chars = [...String(name).trim()];
  return (chars[0] || "A").toUpperCase();
}

function toast(message, isError = false) {
  const element = document.createElement("div");
  element.className = `toast${isError ? " error" : ""}`;
  element.textContent = message;
  $("#toast-region").append(element);
  setTimeout(() => element.remove(), isError ? 8000 : 3400);
}

const composerConfig = {
  guide: { input: "#guide-input", files: "#guide-file-input", attachments: "#guide-attachments", button: "#guide-send", status: "#guide-composer-status", form: "#guide-composer" },
  ai: { input: "#ai-input", files: "#ai-file-input", attachments: "#ai-attachments", button: "#ai-send", status: "#ai-composer-status", form: "#ai-composer" }
};
const textAttachmentExtensions = new Set(["txt", "md", "markdown", "json", "jsonl", "yaml", "yml", "csv", "tsv", "xml", "html", "css", "js", "mjs", "cjs", "ts", "tsx", "jsx", "py", "java", "go", "rs", "sh", "sql", "toml", "ini", "conf", "log"]);
const imageAttachmentTypes = new Set(["image/png", "image/jpeg", "image/webp", "image/gif"]);
const imageAttachmentExtensions = new Set(["png", "jpg", "jpeg", "webp", "gif"]);
const maxAttachments = 4;
const maxAttachmentBytes = 4_000_000;
const maxTextAttachmentBytes = 512_000;
const maxAttachmentTotalBytes = 8_000_000;
const composerFileQueues = { guide: Promise.resolve(), ai: Promise.resolve() };

function composerState(name) {
  return name === "guide" ? state.guide : state.ai;
}

function attachmentKind(file) {
  const extension = file.name.toLowerCase().split(".").pop();
  if (imageAttachmentTypes.has(file.type) || imageAttachmentExtensions.has(extension)) return "image";
  if (file.type === "application/pdf" || extension === "pdf") return "pdf";
  if (file.type.startsWith("text/") || textAttachmentExtensions.has(extension) || ["application/json", "application/xml", "application/x-yaml", "application/yaml", "application/toml", "application/javascript"].includes(file.type)) return "text";
  return "";
}

function formatFileSize(bytes) {
  if (bytes < 1000) return `${bytes} B`;
  if (bytes < 1_000_000) return `${Math.ceil(bytes / 1000)} KB`;
  return `${(bytes / 1_000_000).toFixed(1)} MB`;
}

function setComposerStatus(name, message = "", isError = false) {
  const element = $(composerConfig[name].status);
  element.textContent = message;
  element.classList.toggle("error", isError);
}

function resizeComposerInput(name) {
  const input = $(composerConfig[name].input);
  input.style.height = "auto";
  input.style.height = `${Math.min(154, Math.max(50, input.scrollHeight))}px`;
}

function conversationAttachments(scope) {
  return scope.messages.flatMap(message => Array.isArray(message.attachments) ? message.attachments : []);
}

function renderComposerAttachments(name) {
  const scope = composerState(name);
  $(composerConfig[name].attachments).innerHTML = scope.attachments.map((attachment, index) => {
    const preview = attachment.kind === "image"
      ? `<img src="data:${escapeHtml(attachment.type)};base64,${attachment.data}" alt="">`
      : escapeHtml(attachment.kind === "pdf" ? "PDF" : "TXT");
    return `<div class="attachment-chip"><span class="attachment-preview">${preview}</span><span class="attachment-copy"><strong title="${escapeHtml(attachment.name)}">${escapeHtml(attachment.name)}</strong><small>${formatFileSize(attachment.size)}</small></span><button class="attachment-remove" type="button" data-remove-attachment="${index}" aria-label="移除 ${escapeHtml(attachment.name)}">${icon("x")}</button></div>`;
  }).join("");
  $(composerConfig[name].attachments).querySelectorAll("[data-remove-attachment]").forEach(button => button.addEventListener("click", () => {
    scope.attachments.splice(Number(button.dataset.removeAttachment), 1);
    renderComposerAttachments(name);
    updateComposerButton(name);
  }));
}

function readAttachment(file, kind) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const extension = file.name.toLowerCase().split(".").pop();
      const fallbackImageType = extension === "jpg" || extension === "jpeg" ? "image/jpeg" : `image/${extension}`;
      const mediaType = kind === "image" ? (imageAttachmentTypes.has(file.type) ? file.type : fallbackImageType) : (kind === "pdf" ? "application/pdf" : (file.type || "text/plain"));
      resolve({ name: file.name, type: mediaType, size: file.size, kind, data: String(reader.result).split(",", 2)[1] || "", lastModified: file.lastModified });
    };
    reader.onerror = () => reject(new Error(`无法读取 ${file.name}`));
    reader.readAsDataURL(file);
  });
}

async function processComposerFiles(name, files, generation) {
  const scope = composerState(name);
  const existing = [...conversationAttachments(scope), ...scope.attachments];
  let count = scope.attachments.length;
  let totalBytes = existing.reduce((sum, attachment) => sum + Number(attachment.size || 0), 0);
  for (const file of [...files]) {
    if (scope.attachmentGeneration !== generation) return;
    const kind = attachmentKind(file);
    if (!kind) { setComposerStatus(name, `不支持附件类型：${file.name}`, true); continue; }
    if (!file.size) { setComposerStatus(name, `附件是空文件：${file.name}`, true); continue; }
    const sizeLimit = kind === "text" ? maxTextAttachmentBytes : maxAttachmentBytes;
    if (file.size > sizeLimit) { setComposerStatus(name, `${file.name} 超过 ${kind === "text" ? "500 KB" : "4 MB"} 限制`, true); continue; }
    if (count >= maxAttachments) { setComposerStatus(name, `每条消息最多 ${maxAttachments} 个附件`, true); break; }
    if (totalBytes + file.size > maxAttachmentTotalBytes) { setComposerStatus(name, "附件总大小不能超过 8 MB", true); break; }
    if (scope.attachments.some(item => item.name === file.name && item.size === file.size && item.lastModified === file.lastModified)) continue;
    try {
      const attachment = await readAttachment(file, kind);
      if (scope.attachmentGeneration !== generation) return;
      scope.attachments.push(attachment);
      count += 1;
      totalBytes += file.size;
      setComposerStatus(name, "");
    } catch (error) {
      if (scope.attachmentGeneration === generation) setComposerStatus(name, error.message, true);
    }
  }
  if (scope.attachmentGeneration !== generation) return;
  $(composerConfig[name].files).value = "";
  renderComposerAttachments(name);
  updateComposerButton(name);
}

function addComposerFiles(name, files) {
  const selectedFiles = [...files];
  if (!selectedFiles.length) return Promise.resolve();
  const scope = composerState(name);
  const generation = scope.attachmentGeneration;
  scope.pendingAttachmentReads += 1;
  setComposerStatus(name, "正在读取附件…");
  updateComposerButton(name);
  const job = composerFileQueues[name].catch(() => {}).then(() => processComposerFiles(name, selectedFiles, generation));
  composerFileQueues[name] = job.catch(() => {});
  return job.catch(error => {
    if (scope.attachmentGeneration === generation) setComposerStatus(name, error.message || "附件读取失败", true);
  }).finally(() => {
    if (scope.attachmentGeneration !== generation) return;
    scope.pendingAttachmentReads = Math.max(0, scope.pendingAttachmentReads - 1);
    if (scope.pendingAttachmentReads) setComposerStatus(name, "正在读取附件…");
    updateComposerButton(name);
  });
}

function messageAttachmentHtml(message) {
  if (!message.attachments?.length) return "";
  return `<div class="message-attachments">${message.attachments.map(attachment => `<span title="${escapeHtml(attachment.name)}">附件 · ${escapeHtml(attachment.name)}</span>`).join("")}</div>`;
}

function serializeMessages(messages) {
  return messages.filter(message => !message.loading).map(message => ({
    role: message.role,
    content: message.content,
    ...(message.attachments?.length ? { attachments: message.attachments.map(({ name, type, size, data }) => ({ name, type, size, data })) } : {})
  }));
}

function updateComposerButton(name) {
  const scope = composerState(name);
  const button = $(composerConfig[name].button);
  const hasInput = Boolean($(composerConfig[name].input).value.trim() || scope.attachments.length);
  button.disabled = scope.busy ? false : (scope.pendingAttachmentReads > 0 || !hasInput || !state.ai.configured);
}

function setComposerBusy(name, busy) {
  const scope = composerState(name);
  scope.busy = busy;
  const button = $(composerConfig[name].button);
  button.classList.toggle("stop", busy);
  button.setAttribute("aria-label", busy ? tr("stopGenerating") : tr("send"));
  button.querySelector("span").textContent = busy ? tr("stopGenerating") : tr("send");
  updateComposerButton(name);
}

function replaceLoadingMessage(scope, loadingId, content) {
  const index = scope.messages.findIndex(message => message.id === loadingId);
  if (index >= 0) scope.messages[index] = { id: loadingId, role: "assistant", content };
}

async function confirmComposerCancellation(name, request) {
  const scope = composerState(name);
  let lastError = null;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      const result = await globalApi("/api/ai/cancel", { method: "POST", body: JSON.stringify({ requestId: request.id }) });
      if (result.cancelled) {
        if (!scope.messages.some(message => message.id === request.loadingId)) return;
        replaceLoadingMessage(scope, request.loadingId, "已停止生成。");
        if (!scope.request) setComposerStatus(name, "已停止生成。");
        if (name === "guide") renderGuideMessages(); else renderAIMessages();
        return;
      }
      lastError = new Error("服务端未确认取消。");
    } catch (error) {
      lastError = error;
    }
    if (attempt < 2) await new Promise(resolve => setTimeout(resolve, 120));
  }
  if (!scope.messages.some(message => message.id === request.loadingId)) return;
  replaceLoadingMessage(scope, request.loadingId, "已停止界面等待，但未能确认后端取消。");
  if (!scope.request) setComposerStatus(name, lastError?.message || "后端取消未确认。", true);
  if (name === "guide") renderGuideMessages(); else renderAIMessages();
}

function stopComposerRequest(name, silent = false) {
  const scope = composerState(name);
  const request = scope.request;
  if (!request) return;
  scope.request = null;
  request.cancelled = true;
  request.controller.abort();
  replaceLoadingMessage(scope, request.loadingId, silent ? "正在停止上一次生成…" : "正在停止生成…");
  setComposerBusy(name, false);
  setComposerStatus(name, "正在确认后端已停止…");
  if (name === "guide") renderGuideMessages(); else renderAIMessages();
  confirmComposerCancellation(name, request);
  $(composerConfig[name].input).focus();
}

function setupComposerEvents(name) {
  const config = composerConfig[name];
  const scope = composerState(name);
  const input = $(config.input);
  const form = $(config.form);
  const fileInput = $(config.files);
  const attachButton = name === "guide" ? $("#guide-attach") : $("#ai-attach");
  let composing = false;
  let dragDepth = 0;
  input.addEventListener("compositionstart", () => { composing = true; });
  input.addEventListener("compositionend", () => { composing = false; });
  input.addEventListener("input", () => { resizeComposerInput(name); updateComposerButton(name); });
  input.addEventListener("keydown", event => {
    if (event.key !== "Enter" || event.isComposing || composing) return;
    if (event.metaKey || event.ctrlKey) {
      event.preventDefault();
      if (!scope.busy) form.requestSubmit();
    }
  });
  input.addEventListener("paste", event => {
    const files = [...(event.clipboardData?.files || [])];
    if (!files.length) return;
    event.preventDefault();
    addComposerFiles(name, files);
  });
  attachButton.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", () => addComposerFiles(name, fileInput.files));
  form.addEventListener("dragenter", event => { event.preventDefault(); dragDepth += 1; form.classList.add("dragging"); });
  form.addEventListener("dragover", event => { event.preventDefault(); event.dataTransfer.dropEffect = "copy"; });
  form.addEventListener("dragleave", () => { dragDepth = Math.max(0, dragDepth - 1); if (!dragDepth) form.classList.remove("dragging"); });
  form.addEventListener("drop", event => {
    event.preventDefault();
    dragDepth = 0;
    form.classList.remove("dragging");
    if (event.dataTransfer?.files?.length) addComposerFiles(name, event.dataTransfer.files);
  });
  $(config.button).addEventListener("click", event => {
    if (!scope.busy) return;
    event.preventDefault();
    stopComposerRequest(name);
  });
  resizeComposerInput(name);
  renderComposerAttachments(name);
  updateComposerButton(name);
}

async function loadProject() {
  try {
    const payload = await globalApi("/api/codex/projects");
    state.projects = payload.projects;
    state.selectedProjectId = state.projects.find(project => project.active)?.id || state.projects[0]?.id || null;
    renderProjectList();
    renderSelectedProject();
    setSection("projects");
    const selected = state.projects.find(project => project.id === state.selectedProjectId);
    if (selected && projectIsAuthorized(selected)) await syncProject(selected.id, { silent: true });
  } catch (error) {
    toast(`无法连接本地服务：${error.message}`, true);
  }
}

async function loadAIStatus() {
  try {
    const deviceJob = state.connections?.deviceJob || null;
    const status = await globalApi("/api/connections");
    status.deviceJob = deviceJob;
    state.connections = status;
    const wasConfigured = state.ai.configured;
    state.ai.configured = status.configured;
    state.ai.provider = status.provider;
    state.ai.model = status.model;
    const badge = $("#ai-provider");
    badge.className = `ai-provider ${status.connected ? "ready" : (status.activeProvider ? "missing" : "warning")}`;
    $("#ai-provider-status").textContent = status.connected ? tr("connected") : (status.activeProvider ? tr("disconnected") : (state.language === "zh" ? "待选择" : "Choose provider"));
    $("#ai-provider-detail").textContent = status.connected ? `${status.activeProvider === "codex" ? "Codex" : "API"} · ${modelLabel(status.model)}` : tr("clickToConfigure");
    badge.title = status.checkedAt ? `${tr("lastChecked")}：${status.checkedAt}` : tr("waitingDetection");
    $("#ai-compose-hint").textContent = state.language === "zh" ? "Enter 换行 · ⌘/Ctrl+Enter 发送" : "Enter for a new line · ⌘/Ctrl+Enter to send";
    if (!status.configured) setComposerStatus("ai", localizeConnectionMessage(status.error) || (state.language === "zh" ? "请先连接 AI Assistant" : "Connect AI Assistant first."), true);
    else if (!state.ai.busy) setComposerStatus("ai", `${status.provider} · ${modelLabel(status.model)}`);
    updateComposerButton("ai");
    updateComposerButton("guide");
    if (!wasConfigured && status.configured && state.ai.messages.length === 1 && state.ai.messages[0].role === "assistant") {
      state.ai.messages[0].content = aiWelcome(state.ai.kind, Boolean(state.ai.draft));
      renderAIMessages();
    }
    renderConnectionCenter(status);
  } catch (error) {
    state.ai.configured = false;
    $("#ai-provider").className = "ai-provider missing";
    $("#ai-provider-status").textContent = tr("disconnected");
    $("#ai-provider-detail").textContent = tr("clickToConfigure");
    updateComposerButton("ai");
    updateComposerButton("guide");
  }
}

function localizeConnectionMessage(message) {
  const value = String(message || "");
  if (state.language === "zh" || !value) return value;
  const known = {
    "请填写 API Key。": "Enter an API key.",
    "Codex 尚未登录。": "Codex is not signed in.",
    "Codex CLI 未安装。": "Codex CLI is not installed.",
    "请先连接 Codex 或自定义 API。": "Connect Codex or a custom API first.",
    "Codex 与 API 同时可用，请明确选择活动提供商。": "Codex and API are both available. Choose the active provider.",
    "正在启动 OpenAI 官方设备码登录…": "Starting official OpenAI device authorization…",
    "请在 OpenAI 官方页面输入一次性设备码。": "Enter the one-time device code on the official OpenAI page.",
    "Codex 官方登录已完成。": "Codex sign-in is complete.",
    "Codex 登录未完成。": "Codex sign-in did not complete.",
    "OpenAI 官方设备码登录失败或已过期。": "Official OpenAI device authorization failed or expired.",
    "设备码登录已超时。": "Device authorization timed out.",
    "请重新启动登录并使用新的设备码。": "Start sign-in again and use the new device code.",
    "设备码登录已取消。": "Device authorization was cancelled."
  };
  return known[value] || value;
}

function renderConnectionCenter(status = state.connections) {
  if (!status?.providers) return;
  const codex = status.providers.codex || {};
  const api = status.providers.api || {};
  $("#codex-connection-card").classList.toggle("active", status.activeProvider === "codex");
  $("#ai-config-form").classList.toggle("active", status.activeProvider === "api");
  $("#codex-connection-state").className = `provider-state${codex.connected ? " ready" : ""}`;
  $("#codex-connection-state").textContent = codex.connected ? (state.language === "zh" ? "已登录" : "Signed in") : (codex.installed ? (state.language === "zh" ? "未登录" : "Not signed in") : (state.language === "zh" ? "未安装" : "Not installed"));
  $("#api-connection-state").className = `provider-state${api.connected ? " ready" : ""}`;
  $("#api-connection-state").textContent = api.connected ? (state.language === "zh" ? "可用" : "Available") : (api.hasApiKey ? (state.language === "zh" ? "连接失败" : "Connection failed") : (state.language === "zh" ? "未配置" : "Not configured"));
  if (document.activeElement !== $("#codex-model-id")) $("#codex-model-id").value = codex.modelInherited ? "" : (codex.model || "");
  if (document.activeElement !== $("#ai-config-url")) $("#ai-config-url").value = api.baseUrl || "https://api.openai.com/v1";
  const selectedModel = api.model || "";
  const models = Array.isArray(api.availableModels) ? api.availableModels : [];
  if (models.length && document.activeElement !== $("#ai-config-model")) {
    $("#ai-config-model").innerHTML = models.map(model => `<option value="${escapeHtml(model)}">${escapeHtml(model)}</option>`).join("");
    if (models.includes(selectedModel)) $("#ai-config-model").value = selectedModel;
  } else if (selectedModel && ![...$("#ai-config-model").options].some(option => option.value === selectedModel)) {
    $("#ai-config-model").insertAdjacentHTML("afterbegin", `<option value="${escapeHtml(selectedModel)}">${escapeHtml(selectedModel)}</option>`);
    $("#ai-config-model").value = selectedModel;
  }
  $("#save-api-key").checked = Boolean(api.savedLocally);
  $("#forget-api-key").classList.toggle("hidden", !api.savedLocally);
  const feedback = $("#ai-config-feedback");
  if (!feedback.classList.contains("error")) {
    feedback.className = `config-feedback${api.connected ? " success" : ""}`;
    feedback.textContent = api.connected
      ? `${api.model} · ${api.billingLabel}`
      : (localizeConnectionMessage(api.error) || (state.language === "zh" ? "填写 Key 后获取 /models 列表。" : "Enter a key, then fetch the /models list."));
  }
  renderDeviceAuth(status.deviceJob);
}

async function openAIConfig() {
  const dialog = $("#ai-config-dialog");
  try {
    await loadAIStatus();
    const config = state.connections?.providers?.api || {};
    state.ai.config = config;
    $("#ai-config-key").value = "";
    const model = config.model || "";
    $("#ai-config-model").innerHTML = model ? `<option value="${escapeHtml(model)}">${escapeHtml(model)}</option>` : `<option value="">${escapeHtml(tr("fetchModelsFirst"))}</option>`;
    renderConnectionCenter();
    dialog.showModal();
  } catch (error) {
    toast(error.message, true);
  }
}

async function fetchAIModels() {
  const button = $("#fetch-ai-models");
  const feedback = $("#ai-config-feedback");
  button.disabled = true;
  feedback.className = "config-feedback";
  const modelsUrl = `${$("#ai-config-url").value.trim().replace(/\/+$/, "") || "API"}/models`;
  feedback.textContent = state.language === "zh" ? `正在从 ${modelsUrl} 获取模型 ID…` : `Fetching model IDs from ${modelsUrl}…`;
  try {
    const result = await globalApi("/api/connections/api/models", {
      method: "POST",
      body: JSON.stringify({ apiKey: $("#ai-config-key").value, baseUrl: $("#ai-config-url").value })
    });
    const current = state.ai.config?.model || "";
    $("#ai-config-model").innerHTML = result.models.map(model => `<option value="${escapeHtml(model)}">${escapeHtml(model)}</option>`).join("");
    if (result.models.includes(current)) $("#ai-config-model").value = current;
    feedback.className = "config-feedback success";
    feedback.textContent = state.language === "zh" ? `已获取 ${result.count} 个模型，请选择后保存。` : `Fetched ${result.count} model${result.count === 1 ? "" : "s"}. Choose one, then save.`;
  } catch (error) {
    feedback.className = "config-feedback error";
    feedback.textContent = localizeConnectionMessage(error.message);
  } finally {
    button.disabled = false;
  }
}

async function saveAIConfig(event) {
  event.preventDefault();
  const feedback = $("#ai-config-feedback");
  const button = $("#save-ai-config");
  button.disabled = true;
  try {
    const result = await globalApi("/api/connections/api", {
      method: "POST",
      body: JSON.stringify({
        apiKey: $("#ai-config-key").value,
        baseUrl: $("#ai-config-url").value,
        model: $("#ai-config-model").value,
        saveLocally: $("#save-api-key").checked,
        activate: true
      })
    });
    state.ai.config = result.config;
    feedback.className = `config-feedback ${result.status.configured ? "success" : "error"}`;
    feedback.textContent = result.status.configured
      ? (state.language === "zh" ? `已连接 ${modelLabel(result.status.model)}` : `Connected to ${modelLabel(result.status.model)}`)
      : (localizeConnectionMessage(result.status.error) || (state.language === "zh" ? "配置已保存，但连接检查未通过。" : "Settings saved, but the connection check did not pass."));
    await loadAIStatus();
  } catch (error) {
    feedback.className = "config-feedback error";
    feedback.textContent = localizeConnectionMessage(error.message);
  } finally {
    button.disabled = false;
  }
}

async function useCodexProvider() {
  const button = $("#use-codex-provider");
  button.disabled = true;
  try {
    await globalApi("/api/connections/codex", {
      method: "POST",
      body: JSON.stringify({ modelId: $("#codex-model-id").value.trim(), activate: true })
    });
    await loadAIStatus();
    if (!state.ai.configured) throw new Error(state.connections?.providers?.codex?.error || "Codex is unavailable.");
    toast(state.language === "zh" ? "已选择 Codex 为活动提供商" : "Codex is now the active provider");
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

function renderDeviceAuth(job) {
  const box = $("#device-auth-box");
  if (!job) { box.classList.add("hidden"); return; }
  box.classList.remove("hidden");
  $("#device-auth-link").href = job.verificationUrl || "https://auth.openai.com/";
  $("#device-auth-link").classList.toggle("hidden", !job.verificationUrl);
  $("#device-auth-code").textContent = job.userCode || "…";
  $("#device-auth-message").textContent = localizeConnectionMessage(job.error || job.message || job.status);
  const pending = ["starting", "pending"].includes(job.status);
  $("#cancel-device-auth").classList.toggle("hidden", !pending);
  $("#start-device-auth").disabled = pending;
}

async function pollDeviceAuth() {
  const job = state.connections?.deviceJob;
  if (!job?.jobId || !["starting", "pending"].includes(job.status)) return;
  try {
    const updated = await globalApi(`/api/connections/codex/device-auth/${encodeURIComponent(job.jobId)}`);
    state.connections.deviceJob = updated;
    renderDeviceAuth(updated);
    if (["starting", "pending"].includes(updated.status)) setTimeout(pollDeviceAuth, 1000);
    else await loadAIStatus();
  } catch (error) {
    $("#device-auth-message").textContent = error.message;
  }
}

async function startDeviceAuth() {
  try {
    const job = await globalApi("/api/connections/codex/device-auth", { method: "POST", body: "{}" });
    if (!state.connections) state.connections = {};
    state.connections.deviceJob = job;
    renderDeviceAuth(job);
    setTimeout(pollDeviceAuth, 350);
  } catch (error) {
    toast(error.message, true);
  }
}

async function cancelDeviceAuth() {
  const job = state.connections?.deviceJob;
  if (!job?.jobId) return;
  try {
    state.connections.deviceJob = await globalApi(`/api/connections/codex/device-auth/${encodeURIComponent(job.jobId)}`, { method: "DELETE" });
    renderDeviceAuth(state.connections.deviceJob);
  } catch (error) { toast(error.message, true); }
}

async function forgetAPIKey() {
  try {
    await globalApi("/api/connections/api/key", { method: "DELETE" });
    $("#ai-config-key").value = "";
    await loadAIStatus();
    toast(state.language === "zh" ? "已删除本机保存的 API Key" : "Saved API key deleted");
  } catch (error) { toast(error.message, true); }
}

function renderGuideMessages() {
  $("#guide-messages").innerHTML = state.guide.messages.map(message => `
    <article class="guide-message ${message.role}${message.loading ? " loading" : ""}"><small>${message.role === "user" ? "You" : "AI Assistant"}</small><p>${escapeHtml(message.content || "已添加附件")}</p>${messageAttachmentHtml(message)}</article>
  `).join("");
  $("#guide-messages").scrollTop = $("#guide-messages").scrollHeight;
}

function openAppAssistant() {
  if (!state.guide.messages.length) {
    const scopeHint = state.project
      ? "我也可以结合当前项目的资源状态回答。"
      : "即使还没有选择或授权项目，也可以先问我通用用法。";
    state.guide.messages = [{ role: "assistant", content: `你好，我是 Workflow Studio 使用助手。你可以问我如何创建 Agent、Action、Skill，怎样授权 Action，或者如何在 Workflow 画布中连线。${scopeHint}` }];
  }
  renderGuideMessages();
  $("#app-assistant-dialog").showModal();
  $("#guide-input").focus();
}

async function sendGuideMessage(event) {
  event.preventDefault();
  const input = $("#guide-input");
  const content = input.value.trim();
  if (state.guide.pendingAttachmentReads) {
    setComposerStatus("guide", "附件仍在读取，请稍候。");
    return;
  }
  if ((!content && !state.guide.attachments.length) || state.guide.busy) return;
  const context = captureProjectContext();
  const attachments = state.guide.attachments.splice(0);
  state.guide.messages.push({ role: "user", content, attachments });
  input.value = "";
  resizeComposerInput("guide");
  renderComposerAttachments("guide");
  const loadingId = uid("guide-loading");
  const requestId = uid("guide-request");
  const request = { id: requestId, loadingId, controller: new AbortController(), cancelled: false };
  state.guide.request = request;
  state.guide.messages.push({ id: loadingId, role: "assistant", content: "正在回答…", loading: true });
  setComposerBusy("guide", true);
  setComposerStatus("guide", "正在生成，可随时停止。");
  renderGuideMessages();
  try {
    const options = { method: "POST", signal: request.controller.signal, body: JSON.stringify({ requestId, messages: serializeMessages(state.guide.messages) }) };
    const result = context
      ? await projectApi(context.projectId, "/ai/help", options)
      : await globalApi("/api/ai/help", options);
    if (state.guide.request !== request || (context && !isCurrentProjectContext(context))) return;
    replaceLoadingMessage(state.guide, loadingId, result.message);
    setComposerStatus("guide", "");
  } catch (error) {
    if (state.guide.request !== request || (context && !isCurrentProjectContext(context))) return;
    replaceLoadingMessage(state.guide, loadingId, error.name === "AbortError" || request.cancelled ? "已停止生成。" : `暂时无法回答：${error.message}`);
    if (error.name !== "AbortError" && !request.cancelled) setComposerStatus("guide", error.message, true);
  } finally {
    if (state.guide.request === request) {
      state.guide.request = null;
      setComposerBusy("guide", false);
      renderGuideMessages();
    }
  }
}

async function syncProject(projectId, { silent = false } = {}) {
  const importToken = ++state.projectImportToken;
  const isLatestImport = () => state.projectImportToken === importToken
    && state.selectedProjectId === projectId;
  const switchingProject = Boolean(state.project && state.project.id !== projectId);
  const needsAISessionRestore = !state.project || switchingProject;
  state.syncingProject = true;
  const button = $("#sync-project-details");
  if (button) { button.disabled = true; button.textContent = "导入中…"; }
  $("#project-view-status").textContent = "正在只读导入项目资源…";
  let syncEpoch = null;
  try {
    if (silent && (state.ai.request || state.guide.request)) return false;
    if (!await flushAutosaves()) {
      if (!silent && isLatestImport()) toast("当前 Studio 草稿尚未保存，已取消导入。", true);
      return false;
    }
    if (!isLatestImport()) return false;

    syncEpoch = state.projectEpoch + 1;
    state.projectEpoch = syncEpoch;
    if (silent) {
      try {
        await projectApi(projectId, "/agents");
        if (!isLatestImport() || state.projectEpoch !== syncEpoch) return false;
      } catch (error) {
        if (!isLatestImport() || state.projectEpoch !== syncEpoch) return false;
        if (error.payload?.authorizationRequired) {
          state.authorizedProjectIds.delete(projectId);
          persistStoredSet("workflow-studio-authorized-projects", state.authorizedProjectIds);
          const listed = state.projects.find(item => item.id === projectId);
          if (listed) listed.authorized = false;
          if (state.project?.id === projectId) {
            state.project = null;
            state.agents = [];
            state.actions = [];
            state.skills = [];
            state.workflows = [];
          }
          renderProjectList();
          renderSelectedProject();
        }
        return false;
      }
    }
    if (!isLatestImport() || state.projectEpoch !== syncEpoch) return false;
    if (switchingProject || !silent) {
      if (switchingProject) {
        cacheAICreationSession(state.project.id);
        if (state.ai.request) stopComposerRequest("ai", true);
        resetAICreationClientState();
      }
      if (state.guide.request) stopComposerRequest("guide", true);
      resetActionConnectionStatus();
    }
    const payload = await globalApi(`/api/codex/projects/${encodeURIComponent(projectId)}/import`, {
      method: "POST",
      headers: { "X-Workflow-Studio-Project-Id": projectId }
    });
    if (!isLatestImport() || state.projectEpoch !== syncEpoch) return false;
    if (!payload.project || payload.project.id !== projectId) throw new Error("项目导入响应与所选项目不一致。");

    const nextWorkflows = payload.workflows || [];
    let nextWorkflow;
    let nextWorkflowRevision = null;
    if (nextWorkflows.length) {
      const latest = nextWorkflows.find(item => item.id === state.workflow?.id) || nextWorkflows[nextWorkflows.length - 1];
      const detail = await projectApi(projectId, `/workflows/${encodeURIComponent(latest.id)}`);
      if (!isLatestImport() || state.projectEpoch !== syncEpoch) return false;
      nextWorkflow = resourceFrom(detail, "workflow");
      nextWorkflowRevision = detail.revision ?? null;
      if (!nextWorkflow) throw new Error("无法读取当前项目的 Workflow 详情。");
    } else {
      nextWorkflow = { id: "delivery-flow", name: "多 Agent 交付流", description: "", nodes: [], edges: [], updatedAt: "" };
    }

    const nextRevisions = emptyResourceRevisions();
    if (nextWorkflowRevision !== null) nextRevisions.workflows[nextWorkflow.id] = nextWorkflowRevision;
    state.project = payload.project;
    state.agents = payload.agents || [];
    state.actions = payload.actions || [];
    state.skills = payload.skills || [];
    state.workflows = nextWorkflows;
    state.workflow = nextWorkflow;
    prepareViewForWorkflow();
    state.resourceRevisions = nextRevisions;
    state.selectedAgent = switchingProject ? null : mergeSummaryStatus(state.selectedAgent, state.agents);
    state.selectedAction = switchingProject ? null : mergeSummaryStatus(state.selectedAction, state.actions);
    state.selectedSkill = switchingProject ? null : mergeSummaryStatus(state.selectedSkill, state.skills);
    state.selectedNodeId = null;
    state.selectedEdgeId = null;
    state.selectedProjectId = projectId;
    state.authorizedProjectIds.add(projectId);
    persistStoredSet("workflow-studio-authorized-projects", state.authorizedProjectIds);
    state.projects.forEach(project => {
      project.active = project.id === projectId;
      if (project.id === projectId) project.authorized = true;
    });
    if (switchingProject) {
      state.guide.attachmentGeneration += 1;
      state.guide.pendingAttachmentReads = 0;
      composerFileQueues.guide = Promise.resolve();
      state.guide.messages = [];
      state.guide.attachments = [];
      $("#guide-file-input").value = "";
      setComposerStatus("guide", "");
      renderComposerAttachments("guide");
      renderGuideMessages();
      updateComposerButton("guide");
    }
    const restoredAICreationSession = needsAISessionRestore && restoreAICreationSession(projectId);
    if (!restoredAICreationSession) {
      await restoreLatestAIDraft(state.ai.kind, {
        silent: true,
        preserveOnEmpty: !needsAISessionRestore && state.ai.projectId === projectId
      });
    }
    if (!isLatestImport() || state.projectEpoch !== syncEpoch) return false;
    $("#workflow-name").value = state.workflow.name;
    if (state.workflows.length) markSaved();
    else { markDirty(); seedExampleWorkflow(); }
    renderResources();
    if (state.selectedAgent) updateEditorStatus("agent", state.selectedAgent);
    if (state.selectedAction) updateEditorStatus("action", state.selectedAction);
    if (state.selectedSkill) updateEditorStatus("skill", state.selectedSkill);
    render();
    void validateWorkflow(false);
    void pollAgentTests(true);
    renderProjectList();
    renderSelectedProject();
    if (!silent) toast(`已只读导入「${payload.project.name}」：${state.agents.length} Agents / ${state.actions.length} Actions / ${handwrittenSkillCount()} Skills / ${state.workflows.length} Workflows`);
    return true;
  } catch (error) {
    if (isLatestImport() && error.payload?.authorizationRequired) {
      state.authorizedProjectIds.delete(projectId);
      persistStoredSet("workflow-studio-authorized-projects", state.authorizedProjectIds);
      const listed = state.projects.find(item => item.id === projectId);
      if (listed) listed.authorized = false;
    }
    if (!silent && isLatestImport() && state.projectEpoch === syncEpoch) toast(error.message, true);
    return false;
  } finally {
    if (state.projectImportToken === importToken) {
      state.syncingProject = false;
      renderSelectedProject();
    }
  }
}

function mergeSummaryStatus(resource, summaries) {
  if (!resource) return null;
  const summary = summaries.find(item => item.id === resource.id);
  return summary ? { ...resource, ...summary } : resource;
}

function renderProjectList() {
  $("#project-sidebar-list").innerHTML = state.projects.map(project => {
    const selected = state.selectedProjectId === project.id;
    const unavailable = !project.available;
    const statusLine = unavailable
      ? tr("projectUnavailable")
      : (project.tutorial ? (state.language === "zh" ? "Studio 管理的隔离教程项目" : "Studio-managed isolated tutorial") : (projectIsAuthorized(project) ? tr("projectDetailsSynced") : tr("projectNameSynced")));
    return `
    <button class="resource-card project-resource-card${selected ? " selected" : ""}${unavailable ? " unavailable" : ""}" type="button" data-project-id="${escapeHtml(project.id)}"${unavailable ? ` title="${escapeHtml(tr("projectUnavailable"))}" disabled` : ""}>
      <span class="resource-icon" data-kind="project">${project.tutorial ? icon("project") : escapeHtml(initials(project.title))}</span><span class="resource-copy"><strong>${escapeHtml(project.title)}</strong><small>${escapeHtml(statusLine)}</small></span><span class="resource-count">${selected ? statusDot : (unavailable ? icon("alert") : icon("chevron"))}</span>
    </button>`;
  }).join("");
  document.querySelectorAll("[data-project-id]").forEach(button => button.addEventListener("click", () => selectProject(button.dataset.projectId)));
}

async function selectProject(projectId) {
  const selectionToken = ++state.projectSelectionToken;
  if (!await flushAutosaves()) {
    if (state.projectSelectionToken === selectionToken) toast("当前 Studio 草稿尚未保存，已取消切换项目。", true);
    return;
  }
  if (state.projectSelectionToken !== selectionToken) return;
  state.selectedProjectId = projectId;
  const selected = state.projects.find(project => project.id === projectId);
  if (!selected || !projectIsAuthorized(selected)) clearProjectClientContext();
  renderProjectList();
  renderSelectedProject();
  if (selected && projectIsAuthorized(selected)) await syncProject(projectId, { silent: true });
}

function clearProjectClientContext() {
  const previousProjectId = state.project?.id || state.ai.projectId;
  cacheAICreationSession(previousProjectId);
  if (state.ai.request) stopComposerRequest("ai", true);
  if (state.guide.request) stopComposerRequest("guide", true);
  state.project = null;
  state.projectEpoch += 1;
  state.agents = [];
  state.actions = [];
  state.skills = [];
  state.workflows = [];
  state.selectedAgent = null;
  state.selectedAction = null;
  state.selectedSkill = null;
  state.workflow = { id: "delivery-flow", name: "多 Agent 交付流", description: "研究、实现与审查的协作流程", nodes: [], edges: [], updatedAt: "" };
  prepareViewForWorkflow();
  state.selectedNodeId = null;
  state.selectedEdgeId = null;
  state.workflowTest = null;
  state.syncPreview = null;
  state.resourceRevisions = emptyResourceRevisions();
  resetAICreationClientState();
  state.guide.attachmentGeneration += 1;
  state.guide.pendingAttachmentReads = 0;
  composerFileQueues.guide = Promise.resolve();
  state.guide.messages = [];
  state.guide.attachments = [];
  if (document.querySelector(composerConfig.ai.files)) $(composerConfig.ai.files).value = "";
  if (document.querySelector(composerConfig.guide.files)) $(composerConfig.guide.files).value = "";
  renderComposerAttachments("ai");
  renderComposerAttachments("guide");
  setComposerStatus("ai", "");
  setComposerStatus("guide", "");
  renderAIMessages();
  renderGuideMessages();
  setSection("projects");
}

function projectIsAuthorized(project) {
  return Boolean(project?.authorized === true || project?.imported === true || project?.detailsAuthorized === true);
}

function renderSelectedProject() {
  const project = state.projects.find(item => item.id === state.selectedProjectId);
  if (!project) return;
  const synced = state.project?.id === project.id;
  const authorized = projectIsAuthorized(project);
  $("#project-view-title").textContent = project.title;
  $("#project-view-status").textContent = state.syncingProject ? tr("syncingResources") : (synced ? tr("detailsSynced") : tr("confirmManualSync"));
  $("#project-view-path").textContent = synced ? state.project.root : tr("pathAfterSync");
  $("#sync-project-details").disabled = !project.available || state.syncingProject;
  $("#sync-project-details").textContent = state.syncingProject ? tr("syncing") : (authorized ? tr("resyncDetails") : tr("syncProjectDetails"));
  $(".project-sync-card h2").textContent = authorized ? tr("refreshProjectDetails") : tr("syncProjectDetails");
  $("#project-resource-entry").classList.toggle("hidden", !synced);
  $("#project-sync-center").classList.toggle("hidden", !synced);
  $("#project-targets")?.classList.toggle("hidden", !synced);
  $("#remove-folder-project")?.classList.toggle("hidden", project.source !== "folder");
  if (synced && state.targets?.projectId !== project.id) void loadProjectTargets(project.id);
  if (synced) {
    $("#project-agent-count").textContent = state.agents.length;
    $("#project-action-count").textContent = state.actions.length;
    $("#project-workflow-count").textContent = state.workflows.length;
    $("#project-skill-count").textContent = handwrittenSkillCount();
  }
  renderProjectPendingList();
  renderScanSummary();
}

function studioResources() {
  return [
    ...state.skills.map(resource => ({ kind: "skills", label: "Skill", resource })),
    ...state.actions.map(resource => ({ kind: "actions", label: "Action", resource })),
    ...state.agents.map(resource => ({ kind: "agents", label: "Agent", resource })),
    ...state.workflows.map(resource => ({ kind: "workflows", label: "Workflow", resource }))
  ];
}

function renderProjectPendingList() {
  const container = $("#project-pending-list");
  if (!container) return;
  const pending = studioResources().filter(item => resourceStatus(item.resource) !== "synced");
  container.innerHTML = pending.length ? pending.map(item => `
    <div class="pending-sync-row"><span class="pending-sync-icon" data-kind="${item.kind.slice(0, -1)}">${icon(item.kind.slice(0, -1))}</span><span><strong>${escapeHtml(item.resource.name || item.resource.id)}</strong><small>${escapeHtml(item.label)} · ${tr(resourceStatus(item.resource) === "draft" ? "publishBeforeSync" : "awaitingSyncConfirm")}</small></span>${statusBadge(item.resource)}</div>
  `).join("") : `<div class="pending-sync-empty">${tr("noPendingSync")}</div>`;
  $("#preview-project-sync").disabled = !pending.some(item => ["ready", "pending_delete", "sync_failed"].includes(resourceStatus(item.resource)));
}

function normalizePreviewItems(payload) {
  const items = Array.isArray(payload?.items) ? payload.items : (Array.isArray(payload?.order) ? payload.order : []);
  return items.map((item, index) => typeof item === "string" ? { id: item, name: item, operation: "update", order: index + 1 } : item);
}

function renderSyncPreview(payload) {
  const items = normalizePreviewItems(payload);
  const blockedIds = new Set((payload?.blocked || []).map(item => typeof item === "string" ? item : item.id || item.resourceId));
  $("#sync-preview-list").innerHTML = items.length ? items.map((item, index) => {
    const id = item.id || item.resourceId || `${index + 1}`;
    const kind = item.kind || item.type || item.resourceType || "resource";
    const operation = item.operation || item.action || "update";
    const fileValue = item.targetFiles || item.files || item.paths || [];
    const dependencyValue = item.dependencies || item.dependsOn || [];
    const files = Array.isArray(fileValue) ? fileValue : (fileValue ? [fileValue] : []);
    const dependencies = (Array.isArray(dependencyValue) ? dependencyValue : (dependencyValue ? [dependencyValue] : [])).map(value => typeof value === "string" ? value : `${value.kind || "resource"}:${value.id || value.resourceId || "?"}`);
    const blocked = Boolean(item.blocked || blockedIds.has(id));
    const reasons = (item.blockedReasons || []).map(reason => reason.message || reason.code).filter(Boolean);
    return `<div class="sync-preview-item${blocked ? " blocked" : ""}"><span><strong>${index + 1}. ${escapeHtml(item.name || id)} · ${escapeHtml(kind)}</strong><small>${escapeHtml(operation)}${files.length ? ` · ${escapeHtml(files.join(", "))}` : ""}${dependencies.length ? ` · 依赖 ${escapeHtml(dependencies.join(", "))}` : ""}${reasons.length ? ` · ${escapeHtml(reasons.join("；"))}` : ""}</small></span><span class="resource-status-badge ${blocked ? "conflict" : "ready"}">${blocked ? "已阻止" : "可同步"}</span></div>`;
  }).join("") : `<div class="pending-sync-empty">没有可同步的已发布资源。</div>`;
  const canSync = items.length > 0 && !items.every(item => item.blocked || blockedIds.has(item.id || item.resourceId));
  const hasDelete = items.some(item => (item.operation || item.action) === "delete" && !item.blocked);
  state.syncPreviewHasDelete = hasDelete;
  $("#delete-confirmation").classList.toggle("hidden", !hasDelete);
  $("#confirm-sync-deletes").checked = false;
  $("#run-project-sync").dataset.canSync = canSync ? "true" : "false";
  $("#run-project-sync").disabled = !canSync || hasDelete;
}

async function openProjectSyncPreview(selected = null) {
  let context;
  try {
    context = requireProjectContext();
    if (!await flushAutosaves()) throw new Error("当前 Studio 草稿尚未保存，无法生成同步预览。");
    const body = Array.isArray(selected) && selected.length ? JSON.stringify({ resources: selected }) : "{}";
    const preview = await projectApi(context.projectId, "/sync/preview", { method: "POST", body });
    if (!isCurrentProjectContext(context)) return;
    state.syncPreview = preview;
    renderSyncPreview(preview);
    $("#sync-result-summary").classList.add("hidden");
    $("#sync-preview-dialog").showModal();
  } catch (error) {
    if (!context || isCurrentProjectContext(context)) toast(error.message, true);
  }
}

async function runProjectSync() {
  const context = captureProjectContext();
  if (!context) return;
  const button = $("#run-project-sync");
  button.disabled = true;
  button.textContent = "正在同步…";
  try {
    const confirmDelete = Boolean(state.syncPreviewHasDelete && $("#confirm-sync-deletes").checked);
    const result = await projectApi(context.projectId, "/sync", { method: "POST", body: JSON.stringify({ preview: state.syncPreview, confirmDelete }) });
    if (!isCurrentProjectContext(context)) return;
    const succeeded = Array.isArray(result.succeeded) ? result.succeeded : [];
    const failed = Array.isArray(result.failed) ? result.failed : [];
    const blocked = Array.isArray(result.blocked) ? result.blocked : [];
    const summary = [`成功 ${succeeded.length} 项`, `失败 ${failed.length} 项`, `阻止 ${blocked.length} 项`].join(" · ");
    const detail = [...failed, ...blocked].map(item => typeof item === "string" ? item : `${item.name || item.id || item.resourceId}: ${item.error || item.reason || "未完成"}`);
    $("#sync-result-summary").classList.remove("hidden");
    $("#sync-result-summary").textContent = [summary, ...detail].join("\n");
    markSyncPreviewOutcome(succeeded, failed, blocked);
    toast(failed.length || blocked.length ? `批量同步部分完成：${summary}` : `批量同步完成：${summary}`, Boolean(failed.length));
    // This preview has been used; a retry needs a fresh preview of what is still pending.
    button.dataset.canSync = "false";
    await syncProject(context.projectId, { silent: true });
  } catch (error) {
    if (isCurrentProjectContext(context)) toast(error.message, true);
  } finally {
    button.disabled = button.dataset.canSync !== "true";
    button.textContent = "确认同步到 Codex";
  }
}

function markSyncPreviewOutcome(succeeded, failed, blocked) {
  // Ids are only unique per kind (an Agent and a Workflow may share one).
  const outcomeKey = item => typeof item === "string" ? item : `${item.kind || ""}:${item.id || item.resourceId}`;
  const outcomes = new Map();
  succeeded.forEach(item => outcomes.set(outcomeKey(item), ["synced", "已同步"]));
  failed.forEach(item => outcomes.set(outcomeKey(item), ["conflict", "失败"]));
  blocked.forEach(item => outcomes.set(outcomeKey(item), ["conflict", "已阻止"]));
  const items = normalizePreviewItems(state.syncPreview);
  document.querySelectorAll("#sync-preview-list .sync-preview-item").forEach((row, index) => {
    const item = items[index];
    const outcome = item && outcomes.get(outcomeKey(item));
    const badge = row.querySelector(".resource-status-badge");
    if (!outcome || !badge) return;
    badge.className = `resource-status-badge ${outcome[0]}`;
    badge.textContent = outcome[1];
  });
}

function seedExampleWorkflow() {
  if (state.agents.length < 2) return;
  const preferredOrder = ["researcher", "builder", "reviewer"];
  const exampleAgents = [...state.agents].sort((left, right) => {
    const leftIndex = preferredOrder.findIndex(name => left.name.toLowerCase().includes(name));
    const rightIndex = preferredOrder.findIndex(name => right.name.toLowerCase().includes(name));
    return (leftIndex < 0 ? 99 : leftIndex) - (rightIndex < 0 ? 99 : rightIndex);
  });
  // Seed inside the region the current view shows (graph space).
  const region = visibleGraphRegion();
  const canvasWidth = Math.max(600, region.width);
  const y = region.top + Math.max(130, region.height * .32);
  state.workflow.nodes = exampleAgents.slice(0, 3).map((agent, index) => ({
    id: uid("node"),
    agentId: agent.id,
    label: agent.name,
    role: agent.description,
    entrypoint: agent.entrypoint,
    model: agent.model || "inherit",
    parallel: true,
    position: { x: Math.round(region.left + Math.max(35, (canvasWidth - 190) * (index + 1) / 4)), y: Math.round(y + (index % 2) * 125) }
  }));
  state.workflow.edges = state.workflow.nodes.slice(1).map((node, index) => ({
    id: uid("edge"), source: state.workflow.nodes[index].id, target: node.id, condition: "上游任务完成后交接"
  }));
  markDirty();
}

const aiKindSections = { agent: "agents", skill: "skills", action: "actions" };

// In the AI workbench the library and rail follow the active AI kind tab.
function aiLibrarySection() {
  return aiKindSections[state.ai.kind] || "agents";
}

// The sidebar footer is shared by every library, so it always describes the visible one.
function renderScanSummary() {
  const section = activeResourceSection();
  const summary = section === "projects" ? tr("projectsInLibrary", state.projects.length)
    : section === "actions" ? tr("projectActionsCount", state.actions.length)
    : section === "skills" ? tr("projectSkillsCount", handwrittenSkillCount(), state.skills.length - handwrittenSkillCount())
    : tr("projectAgentsCount", state.agents.length);
  $("#scan-summary").textContent = summary;
}

function activeResourceSection() {
  return state.section === "ai" ? aiLibrarySection() : state.section;
}

async function flushAIDraftBeforeLeaving() {
  if (state.section !== "ai") return true;
  if (await flushAutosaveKind("ai")) return true;
  toast("AI 草稿尚未保存，已取消切换。", true);
  return false;
}

function renderAgentLibrary() {
  const resourceSection = activeResourceSection();
  const query = $("#resource-search").value.trim().toLowerCase();
  const visible = state.agents.filter(agent =>
    `${agent.name} ${agent.path} ${agent.description}`.toLowerCase().includes(query)
  );
  renderScanSummary();
  if (!visible.length && resourceSection !== "workflow") {
    $("#agent-list").innerHTML = `<div class="empty-list">${escapeHtml(tr("noMatchingAgent")).replace("\n", "<br>")}</div>`;
    return;
  }
  const workflowCards = resourceSection === "workflow" ? `
    <div class="list-section-label">${escapeHtml(tr("savedWorkflowsLabel"))}</div>
    ${state.workflows.map(workflow => `<button class="resource-card compact" type="button" data-workflow-id="${escapeHtml(workflow.id)}"><span class="resource-icon" data-kind="workflow">${icon("workflow")}</span><span class="resource-copy"><strong>${escapeHtml(workflow.name)}</strong><small>${workflowCountsLabel(workflow)}</small></span>${statusBadge(workflow)}</button>`).join("") || `<div class="empty-list compact-empty">${tr("noSavedWorkflow")}</div>`}
    <div class="list-section-label">${escapeHtml(tr("agentsLabel"))}</div>` : "";
  const actionCards = resourceSection === "workflow" ? `
    <div class="list-section-label">${escapeHtml(tr("authorizedActionsLabel"))}</div>
    ${state.actions.filter(action => `${action.name} ${action.id} ${action.executor} ${action.description}`.toLowerCase().includes(query)).map(action => {
      const callers = state.agents.filter(agent => (agent.allowedActions || []).includes(action.id));
      const detail = [action.executor, callers.length ? tr("authorizedAgents", callers.length) : tr("notAuthorized")].filter(Boolean).join(" · ");
      const trail = callers.length
        ? `<span class="resource-trail">${statusBadge(action)}<span class="resource-count">${icon("plus")}</span></span>`
        : `<span class="resource-count">${icon("lock")}<span class="sr-only">${escapeHtml(tr("lockedAction"))}</span></span>`;
      return `<button class="resource-card" type="button" draggable="${callers.length > 0}" data-workflow-action-id="${escapeHtml(action.id)}" ${callers.length ? "" : "disabled"}>
        <span class="resource-icon action-avatar" data-kind="action">${icon("action")}</span><span class="resource-copy"><strong>${escapeHtml(action.name)}</strong><small>${escapeHtml(detail)}</small></span>${trail}
      </button>`;
    }).join("") || `<div class="empty-list compact-empty">${tr("noProjectAction")}</div>`}` : "";
  $("#agent-list").innerHTML = workflowCards + visible.map(agent => `
    <button class="resource-card${state.selectedAgent?.id === agent.id ? " selected" : ""}" type="button" draggable="${state.section !== "ai" && resourceSection === "workflow"}" data-agent-id="${escapeHtml(agent.id)}">
      <span class="resource-icon" data-kind="agent">${escapeHtml(initials(agent.name))}</span>
      <span class="resource-copy"><strong>${escapeHtml(agent.name)}</strong><small>${escapeHtml(agent.path)}</small></span>
      ${resourceSection === "workflow" ? `<span class="resource-trail">${statusBadge(agent)}<span class="resource-count">${icon("plus")}</span></span>` : statusBadge(agent)}
    </button>
  `).join("") + actionCards;
  document.querySelectorAll("[data-agent-id]").forEach(card => {
    card.addEventListener("click", async () => {
      if (!await flushAIDraftBeforeLeaving()) return;
      if (state.section === "ai") setSection(resourceSection);
      if (resourceSection === "workflow") addAgent(card.dataset.agentId);
      else await openAgent(card.dataset.agentId);
    });
    card.addEventListener("dragstart", event => {
      if (state.section === "ai" || resourceSection !== "workflow") { event.preventDefault(); return; }
      event.dataTransfer.setData("text/agent-id", card.dataset.agentId);
      event.dataTransfer.effectAllowed = "copy";
    });
  });
  document.querySelectorAll("[data-workflow-action-id]").forEach(card => {
    card.addEventListener("click", async () => {
      if (!await flushAIDraftBeforeLeaving()) return;
      if (state.section === "ai") setSection("workflow");
      addActionNode(card.dataset.workflowActionId);
    });
    card.addEventListener("dragstart", event => {
      event.dataTransfer.setData("text/action-id", card.dataset.workflowActionId);
      event.dataTransfer.effectAllowed = "copy";
    });
  });
  document.querySelectorAll("[data-workflow-id]").forEach(card => card.addEventListener("click", async () => {
    if (!await flushAIDraftBeforeLeaving()) return;
    if (state.section === "ai") setSection("workflow");
    await loadWorkflow(card.dataset.workflowId);
  }));
}

function renderActionLibrary() {
  const query = $("#resource-search").value.trim().toLowerCase();
  const visible = state.actions.filter(action => `${action.name} ${action.id} ${action.executor} ${action.description}`.toLowerCase().includes(query));
  renderScanSummary();
  $("#action-list").innerHTML = visible.length ? visible.map(action => {
    // Studio-only drafts have no file path yet: fall back to the id, never a dangling "·".
    const location = String(action.path || action.source || "").trim() || action.id;
    const detail = [action.executor, location].filter(Boolean).join(" · ");
    return `
    <button class="resource-card${state.selectedAction?.id === action.id ? " selected" : ""}" type="button" data-action-id="${escapeHtml(action.id)}">
      <span class="resource-icon action-avatar" data-kind="action">${icon("action")}</span><span class="resource-copy"><strong>${escapeHtml(action.name || action.id)}</strong><small>${escapeHtml(detail)}</small></span>${statusBadge(action)}
    </button>`;
  }).join("") : `<div class="empty-list">还没有 Action。<br>点击“新建 JSON”或使用 AI 创建。</div>`;
  document.querySelectorAll("[data-action-id]").forEach(card => card.addEventListener("click", async () => {
    if (!await flushAIDraftBeforeLeaving()) return;
    await openAction(card.dataset.actionId);
  }));
}

async function loadWorkflow(workflowId) {
  const loadToken = ++state.resourceLoadTokens.workflows;
  let context;
  try {
    if (state.workflow?.id && state.workflow.id !== workflowId && !await flushAutosaveKind("workflows")) {
      throw new Error("当前 Workflow 草稿尚未保存，已取消切换。");
    }
    if (state.resourceLoadTokens.workflows !== loadToken) return;
    context = requireProjectContext();
    const detail = await projectApi(context.projectId, `/workflows/${encodeURIComponent(workflowId)}`);
    if (state.resourceLoadTokens.workflows !== loadToken || !isCurrentProjectContext(context)) return;
    const workflow = resourceFrom(detail, "workflow");
    if (!workflow) throw new Error("Workflow not found.");
    state.workflow = workflow;
    rememberResourceRevision("workflows", workflow.id, revisionFrom(detail, workflow));
    prepareViewForWorkflow(true);
    $("#workflow-name").value = state.workflow.name;
    state.selectedNodeId = null;
    state.selectedEdgeId = null;
    markSaved();
    state.workflowTest = null;
    renderWorkflowTestPanel();
    render();
    void validateWorkflow(false, context);
  } catch (error) {
    if (state.resourceLoadTokens.workflows === loadToken && (!context || isCurrentProjectContext(context))) toast(error.message, true);
  }
}

function renderSkillLibrary() {
  const query = $("#resource-search").value.trim().toLowerCase();
  const visible = state.skills.filter(skill => `${skill.name} ${skill.path} ${skill.description}`.toLowerCase().includes(query));
  renderScanSummary();
  $("#skill-list").innerHTML = visible.length ? visible.map(skill => `
    <button class="resource-card${state.selectedSkill?.id === skill.id ? " selected" : ""}" type="button" data-skill-id="${escapeHtml(skill.id)}">
      <span class="resource-icon" data-kind="skill">${icon("skill")}</span><span class="resource-copy"><strong>${escapeHtml(skill.name)}</strong><small>${escapeHtml(skill.path)}</small></span>${statusBadge(skill)}
    </button>`).join("") : `<div class="empty-list">这个项目还没有 SKILL.md。</div>`;
  document.querySelectorAll("[data-skill-id]").forEach(card => card.addEventListener("click", async () => {
    if (!await flushAIDraftBeforeLeaving()) return;
    await openSkill(card.dataset.skillId);
  }));
}

// $agent-/$workflow- skills are Studio output, not skills the user wrote.
function handwrittenSkillCount() {
  return state.skills.filter(skill => !skill.generated).length;
}

// The open workflow's summary lags behind unsaved canvas edits, so count it live.
function workflowCountsLabel(workflow) {
  const live = state.workflow?.id === workflow.id ? state.workflow : null;
  const nodes = live ? live.nodes.length : workflow.nodeCount ?? workflow.nodes?.length ?? 0;
  const edges = live ? live.edges.length : workflow.edgeCount ?? workflow.edges?.length ?? 0;
  return tr("nodesAndConnections", nodes, edges);
}

function renderResources() {
  const resourceSection = activeResourceSection();
  const isProjects = resourceSection === "projects";
  const isSkills = resourceSection === "skills";
  const isActions = resourceSection === "actions";
  $("#project-sidebar-list").classList.toggle("hidden", !isProjects);
  $("#agent-list").classList.toggle("hidden", isProjects || isSkills || isActions);
  $("#action-list").classList.toggle("hidden", !isActions);
  $("#skill-list").classList.toggle("hidden", !isSkills);
  $("#workflow-list").classList.add("hidden");
  if (isProjects) { renderProjectList(); renderSelectedProject(); }
  else if (isSkills) renderSkillLibrary();
  else if (isActions) renderActionLibrary();
  else renderAgentLibrary();
}

function defaultNodePosition(index) {
  // Lay new nodes out inside the region the current view shows (graph space).
  const bounds = canvas.getBoundingClientRect();
  const { s } = state.view;
  const region = visibleGraphRegion();
  const width = Math.max(240, (bounds.width || canvas.clientWidth || 760) / s);
  const usableWidth = Math.max(190, width - 80);
  const columns = Math.max(1, Math.floor((usableWidth + nodeColumnStep - nodeWidth) / nodeColumnStep));
  const column = index % columns;
  const row = Math.floor(index / columns);
  return {
    x: Math.round(region.left + Math.min(Math.max(35, 40 + column * nodeColumnStep), Math.max(35, width - nodeWidth - 30))),
    y: Math.round(region.top + 50 + row * 125)
  };
}

function addAgent(agentId, position = null) {
  const agent = state.agents.find(item => item.id === agentId);
  if (!agent) return;
  const count = state.workflow.nodes.length;
  const fallbackPosition = defaultNodePosition(count);
  const x = position?.x ?? fallbackPosition.x;
  const y = position?.y ?? fallbackPosition.y;
  const node = {
    id: uid("node"),
    type: "agent",
    agentId: agent.id,
    label: agent.name,
    role: agent.description,
    entrypoint: agent.entrypoint,
    model: agent.model || "inherit",
    parallel: true,
    position: { x, y }
  };
  state.workflow.nodes.push(node);
  selectNode(node.id);
  markDirty();
  render();
  ensureWorkflowVisible();
}

function addActionNode(actionId, position = null) {
  const action = state.actions.find(item => item.id === actionId);
  const callers = state.agents.filter(agent => (agent.allowedActions || []).includes(actionId));
  if (!action || !callers.length) {
    toast("请先在 Agent 编辑界面允许至少一个 Agent 调用这个 Action", true);
    return;
  }
  const count = state.workflow.nodes.length;
  const fallbackPosition = defaultNodePosition(count);
  const node = {
    id: uid("node"),
    type: "action",
    actionId: action.id,
    agentId: callers[0].id,
    label: action.name,
    executor: action.executor,
    parallel: true,
    position: {
      x: position?.x ?? fallbackPosition.x,
      y: position?.y ?? fallbackPosition.y
    }
  };
  state.workflow.nodes.push(node);
  selectNode(node.id);
  markDirty();
  render();
  ensureWorkflowVisible();
}

function identityView() {
  return { s: 1, tx: 0, ty: 0 };
}

function isIdentityView(view = state.view) {
  return view.s === 1 && view.tx === 0 && view.ty === 0;
}

function canvasHasSize() {
  return canvas.clientWidth > 0 && canvas.clientHeight > 0;
}

// Identity leaves no transform (and so no stacking context). The tutorial only
// targets #canvas itself, which sits outside the transformed viewport.
function applyView() {
  if (!canvasViewport) return;
  const { s, tx, ty } = state.view;
  const identity = isIdentityView();
  canvasViewport.style.transform = identity ? "" : `translate(${tx}px, ${ty}px) scale(${s})`;
  // The dot grid travels with the view, so panning reads as moving the paper.
  let grid = 20 * s;
  while (grid < 10) grid *= 2;
  canvas.style.backgroundSize = identity ? "" : `${grid}px ${grid}px`;
  canvas.style.backgroundPosition = identity ? "" : `${tx}px ${ty}px`;
  const percent = Math.round(s * 100);
  const readout = $("#zoom-readout");
  if (readout) {
    readout.textContent = `${percent}%`;
    readout.setAttribute("aria-label", tr("zoomLabel", percent));
  }
  const zoomOut = $("#zoom-out");
  const zoomIn = $("#zoom-in");
  if (zoomOut) zoomOut.disabled = s <= minZoom + 1e-4;
  if (zoomIn) zoomIn.disabled = s >= maxZoom - 1e-4;
}

function visibleGraphRegion() {
  const { s, tx, ty } = state.view;
  return { left: -tx / s, top: -ty / s, width: canvas.clientWidth / s, height: canvas.clientHeight / s };
}

function clientToGraph(clientX, clientY) {
  const bounds = canvas.getBoundingClientRect();
  const { s, tx, ty } = state.view;
  return {
    x: (clientX - bounds.left - canvas.clientLeft - tx) / s,
    y: (clientY - bounds.top - canvas.clientTop - ty) / s
  };
}

// With pan and zoom a node may live anywhere in a generous graph area; the
// view follows it (drag auto-pan, revealGraphRect) instead of pinning it.
function nodeClampBounds() {
  return { minX: -graphLimit, minY: -graphLimit, maxX: graphLimit - nodeWidth, maxY: graphLimit - nodeHeight };
}

function clampNodePosition(x, y) {
  const bounds = nodeClampBounds();
  const clamp = (value, min, max) => Math.min(Math.floor(max), Math.max(Math.ceil(min), Math.round(value)));
  return {
    x: clamp(x, bounds.minX, bounds.maxX),
    y: clamp(y, bounds.minY, bounds.maxY)
  };
}

function graphBounds() {
  const nodes = state.workflow.nodes;
  if (!nodes.length) return null;
  const xs = nodes.map(node => Number(node.position?.x) || 0);
  const ys = nodes.map(node => Number(node.position?.y) || 0);
  const minX = Math.min(...xs);
  const minY = Math.min(...ys);
  const maxX = Math.max(...xs) + nodeWidth;
  const maxY = Math.max(...ys) + nodeHeight;
  return { minX, minY, maxX, maxY, width: maxX - minX, height: maxY - minY };
}

// Pure view computation: never touches node positions or the dirty state.
function computeFit({ center = false } = {}) {
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  if (width <= 0 || height <= 0) return { ...state.view };
  const box = graphBounds();
  if (!box) return identityView();
  if (!center && box.minX >= 10 && box.maxX <= width - 10 && box.minY >= 10 && box.maxY <= height - 13) {
    return identityView();
  }
  const availableWidth = Math.max(1, width - 2 * viewPad);
  const availableHeight = Math.max(1, height - 2 * viewPad);
  const s = Math.min(1, availableWidth / Math.max(1, box.width), availableHeight / Math.max(1, box.height));
  const scale = Math.max(0.0001, Math.round(s * 10000) / 10000);
  const tx = Math.round(viewPad + (availableWidth - box.width * scale) / 2 - box.minX * scale);
  const ty = Math.round(viewPad + (availableHeight - box.height * scale) / 2 - box.minY * scale);
  return { s: scale, tx: tx || 0, ty: ty || 0 };
}

function autoFitView() {
  if (!canvasHasSize()) {
    renderEdges();
    return;
  }
  state.viewFitPending = false;
  state.view = computeFit({ center: false });
  applyView();
  renderEdges();
}

// 适应: center the whole graph in the canvas. A view action only — it must
// never rewrite positions or call markDirty, so a synced workflow stays synced.
function fitView() {
  state.viewFitPending = false;
  state.viewTouched = false;
  state.view = computeFit({ center: true });
  applyView();
  renderEdges();
}

function clampZoom(value) {
  return Math.min(maxZoom, Math.max(minZoom, value));
}

// Every manual pan or zoom lands here. The transform carries edges, labels and
// the delete popover (all in graph space), so nothing re-renders or saves.
function setManualView(view) {
  state.view = view;
  state.viewTouched = true;
  state.viewFitPending = false;
  applyView();
}

// Zoom so the graph point under (clientX, clientY) stays under the pointer.
function zoomViewAt(clientX, clientY, nextScale) {
  const scale = Math.round(clampZoom(nextScale) * 10000) / 10000;
  if (Math.abs(scale - state.view.s) < 1e-4) return;
  const bounds = canvas.getBoundingClientRect();
  const point = clientToGraph(clientX, clientY);
  const localX = clientX - bounds.left - canvas.clientLeft;
  const localY = clientY - bounds.top - canvas.clientTop;
  setManualView({ s: scale, tx: Math.round(localX - point.x * scale), ty: Math.round(localY - point.y * scale) });
}

function zoomViewBy(factor) {
  const bounds = canvas.getBoundingClientRect();
  zoomViewAt(bounds.left + canvas.clientLeft + canvas.clientWidth / 2, bounds.top + canvas.clientTop + canvas.clientHeight / 2, state.view.s * factor);
}

function panViewBy(dx, dy) {
  if (!dx && !dy) return;
  setManualView({ ...state.view, tx: Math.round(state.view.tx + dx), ty: Math.round(state.view.ty + dy) });
}

// Pan just enough to bring a graph rectangle (e.g. a node) on screen.
function revealGraphRect(x, y, width, height, margin = 16) {
  if (!canvasHasSize()) return;
  const { s, tx, ty } = state.view;
  const left = x * s + tx;
  const top = y * s + ty;
  const right = left + width * s;
  const bottom = top + height * s;
  let dx = 0;
  let dy = 0;
  if (left < margin) dx = margin - left;
  else if (right > canvas.clientWidth - margin) dx = canvas.clientWidth - margin - right;
  if (top < margin) dy = margin - top;
  else if (bottom > canvas.clientHeight - margin) dy = canvas.clientHeight - margin - bottom;
  panViewBy(dx, dy);
}

// Refit only when part of the graph has left the visible canvas, so adding a
// node that fits does not jump the current view.
function ensureWorkflowVisible() {
  const box = graphBounds();
  if (!box || !canvasHasSize()) return;
  const { s, tx, ty } = state.view;
  const visible = box.minX * s + tx >= 0 && box.maxX * s + tx <= canvas.clientWidth
    && box.minY * s + ty >= 0 && box.maxY * s + ty <= canvas.clientHeight;
  if (!visible && !state.viewTouched) autoFitView();
}

function workflowViewKey() {
  return `${state.project?.id || ""}\u0000${state.workflow?.id || ""}`;
}

// A newly opened workflow starts from identity; the next visible render fits it.
function prepareViewForWorkflow(force = false) {
  const key = workflowViewKey();
  if (!force && key === state.viewKey) return;
  state.viewKey = key;
  state.view = identityView();
  state.viewTouched = false;
  state.viewFitPending = true;
  applyView();
}

function render() {
  prepareViewForWorkflow();
  renderNodes();
  requestAnimationFrame(() => {
    if (state.viewFitPending && canvasHasSize()) autoFitView();
    else renderEdges();
  });
  renderInspector();
  updateResourceActionButtons("workflows", state.workflow);
  $("#empty-canvas").classList.toggle("hidden", state.workflow.nodes.length > 0);
}

function focusedCanvasItemId(container, selector, key) {
  const active = document.activeElement;
  if (!active || !container.contains(active)) return null;
  return active.closest?.(selector)?.dataset[key] || null;
}

// renderNodes/renderEdges rebuild innerHTML, which drops keyboard focus. Put it
// back on the same item, or on the canvas when that item no longer exists.
function restoreCanvasItemFocus(container, selector, key, id) {
  if (!id) return;
  const element = [...container.querySelectorAll(selector)].find(item => item.dataset[key] === id);
  (element || canvas).focus({ preventScroll: true });
}

function renderNodes() {
  const focusedNodeId = focusedCanvasItemId(nodeLayer, ".workflow-node", "nodeId");
  nodeLayer.innerHTML = state.workflow.nodes.map(node => {
    const isAction = (node.type || "agent") === "action";
    const agent = state.agents.find(item => item.id === node.agentId);
    const action = isAction ? state.actions.find(item => item.id === node.actionId) : null;
    const isSelected = state.selectedNodeId === node.id;
    const selected = isSelected ? " selected" : "";
    const source = state.connectSource === node.id ? " connect-source" : "";
    return `
      <article class="workflow-node${isAction ? " action-node" : ""}${selected}${source}" data-node-id="${escapeHtml(node.id)}" tabindex="0" role="button" aria-label="${escapeHtml(tr("nodeAriaLabel", node.label || "", isAction ? "Action" : "Agent"))}" aria-pressed="${isSelected ? "true" : "false"}" style="transform: translate(${Number(node.position.x)}px, ${Number(node.position.y)}px)">
        <button class="node-port input" type="button" tabindex="-1" aria-label="连接到 ${escapeHtml(node.label)}" data-port="input"></button>
        <div class="node-head">
          <span class="node-avatar" data-kind="${isAction ? "action" : "agent"}">${isAction ? icon("action") : escapeHtml(initials(node.label))}</span>
          <span class="node-copy"><strong>${escapeHtml(node.label)}</strong><span>${escapeHtml(isAction ? `${action?.executor || node.executor || "action"} · ${agent?.name || "未授权"}` : agent?.format || "local agent")}</span></span>
        </div>
        <div class="node-role">${escapeHtml(isAction ? action?.description || "确定性 Action" : node.role || "尚未填写职责")}</div>
        <button class="node-port output" type="button" tabindex="-1" aria-label="从 ${escapeHtml(node.label)} 连接" data-port="output"></button>
      </article>`;
  }).join("");

  document.querySelectorAll(".workflow-node").forEach(element => {
    const nodeId = element.dataset.nodeId;
    element.addEventListener("pointerdown", event => beginNodeDrag(event, nodeId));
    element.addEventListener("click", event => {
      event.stopPropagation();
      if (event.target.dataset.port) return;
      activateNode(nodeId);
    });
    element.addEventListener("dblclick", event => {
      event.stopPropagation();
      const node = state.workflow.nodes.find(item => item.id === nodeId);
      if ((node?.type || "agent") === "action" && node.actionId) openAction(node.actionId);
      else if (node?.agentId) openAgent(node.agentId);
    });
    element.querySelector('[data-port="output"]').addEventListener("pointerdown", event => beginConnectionDrag(event, nodeId));
    element.querySelector('[data-port="input"]').addEventListener("click", event => {
      event.stopPropagation();
      if (state.connectSource) completeConnection(nodeId);
    });
  });
  restoreCanvasItemFocus(nodeLayer, ".workflow-node", "nodeId", focusedNodeId);
}

function activateNode(nodeId) {
  if (state.mode === "connect" && state.connectSource) completeConnection(nodeId);
  else selectNode(nodeId);
}

function moveNodeBy(nodeId, dx, dy) {
  const node = state.workflow.nodes.find(item => item.id === nodeId);
  if (!node) return;
  const { x, y } = clampNodePosition(Number(node.position.x) + dx, Number(node.position.y) + dy);
  if (x === node.position.x && y === node.position.y) return;
  node.position.x = x;
  node.position.y = y;
  const element = [...nodeLayer.querySelectorAll(".workflow-node")].find(item => item.dataset.nodeId === nodeId);
  if (element) element.style.transform = `translate(${x}px, ${y}px)`;
  renderEdges();
  revealGraphRect(x, y, nodeWidth, nodeHeight);
  markDirty();
}

// Backspace/Delete may only remove canvas items while the canvas (or nothing)
// owns the keyboard: never from dialogs, the tutorial, or other controls.
function canvasOwnsDeleteKey() {
  if (state.section !== "workflow") return false;
  if (document.querySelector("dialog[open]")) return false;
  const active = document.activeElement;
  const focusInCanvas = Boolean(active && canvas.contains(active));
  const overlay = $("#tutorial-overlay");
  if (overlay && !overlay.classList.contains("hidden") && !focusInCanvas) return false;
  if (!active || active === document.body) return true;
  if (!focusInCanvas) return false;
  return !(active.isContentEditable || active.matches?.("input, textarea, select, [contenteditable]"));
}

function handleCanvasKeydown(event) {
  if (event.altKey || event.metaKey || event.ctrlKey) return;
  const target = event.target;
  const isActivate = event.key === "Enter" || event.key === " ";
  const edgeGroup = target.closest?.(".edge-group");
  if (edgeGroup && edgePaths.contains(edgeGroup)) {
    if (!isActivate) return;
    event.preventDefault();
    event.stopPropagation();
    selectEdge(edgeGroup.dataset.edgeId);
    return;
  }
  const nodeElement = target.classList?.contains("workflow-node") ? target : null;
  if (nodeElement && isActivate && event.repeat) {
    event.preventDefault();
    return;
  }
  if (nodeElement && isActivate) {
    event.preventDefault();
    event.stopPropagation();
    activateNode(nodeElement.dataset.nodeId);
    return;
  }
  const deltas = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
  const direction = deltas[event.key];
  if (!direction) return;
  const nodeId = nodeElement ? nodeElement.dataset.nodeId : (target === canvas ? state.selectedNodeId : null);
  if (!nodeId) return;
  event.preventDefault();
  const step = event.shiftKey ? 40 : 10;
  moveNodeBy(nodeId, direction[0] * step, direction[1] * step);
}

function updateDraftConnection(clientX, clientY) {
  const source = state.workflow.nodes.find(item => item.id === state.connectSource);
  if (!source) return;
  const sx = source.position.x + 190;
  const sy = source.position.y + 46;
  const pointer = clientToGraph(clientX, clientY);
  const px = pointer.x;
  const py = pointer.y;
  const distance = Math.max(55, Math.abs(px - sx) * .48);
  draftEdge.setAttribute("d", `M ${sx} ${sy} C ${sx + distance} ${sy}, ${px - distance} ${py}, ${px} ${py}`);
}

function beginConnectionDrag(event, sourceId) {
  if (event.button !== 0) return;
  event.preventDefault();
  event.stopPropagation();
  const origin = { x: event.clientX, y: event.clientY };
  state.mode = "connect";
  state.connectSource = sourceId;
  state.connectionDrag = { sourceId, moved: false };
  canvas.classList.add("connecting");
  event.currentTarget.closest(".workflow-node")?.classList.add("connect-source");
  updateDraftConnection(event.clientX, event.clientY);
  const move = moveEvent => {
    if (!state.connectionDrag) return;
    if (Math.abs(moveEvent.clientX - origin.x) + Math.abs(moveEvent.clientY - origin.y) > 4) state.connectionDrag.moved = true;
    updateDraftConnection(moveEvent.clientX, moveEvent.clientY);
  };
  const up = upEvent => {
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", up);
    const moved = Boolean(state.connectionDrag?.moved);
    state.connectionDrag = null;
    draftEdge.setAttribute("d", "");
    if (moved) {
      const target = document.elementFromPoint(upEvent.clientX, upEvent.clientY);
      const input = target?.closest?.('[data-port="input"]');
      const targetId = input?.closest?.(".workflow-node")?.dataset.nodeId;
      if (targetId) completeConnection(targetId);
      else cancelConnection();
    } else {
      updateToolState();
      render();
    }
  };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", up);
}

function beginNodeDrag(event, nodeId) {
  if (event.button !== 0 || event.target.dataset.port || state.mode === "connect" || state.spaceHeld) return;
  const node = state.workflow.nodes.find(item => item.id === nodeId);
  if (!node) return;
  const element = event.currentTarget;
  element.setPointerCapture(event.pointerId);
  // The grab point is kept in graph space, so the node stays under the pointer
  // even while the view auto-pans underneath it.
  const grab = clientToGraph(event.clientX, event.clientY);
  state.dragging = {
    nodeId,
    startX: event.clientX,
    startY: event.clientY,
    clientX: event.clientX,
    clientY: event.clientY,
    offsetX: grab.x - node.position.x,
    offsetY: grab.y - node.position.y,
    moved: false,
    frame: 0
  };
  const place = () => {
    const drag = state.dragging;
    if (!drag) return;
    const pointer = clientToGraph(drag.clientX, drag.clientY);
    const next = clampNodePosition(pointer.x - drag.offsetX, pointer.y - drag.offsetY);
    node.position.x = next.x;
    node.position.y = next.y;
    element.style.transform = `translate(${next.x}px, ${next.y}px)`;
    renderEdges();
  };
  // Near (or past) a canvas edge the view keeps panning, one step per frame,
  // so a node can be carried beyond what is currently visible.
  const autoPan = () => {
    const drag = state.dragging;
    if (!drag) return;
    drag.frame = 0;
    const bounds = canvas.getBoundingClientRect();
    const edge = 28;
    const speed = 12;
    const dx = drag.clientX < bounds.left + edge ? speed : drag.clientX > bounds.right - edge ? -speed : 0;
    const dy = drag.clientY < bounds.top + edge ? speed : drag.clientY > bounds.bottom - edge ? -speed : 0;
    if (!dx && !dy) return;
    panViewBy(dx, dy);
    place();
    drag.frame = requestAnimationFrame(autoPan);
  };
  const move = moveEvent => {
    const drag = state.dragging;
    if (!drag) return;
    drag.clientX = moveEvent.clientX;
    drag.clientY = moveEvent.clientY;
    if (Math.abs(moveEvent.clientX - drag.startX) + Math.abs(moveEvent.clientY - drag.startY) > 2) drag.moved = true;
    // A click (below the move threshold) must not nudge the stored position.
    if (!drag.moved) return;
    place();
    if (!drag.frame) drag.frame = requestAnimationFrame(autoPan);
  };
  const up = () => {
    element.removeEventListener("pointermove", move);
    element.removeEventListener("pointerup", up);
    element.removeEventListener("pointercancel", up);
    if (state.dragging?.frame) cancelAnimationFrame(state.dragging.frame);
    if (state.dragging?.moved) markDirty();
    state.dragging = null;
  };
  element.addEventListener("pointermove", move);
  element.addEventListener("pointerup", up);
  element.addEventListener("pointercancel", up);
}

// Pan and zoom: wheel/trackpad scroll pans, Cmd/Ctrl+wheel and trackpad pinch
// zoom around the pointer; dragging empty canvas, Space+drag or a middle-button
// drag pans; two touch points pinch-zoom. View changes never save anything.
function bindCanvasPanZoom() {
  const touches = new Map();
  let pan = null;
  let pinch = null;
  let suppressClick = false;

  const pinchFrame = () => {
    const [a, b] = [...touches.values()];
    return { distance: Math.hypot(a.x - b.x, a.y - b.y) || 1, midX: (a.x + b.x) / 2, midY: (a.y + b.y) / 2 };
  };
  const startPan = event => {
    pan.active = true;
    suppressClick = true;
    canvas.classList.add("panning");
    if (!canvas.hasPointerCapture(event.pointerId)) canvas.setPointerCapture(event.pointerId);
  };
  const endPointer = event => {
    touches.delete(event.pointerId);
    if (touches.size < 2) pinch = null;
    if (pan && event.pointerId === pan.pointerId) {
      canvas.classList.remove("panning");
      if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
      pan = null;
    }
  };

  // Capture phase: Space/middle-button drags over a node or port pan instead.
  canvas.addEventListener("pointerdown", event => {
    if (state.section !== "workflow") return;
    suppressClick = false;
    const onBackground = event.target === canvas;
    if (event.pointerType === "touch" && onBackground) {
      touches.set(event.pointerId, { x: event.clientX, y: event.clientY });
      if (touches.size === 2) {
        if (pan) canvas.classList.remove("panning");
        pan = null;
        pinch = { ...pinchFrame(), scale: state.view.s };
        return;
      }
    }
    const forcedPan = event.button === 1 || (event.button === 0 && state.spaceHeld);
    const backgroundPan = event.button === 0 && onBackground && state.mode !== "connect";
    if (!forcedPan && !backgroundPan) return;
    if (forcedPan) {
      event.preventDefault();
      event.stopPropagation();
    }
    pan = { pointerId: event.pointerId, startX: event.clientX, startY: event.clientY, lastX: event.clientX, lastY: event.clientY, active: false };
    if (forcedPan) startPan(event);
  }, true);

  canvas.addEventListener("pointermove", event => {
    if (touches.has(event.pointerId)) touches.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (pinch && touches.size === 2) {
      const frame = pinchFrame();
      panViewBy(frame.midX - pinch.midX, frame.midY - pinch.midY);
      zoomViewAt(frame.midX, frame.midY, pinch.scale * frame.distance / pinch.distance);
      pinch.midX = frame.midX;
      pinch.midY = frame.midY;
      suppressClick = true;
      return;
    }
    if (!pan || event.pointerId !== pan.pointerId) return;
    if (!pan.active) {
      if (Math.abs(event.clientX - pan.startX) + Math.abs(event.clientY - pan.startY) < 4) return;
      startPan(event);
    }
    panViewBy(event.clientX - pan.lastX, event.clientY - pan.lastY);
    pan.lastX = event.clientX;
    pan.lastY = event.clientY;
  });
  canvas.addEventListener("pointerup", endPointer);
  canvas.addEventListener("pointercancel", endPointer);
  canvas.addEventListener("lostpointercapture", endPointer);
  // A pan ends in a click on the canvas; it must not also clear the selection.
  canvas.addEventListener("click", event => {
    if (suppressClick) {
      suppressClick = false;
      event.stopPropagation();
      return;
    }
    clearCanvasSelection();
  });

  canvas.addEventListener("wheel", event => {
    if (state.section !== "workflow" || !canvasHasSize()) return;
    event.preventDefault();
    const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? canvas.clientHeight : 1;
    if (event.ctrlKey || event.metaKey) {
      const delta = event.deltaY * unit;
      // Trackpad pinches arrive as many small deltas, mouse wheels as large notches.
      const sensitivity = Math.abs(delta) < 40 ? 0.012 : 0.0025;
      zoomViewAt(event.clientX, event.clientY, state.view.s * Math.exp(-delta * sensitivity));
      return;
    }
    let dx = event.deltaX * unit;
    let dy = event.deltaY * unit;
    if (event.shiftKey && !dx) {
      dx = dy;
      dy = 0;
    }
    panViewBy(-dx, -dy);
  }, { passive: false });

  // Cmd/Ctrl + = / - / 0 while the canvas (or a node in it) has focus.
  canvas.addEventListener("keydown", event => {
    if (!(event.metaKey || event.ctrlKey) || event.altKey) return;
    if (event.key === "=" || event.key === "+") zoomViewBy(zoomStep);
    else if (event.key === "-" || event.key === "_") zoomViewBy(1 / zoomStep);
    else if (event.key === "0") zoomViewBy(1 / state.view.s);
    else return;
    event.preventDefault();
  });

  // Hold Space to pan with a plain drag (capture phase, before node activation).
  document.addEventListener("keydown", event => {
    if (event.code !== "Space" || state.section !== "workflow") return;
    const active = document.activeElement;
    if (document.querySelector("dialog[open]")) return;
    const onCanvas = !active || active === document.body || active === canvas;
    const onNode = Boolean(active?.classList?.contains("workflow-node"));
    if (!onCanvas && !onNode) return;
    if (onCanvas) event.preventDefault();
    if (!state.spaceHeld) {
      state.spaceHeld = true;
      canvas.classList.add("space-pan");
    }
  }, true);
  const releaseSpace = () => {
    if (!state.spaceHeld) return;
    state.spaceHeld = false;
    canvas.classList.remove("space-pan");
  };
  document.addEventListener("keyup", event => { if (event.code === "Space") releaseSpace(); });
  window.addEventListener("blur", releaseSpace);

  // Keyboard focus on an off-screen node brings it into view (not mouse focus).
  nodeLayer.addEventListener("focusin", event => {
    const element = event.target.closest?.(".workflow-node");
    if (!element || !element.matches(":focus-visible")) return;
    const node = state.workflow.nodes.find(item => item.id === element.dataset.nodeId);
    if (node) revealGraphRect(Number(node.position.x) || 0, Number(node.position.y) || 0, nodeWidth, nodeHeight);
  });

  $("#zoom-in")?.addEventListener("click", () => zoomViewBy(zoomStep));
  $("#zoom-out")?.addEventListener("click", () => zoomViewBy(1 / zoomStep));
  $("#zoom-readout")?.addEventListener("click", fitView);
}

function edgeCurve(sourceNode, targetNode) {
  const sx = sourceNode.position.x + 190;
  const sy = sourceNode.position.y + 46;
  const tx = targetNode.position.x;
  const ty = targetNode.position.y + 46;
  const distance = Math.max(50, Math.abs(tx - sx) * .48);
  const c1x = sx + (tx >= sx ? distance : 75);
  const c2x = tx - (tx >= sx ? distance : 75);
  return { path: `M ${sx} ${sy} C ${c1x} ${sy}, ${c2x} ${ty}, ${tx} ${ty}`, sx, sy, tx, ty };
}

function edgeMidpoint(curve) {
  return { x: (curve.sx + curve.tx) / 2, y: (curve.sy + curve.ty) / 2 };
}

function truncateEdgeLabel(text, maxLength = 14) {
  const chars = [...text];
  return chars.length > maxLength ? `${chars.slice(0, maxLength).join("")}…` : text;
}

function renderEdges() {
  const focusedEdgeId = focusedCanvasItemId(edgePaths, ".edge-group", "edgeId");
  let selectedCurve = null;
  let selectedHasLabel = false;
  const labels = [];
  edgePaths.innerHTML = state.workflow.edges.map(edge => {
    const source = state.workflow.nodes.find(node => node.id === edge.source);
    const target = state.workflow.nodes.find(node => node.id === edge.target);
    if (!source || !target) return "";
    const curve = edgeCurve(source, target);
    const isSelected = edge.id === state.selectedEdgeId;
    const selected = isSelected ? " selected" : "";
    const condition = String(edge.condition ?? "").trim();
    if (isSelected) {
      selectedCurve = curve;
      selectedHasLabel = Boolean(condition);
    }
    if (condition) {
      const midpoint = edgeMidpoint(curve);
      labels.push(`<span class="edge-label${selected}" data-edge-id="${escapeHtml(edge.id)}" title="${escapeHtml(condition)}" style="left:${Math.round(midpoint.x)}px;top:${Math.round(midpoint.y)}px">${escapeHtml(truncateEdgeLabel(condition))}</span>`);
    }
    return `<g class="edge-group${selected}" data-edge-id="${escapeHtml(edge.id)}" tabindex="0" focusable="true" role="button" aria-label="${escapeHtml(tr("edgeAriaLabel", source.label || "", target.label || "", edge.condition || ""))}" aria-pressed="${isSelected ? "true" : "false"}">
      <path class="edge-hit" d="${curve.path}"></path>
      <path class="edge-path" d="${curve.path}"></path>
    </g>`;
  }).join("");
  edgePaths.querySelectorAll(".edge-group").forEach(group => {
    group.addEventListener("click", event => {
      event.stopPropagation();
      selectEdge(group.dataset.edgeId);
    });
  });
  const labelLayer = $("#edge-label-layer");
  if (labelLayer) labelLayer.innerHTML = labels.join("");
  const deleteButton = $("#edge-delete-popover");
  deleteButton.classList.toggle("hidden", !selectedCurve);
  if (selectedCurve) {
    const spot = clearEdgePopoverSpot(edgeMidpoint(selectedCurve), selectedHasLabel && labelLayer ? 30 : 18);
    deleteButton.style.left = `${spot.x}px`;
    deleteButton.style.top = `${spot.y}px`;
  }
  restoreCanvasItemFocus(edgePaths, ".edge-group", "edgeId", focusedEdgeId);
}

// The delete popover sits beside the edge midpoint (clear of its label) and
// avoids node bodies: first clear spot wins, else the least-covered one.
// Positions are graph coordinates.
function clearEdgePopoverSpot(midpoint, gap) {
  const halfWidth = 52;
  const halfHeight = 14;
  const margin = 4;
  const coveredArea = (x, y) => state.workflow.nodes.reduce((area, node) => {
    const nodeX = Number(node.position?.x) || 0;
    const nodeY = Number(node.position?.y) || 0;
    const overlapX = Math.min(x + halfWidth + margin, nodeX + nodeWidth) - Math.max(x - halfWidth - margin, nodeX);
    const overlapY = Math.min(y + halfHeight + margin, nodeY + nodeHeight) - Math.max(y - halfHeight - margin, nodeY);
    return area + (overlapX > 0 && overlapY > 0 ? overlapX * overlapY : 0);
  }, 0);
  const candidates = [[0, -gap], [0, gap], [-150, 0], [150, 0], [0, -gap - 36], [0, gap + 36], [-210, 0], [210, 0]];
  let best = null;
  for (const [dx, dy] of candidates) {
    const spot = { x: midpoint.x + dx, y: midpoint.y + dy, area: coveredArea(midpoint.x + dx, midpoint.y + dy) };
    if (!spot.area) return spot;
    if (!best || spot.area < best.area) best = spot;
  }
  return best;
}

function workflowPathExists(fromId, toId) {
  const seen = new Set();
  const pending = [fromId];
  while (pending.length) {
    const nodeId = pending.pop();
    if (nodeId === toId) return true;
    if (seen.has(nodeId)) continue;
    seen.add(nodeId);
    state.workflow.edges.forEach(edge => { if (edge.source === nodeId) pending.push(edge.target); });
  }
  return false;
}

function completeConnection(targetId) {
  const sourceId = state.connectSource;
  if (!sourceId || sourceId === targetId) {
    toast("请选择另一个节点作为连接目标", true);
    return;
  }
  if (state.workflow.edges.some(edge => edge.source === sourceId && edge.target === targetId)) {
    toast("这两个节点已经连接");
    cancelConnection();
    return;
  }
  if (workflowPathExists(targetId, sourceId)) {
    toast("这条连线会形成循环。Workflow 必须是有向无环图，请调整连接方向。", true);
    cancelConnection();
    return;
  }
  const edge = { id: uid("edge"), source: sourceId, target: targetId, condition: "上游任务完成后交接" };
  state.workflow.edges.push(edge);
  state.selectedEdgeId = edge.id;
  state.selectedNodeId = null;
  cancelConnection(false);
  markDirty();
  render();
}

function cancelConnection(renderAfter = true) {
  state.connectSource = null;
  state.connectionDrag = null;
  state.mode = "select";
  draftEdge.setAttribute("d", "");
  updateToolState();
  if (renderAfter) render();
}

function selectNode(nodeId) {
  state.selectedNodeId = nodeId;
  state.selectedEdgeId = null;
  render();
}

function selectEdge(edgeId) {
  state.selectedEdgeId = edgeId;
  state.selectedNodeId = null;
  render();
}

function renderInspector() {
  const node = state.workflow.nodes.find(item => item.id === state.selectedNodeId);
  const edge = state.workflow.edges.find(item => item.id === state.selectedEdgeId);
  $("#inspector-empty").classList.toggle("hidden", Boolean(node || edge));
  $("#node-inspector").classList.toggle("hidden", !node);
  $("#edge-inspector").classList.toggle("hidden", !edge);
  if (node) {
    const isAction = (node.type || "agent") === "action";
    const agent = state.agents.find(item => item.id === node.agentId);
    const action = isAction ? state.actions.find(item => item.id === node.actionId) : null;
    $("#selected-agent-summary").innerHTML = `<strong>${escapeHtml(isAction ? action?.name || node.label : agent?.name || node.label)}</strong><small>${escapeHtml(isAction ? `${action?.executor || "Action"} · 调用 Agent：${agent?.name || "未授权"}` : agent?.path || "Agent source missing")}</small>`;
    $("#node-label").value = node.label || "";
    $("#node-role").value = node.role || "";
    $("#node-entrypoint").value = node.entrypoint || "";
    $("#node-model").value = ["inherit", "fast", "balanced", "deep"].includes(node.model) ? node.model : "inherit";
    $("#node-parallel").checked = node.parallel !== false;
    $("#node-role-wrap").classList.toggle("hidden", isAction);
    $("#node-entrypoint-wrap").classList.toggle("hidden", isAction);
    $("#node-model-wrap").classList.toggle("hidden", isAction);
    $("#node-caller-wrap").classList.toggle("hidden", !isAction);
    if (isAction) {
      const callers = state.agents.filter(item => (item.allowedActions || []).includes(node.actionId));
      $("#node-caller").innerHTML = callers.map(item => `<option value="${escapeHtml(item.id)}" ${item.id === node.agentId ? "selected" : ""}>${escapeHtml(item.name)}</option>`).join("");
    }
  }
  if (edge) $("#edge-condition").value = edge.condition || "";
  if (!node && !edge) renderWorkflowSettings();
}

function parseStartPhrases(value) {
  const seen = new Set();
  return String(value || "").split(/[,，、\n]/)
    .map(item => item.trim().replace(/\s+/g, " "))
    .filter(item => item && !seen.has(item.toLowerCase()) && seen.add(item.toLowerCase()))
    .slice(0, 8);
}

function renderWorkflowSettings() {
  const description = $("#workflow-description");
  const phrases = $("#workflow-start-phrases");
  if (!description || !phrases) return;
  if (document.activeElement !== description) description.value = state.workflow.description || "";
  if (document.activeElement !== phrases) phrases.value = (state.workflow.startPhrases || []).join(", ");
  $("#use-default-start")?.classList.toggle("hidden", (state.workflow.startPhrases || []).length > 0);
}

function bindInspector() {
  const updateNode = (key, value) => {
    const node = state.workflow.nodes.find(item => item.id === state.selectedNodeId);
    if (!node) return;
    node[key] = value;
    markDirty();
    renderNodes();
    requestAnimationFrame(renderEdges);
  };
  $("#node-label").addEventListener("input", event => updateNode("label", event.target.value));
  $("#node-role").addEventListener("input", event => updateNode("role", event.target.value));
  $("#node-model").addEventListener("change", event => updateNode("model", event.target.value));
  $("#node-caller").addEventListener("change", event => updateNode("agentId", event.target.value));
  $("#node-parallel").addEventListener("change", event => updateNode("parallel", event.target.checked));
  $("#workflow-description")?.addEventListener("input", event => {
    state.workflow.description = event.target.value;
    markDirty();
  });
  const setStartPhrases = value => {
    state.workflow.startPhrases = parseStartPhrases(value);
    markDirty();
    $("#use-default-start")?.classList.toggle("hidden", state.workflow.startPhrases.length > 0);
  };
  $("#workflow-start-phrases")?.addEventListener("input", event => setStartPhrases(event.target.value));
  $("#use-default-start")?.addEventListener("click", () => {
    $("#workflow-start-phrases").value = "开始";
    setStartPhrases("开始");
  });
  $("#edge-condition").addEventListener("input", event => {
    const edge = state.workflow.edges.find(item => item.id === state.selectedEdgeId);
    if (edge) { edge.condition = event.target.value; markDirty(); renderEdges(); }
  });
  $("#remove-node").addEventListener("click", () => {
    const nodeId = state.selectedNodeId;
    state.workflow.nodes = state.workflow.nodes.filter(node => node.id !== nodeId);
    state.workflow.edges = state.workflow.edges.filter(edge => edge.source !== nodeId && edge.target !== nodeId);
    state.selectedNodeId = null;
    markDirty();
    render();
  });
  $("#remove-edge").addEventListener("click", () => {
    state.workflow.edges = state.workflow.edges.filter(edge => edge.id !== state.selectedEdgeId);
    state.selectedEdgeId = null;
    markDirty();
    render();
  });
}

// Shared by an empty-canvas click and the inspector close button.
function clearCanvasSelection() {
  if (state.mode === "connect") cancelConnection();
  else { state.selectedNodeId = null; state.selectedEdgeId = null; render(); }
}

function setMode(mode) {
  state.mode = mode;
  if (mode !== "connect") state.connectSource = null;
  updateToolState();
  render();
}

function updateToolState() {
  $("#select-tool").classList.toggle("active", state.mode === "select");
  $("#connect-tool").classList.toggle("active", state.mode === "connect");
  canvas.classList.toggle("connecting", state.mode === "connect");
}

function autoLayout() {
  if (!state.workflow.nodes.length) return;
  const nodes = state.workflow.nodes;
  const indegree = Object.fromEntries(nodes.map(node => [node.id, 0]));
  const next = Object.fromEntries(nodes.map(node => [node.id, []]));
  state.workflow.edges.forEach(edge => {
    if (next[edge.source] && edge.target in indegree) { next[edge.source].push(edge.target); indegree[edge.target]++; }
  });
  let current = nodes.filter(node => indegree[node.id] === 0).map(node => node.id);
  const layers = [];
  const seen = new Set();
  while (current.length) {
    layers.push(current);
    const following = [];
    current.forEach(id => {
      seen.add(id);
      next[id].forEach(target => { indegree[target]--; if (!indegree[target]) following.push(target); });
    });
    current = following;
  }
  const orphans = nodes.filter(node => !seen.has(node.id)).map(node => node.id);
  if (orphans.length) layers.push(orphans);
  // Layout is computed in graph space from the identity view, then the view is
  // refit so the whole result stays visible on narrow canvases.
  state.view = identityView();
  state.viewTouched = false;
  applyView();
  layers.forEach((layer, column) => {
    layer.forEach((id, row) => {
      const node = nodes.find(item => item.id === id);
      node.position.x = 35 + column * nodeColumnStep;
      node.position.y = 50 + row * 125;
    });
  });
  markDirty();
  render();
  autoFitView();
}

async function validateWorkflow(showToast = true, suppliedContext = null, workflow = state.workflow) {
  const badge = $("#validation-state");
  let context;
  try {
    context = suppliedContext || requireProjectContext();
    const result = await projectApi(context.projectId, "/validate", { method: "POST", body: JSON.stringify(workflow) });
    if (!isCurrentProjectContext(context)) return false;
    if (result.valid) {
      // Valid with reminders is a warning, not green: "valid" means nothing left to look at.
      const warnings = Array.isArray(result.warnings) ? result.warnings : [];
      badge.className = `validation-state ${warnings.length ? "warning" : "valid"}`;
      badge.innerHTML = `${statusDot} ${warnings.length ? `${warnings.length} 条提醒` : "结构有效"}`;
      if (showToast && warnings.length) toast(warnings[0]);
    } else {
      badge.className = "validation-state invalid";
      badge.innerHTML = `${statusDot} ${escapeHtml(result.errors[0])}`;
      if (showToast) toast(result.errors[0], true);
    }
    return result.valid;
  } catch (error) {
    if (showToast && (!context || isCurrentProjectContext(context))) toast(error.message, true);
    return false;
  }
}

function collectWorkflow() {
  state.workflow.name = $("#workflow-name").value.trim() || "Untitled workflow";
  state.workflow.id = slugify(state.workflow.id || state.workflow.name);
  return state.workflow;
}

async function persistWorkflowDraft(showToast = false) {
  let context;
  try {
    context = requireProjectContext();
  } catch (error) {
    toast(error.message, true);
    return;
  }
  collectWorkflow();
  const workflowId = state.workflow.id;
  const revision = state.resourceRevisions.workflows[workflowId];
  $("#save-state").className = "save-state";
  $("#save-state").innerHTML = "<i></i> 正在保存…";
  try {
    const result = await projectApi(context.projectId, `/workflows/${encodeURIComponent(workflowId)}`, {
      method: "PUT",
      headers: revisionHeaders(revision),
      body: JSON.stringify(state.workflow)
    });
    if (!isCurrentProjectContext(context)) return;
    const savedWorkflow = resourceFrom(result, "workflow");
    if (!savedWorkflow) throw new Error("Workflow 保存响应无效。");
    rememberResourceRevision("workflows", savedWorkflow.id, revisionFrom(result, savedWorkflow));
    // Do not replace edits made while this request was in flight. The stable
    // autosave loop will immediately persist that newer in-memory generation.
    if (!state.autosave.dirty.has("workflows")) state.workflow = savedWorkflow;
    const workflows = await projectApi(context.projectId, "/workflows");
    if (!isCurrentProjectContext(context)) return;
    state.workflows = workflows.workflows;
    renderAgentLibrary();
    if (!state.autosave.dirty.has("workflows")) markSaved();
    if (showToast) toast("Workflow 草稿已保存到 Studio");
    renderProjectPendingList();
    return true;
  } catch (error) {
    if (!isCurrentProjectContext(context)) return;
    $("#save-state").className = "save-state error";
    $("#save-state").innerHTML = "<i></i> 自动保存失败";
    if (isRevisionConflict(error)) showRevisionConflict("Workflow");
    else if (showToast) toast(error.message, true);
    return false;
  }
}

function renderWorkflowTestPanel(result = state.workflowTest) {
  const panel = $("#workflow-test-panel");
  if (!panel) return;
  if (result?.stale) {
    panel.className = "workflow-test-panel";
    panel.innerHTML = "<h3>Workflow 需重新测试</h3><p>画布已修改。发布或同步前会自动执行只读 Dry-run。</p>";
    return;
  }
  if (!result) { panel.classList.add("hidden"); return; }
  const passed = Boolean(result.passed ?? result.valid);
  const errors = result.errors || [];
  const warnings = result.warnings || [];
  const layers = result.layers || [];
  const handoffs = result.handoffs || result.handoffPlan || [];
  const runtime = result.runtime || {};
  const runtimeRequirements = result.runtimeRequirements || runtime.scriptActions || [];
  const runtimeUnavailable = Boolean(runtime.required && !runtime.available);
  panel.className = `workflow-test-panel ${passed ? "passed" : "failed"}`;
  panel.innerHTML = `<h3>${passed ? `${icon("check")} Workflow Dry-run 通过` : `${icon("alert")} Workflow Dry-run 未通过`}</h3><p>只验证结构、依赖、授权与交接计划，不会运行 Agent 或 Action，也不会写入项目文件。</p>${errors.length || warnings.length ? `<ul>${errors.map(item => `<li>${escapeHtml(item)}</li>`).join("")}${warnings.map(item => `<li>提醒：${escapeHtml(item)}</li>`).join("")}</ul>` : ""}${runtimeUnavailable ? "<p>Action Runtime 尚未就绪，相关脚本 Action 不能实际执行。</p>" : ""}<div class="test-meta"><span>${layers.length} 个拓扑层</span><span>${handoffs.length} 个交接</span><span>${runtimeRequirements.length} 个 Runtime 要求</span></div>`;
}

async function testWorkflow(showToast = true) {
  const loadToken = state.resourceLoadTokens.workflows;
  const workflowId = state.workflow?.id;
  let context;
  try {
    context = requireProjectContext();
    if (!await flushAutosaveKind("workflows")) throw new Error("Workflow 草稿尚未保存，无法测试当前版本。");
    if (!isCurrentProjectContext(context)
        || state.resourceLoadTokens.workflows !== loadToken
        || state.workflow?.id !== workflowId) return false;
    const workflow = collectWorkflow();
    const testedRevision = state.resourceRevisions.workflows[workflow.id];
    $("#workflow-test-panel").className = "workflow-test-panel";
    $("#workflow-test-panel").innerHTML = "<h3>正在测试 Workflow…</h3><p>执行只读 Dry-run，请稍候。</p>";
    const result = await projectApi(context.projectId, `/workflows/${encodeURIComponent(workflow.id)}/test`, { method: "POST", body: JSON.stringify(workflow) });
    const currentRevision = state.resourceRevisions.workflows[workflow.id];
    if (!isCurrentProjectContext(context)
        || state.resourceLoadTokens.workflows !== loadToken
        || state.workflow?.id !== workflowId
        || state.autosave.dirty.has("workflows")
        || Boolean(state.autosave.inFlight.workflows)
        || (testedRevision !== undefined && currentRevision !== undefined && String(testedRevision) !== String(currentRevision))) return false;
    state.workflowTest = result;
    const passed = Boolean(result.passed ?? result.valid);
    state.workflow.testStatus = passed ? "passed" : "failed";
    renderWorkflowTestPanel(result);
    if (showToast) toast(passed ? "Workflow 测试通过" : "Workflow 测试未通过", !passed);
    return passed;
  } catch (error) {
    if (state.resourceLoadTokens.workflows === loadToken
        && state.workflow?.id === workflowId
        && (!context || isCurrentProjectContext(context))) {
      state.workflowTest = { passed: false, errors: [error.message] };
      renderWorkflowTestPanel(state.workflowTest);
      if (showToast) toast(error.message, true);
    }
    return false;
  }
}

async function publishWorkflow() {
  const loadToken = state.resourceLoadTokens.workflows;
  const workflowId = state.workflow.id;
  if (!await testWorkflow(false)) {
    if (state.resourceLoadTokens.workflows === loadToken && state.workflow?.id === workflowId) toast("Workflow 测试未通过，无法发布到 Studio", true);
    return false;
  }
  if (state.resourceLoadTokens.workflows !== loadToken || state.workflow?.id !== workflowId) return false;
  return publishResource("workflows", state.workflow.id, $("#publish-workflow"));
}

// One click: a draft is first published to Studio (still a Studio-only step),
// then the write preview opens for just this resource. Project files change
// only after the person confirms there.
async function publishAndReviewSync(kind) {
  const meta = resourceMeta[kind];
  const resource = selectedResource(kind) || (kind === "workflows" ? state.workflow : null);
  if (!meta || !resource?.id) return;
  if (resourceHasDeleteIntent(resource)) {
    const legacySync = { workflows: syncWorkflow, agents: syncAgent, actions: syncAction, skills: syncSkill }[kind];
    await legacySync?.();
    return;
  }
  const loadToken = state.resourceLoadTokens[kind];
  const resourceId = resource.id;
  if (resourceStatus(resource) === "draft") {
    const published = kind === "workflows"
      ? await publishWorkflow()
      : await publishResource(kind, resourceId, $(`#publish-${meta.singular}`));
    if (!published || state.resourceLoadTokens[kind] !== loadToken) return;
  }
  await openProjectSyncPreview([{ kind: meta.singular, id: resourceId }]);
}

async function syncWorkflow() {
  const loadToken = state.resourceLoadTokens.workflows;
  const workflowId = state.workflow.id;
  if (resourceHasDeleteIntent(state.workflow)) {
    await syncResource("workflows", state.workflow.id, $("#save-workflow"));
    return;
  }
  if (!await testWorkflow(false)) {
    if (state.resourceLoadTokens.workflows === loadToken && state.workflow?.id === workflowId) toast("Workflow 测试未通过，无法同步到 Codex", true);
    return;
  }
  if (state.resourceLoadTokens.workflows !== loadToken || state.workflow?.id !== workflowId) return;
  await syncResource("workflows", state.workflow.id, $("#save-workflow"));
}

function openRunDialog() {
  const invocation = String(state.workflow.codexInvocation || `$workflow-${state.workflow.id}`).trim();
  const phrase = (state.workflow.startPhrases || [])[0];
  const command = phrase || `${invocation} 请描述你要完成的任务`;
  $("#run-command").textContent = command;
  $("#run-dialog").showModal();
}

async function copyCommand() {
  const command = $("#run-command").textContent;
  try {
    await navigator.clipboard.writeText(command);
    toast("调用方式已复制");
  } catch (_) {
    toast("浏览器没有剪贴板权限，请手动复制", true);
  }
}

async function waitForProjectSync(timeoutMs = 30000) {
  const started = Date.now();
  while (state.syncingProject) {
    if (Date.now() - started > timeoutMs) return false;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  return true;
}

async function navigateToSection(section) {
  if (!await flushAutosaves()) {
    toast("当前 Studio 草稿尚未保存，已取消切换。", true);
    return;
  }
  if (section === "projects") {
    setSection("projects");
    return;
  }
  const selected = state.projects.find(project => project.id === state.selectedProjectId);
  if (!selected?.available) {
    toast("没有可用的 Codex 项目，请先在项目库确认项目。", true);
    setSection("projects");
    return;
  }
  // A background refresh of the project already open must not swallow the click;
  // only a first import has to finish before the section has anything to show.
  if (state.syncingProject && state.project?.id !== selected.id) {
    toast("项目详情正在导入，完成后自动打开");
    if (!await waitForProjectSync()) return;
  }
  if (state.project?.id !== selected.id) {
    setSection("projects");
    toast("请先确认项目，并点击“授权并导入项目”", true);
    return;
  }
  setSection(section);
}

function setSection(section) {
  if (section !== "projects" && !state.project) return;
  if (section !== "workflow") state.resourceLoadTokens.workflows += 1;
  if (section !== "agents") state.resourceLoadTokens.agents += 1;
  if (section !== "actions") state.resourceLoadTokens.actions += 1;
  if (section !== "skills") state.resourceLoadTokens.skills += 1;
  if (section !== "ai") state.ai.returnSection = section;
  state.section = section;
  const copies = translations[state.language].sections;
  const resourceSection = activeResourceSection();
  const contextCopy = copies[section];
  renderResourceHeading(resourceSection);
  $("#context-title strong").textContent = contextCopy[3];
  $("#context-subtitle").textContent = contextCopy[4];
  $("#project-view").classList.toggle("hidden", section !== "projects");
  $("#workflow-view").classList.toggle("hidden", section !== "workflow");
  $("#agent-view").classList.toggle("hidden", section !== "agents");
  $("#actions-view").classList.toggle("hidden", section !== "actions");
  $("#skills-view").classList.toggle("hidden", section !== "skills");
  $("#ai-view").classList.toggle("hidden", section !== "ai");
  $("#workflow-inspector").classList.toggle("hidden", section !== "workflow");
  document.querySelector(".workspace").classList.toggle("no-inspector", section !== "workflow");
  $("#workflow-actions").classList.toggle("hidden", section !== "workflow");
  $("#agent-actions").classList.toggle("hidden", section !== "agents");
  $("#action-actions").classList.toggle("hidden", section !== "actions");
  $("#skill-actions").classList.toggle("hidden", section !== "skills");
  $("#resource-search").value = "";
  renderResources();
  if (section === "projects") renderSelectedProject();
  if (section === "agents" && !state.selectedAgent && state.agents.length) openAgent(state.agents[0].id);
  if (section === "actions" && !state.selectedAction && state.actions.length) openAction(state.actions[0].id);
  if (section === "actions" && !state.selectedAction && !state.actions.length) showActionEditor(actionTemplate(), "新建草稿 · 自动保存到 Studio");
  if (section === "skills" && !state.selectedSkill && state.skills.length) openSkill(state.skills[0].id);
  // The canvas only has a size once visible: fit the view (never positions) here.
  if (section === "workflow") requestAnimationFrame(() => { render(); autoFitView(); });
  if (section === "ai" && !state.ai.messages.length) startAICreation("agent", null, false);
}

function highlightRail(resourceSection) {
  document.querySelectorAll("[data-section]").forEach(button => {
    const active = button.dataset.section === resourceSection;
    button.classList.toggle("active", active);
    if (!button.classList.contains("rail-button")) return;
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
}

function renderResourceHeading(resourceSection) {
  const resourceCopy = translations[state.language].sections[resourceSection];
  const currentProject = state.projects.find(project => project.id === state.selectedProjectId);
  const aiProjectLabel = state.section === "ai"
    ? (state.project?.title || state.project?.name || currentProject?.title || "")
    : "";
  $("#resource-eyebrow").textContent = aiProjectLabel || resourceCopy[0];
  $("#resource-eyebrow").title = aiProjectLabel;
  $("#resource-title").textContent = resourceCopy[1];
  $("#resource-hint").textContent = resourceCopy[2];
  $("#add-folder-project")?.classList.toggle("hidden", resourceSection !== "projects");
  highlightRail(resourceSection);
}

// While the AI workbench is open, the rail highlight and the library follow
// the active kind tab (highlight only: rail clicks still navigate as before).
function syncAIOrientation() {
  if (state.section !== "ai") return;
  const resourceSection = aiLibrarySection();
  const previous = document.querySelector(".rail-button.active")?.dataset.section;
  if (previous && previous !== resourceSection) $("#resource-search").value = "";
  renderResourceHeading(resourceSection);
  renderResources();
}

async function openAgent(agentId) {
  const loadToken = ++state.resourceLoadTokens.agents;
  let context;
  try {
    if (state.selectedAgent?.id && state.selectedAgent.id !== agentId && !await flushAutosaveKind("agents")) {
      throw new Error("当前 Agent 草稿尚未保存，已取消切换。");
    }
    if (state.resourceLoadTokens.agents !== loadToken) return;
    context = requireProjectContext();
    const detail = await projectApi(context.projectId, `/agents/${encodeURIComponent(agentId)}`);
    if (state.resourceLoadTokens.agents !== loadToken || !isCurrentProjectContext(context)) return;
    const selectedAgent = resourceFrom(detail, "agent");
    if (!selectedAgent) throw new Error("Agent not found.");
    state.selectedAgent = selectedAgent;
    rememberResourceRevision("agents", selectedAgent.id, revisionFrom(detail, selectedAgent));
    if (state.section !== "agents") setSection("agents");
    const agent = state.selectedAgent;
    $("#agent-editor-avatar").textContent = initials(agent.name);
    $("#agent-editor-title").textContent = agent.name;
    $("#agent-editor-path").textContent = agent.entrypoint;
    $("#agent-name").value = agent.name;
    $("#agent-description").value = agent.description;
    $("#agent-model").value = ["inherit", "fast", "balanced", "deep"].includes(agent.model) ? agent.model : "inherit";
    $("#agent-instructions").value = agent.instructions || "";
    renderAgentActionPicker();
    renderAgentSkillPicker();
    renderAgentLibrary();
    updateEditorStatus("agent", agent);
  } catch (error) {
    if (state.resourceLoadTokens.agents === loadToken && (!context || isCurrentProjectContext(context))) toast(error.message, true);
  }
}

function renderAgentActionPicker() {
  const selected = new Set(state.selectedAgent?.allowedActions || []);
  $("#agent-action-picker").innerHTML = state.actions.length ? state.actions.map(action => `
    <label class="skill-choice"><input type="checkbox" value="${escapeHtml(action.id)}" ${selected.has(action.id) ? "checked" : ""}><span><strong>${escapeHtml(action.name)}</strong><small>${escapeHtml(action.executor)} · ${escapeHtml(action.id)}</small></span></label>
  `).join("") : `<div class="empty-list">项目中还没有 Action。请先进入 Action 库创建。</div>`;
}

function renderAgentSkillPicker() {
  const selected = new Set(state.selectedAgent?.skills || []);
  const assignable = state.skills.filter(skill => !skill.generated);
  $("#agent-skill-picker").innerHTML = assignable.length ? assignable.map(skill => `
    <label class="skill-choice"><input type="checkbox" value="${escapeHtml(skill.name)}" ${selected.has(skill.name) ? "checked" : ""}><span><strong>$${escapeHtml(skill.name)}</strong><small>${escapeHtml(skill.description)}</small></span></label>
  `).join("") : `<div class="empty-list">项目中还没有可关联的手写 Skill。</div>`;
}

function collectAgentDraft() {
  if (!state.selectedAgent) return null;
  return {
    ...state.selectedAgent,
    name: $("#agent-name").value,
    description: $("#agent-description").value,
    model: $("#agent-model").value,
    instructions: $("#agent-instructions").value,
    allowedActions: [...document.querySelectorAll("#agent-action-picker input:checked")].map(input => input.value),
    skills: [...document.querySelectorAll("#agent-skill-picker input:checked")].map(input => input.value)
  };
}

async function persistAgentDraft(showToast = false) {
  if (!state.selectedAgent) return false;
  let context;
  try {
    context = requireProjectContext();
  } catch (error) {
    toast(error.message, true);
    return false;
  }
  const agentId = state.selectedAgent.id;
  const payload = collectAgentDraft();
  try {
    const result = await projectApi(context.projectId, `/agents/${encodeURIComponent(agentId)}`, {
      method: "PUT",
      headers: revisionHeaders(state.resourceRevisions.agents[agentId]),
      body: JSON.stringify(payload)
    });
    if (!isCurrentProjectContext(context)) return true;
    const savedAgent = resourceFrom(result, "agent");
    if (!savedAgent) throw new Error("Agent 保存响应无效。");
    rememberResourceRevision("agents", savedAgent.id, revisionFrom(result, savedAgent));
    if (!state.autosave.dirty.has("agents")) state.selectedAgent = savedAgent;
    const [agents, skills] = await Promise.all([
      projectApi(context.projectId, "/agents"),
      projectApi(context.projectId, "/skills")
    ]);
    if (!isCurrentProjectContext(context)) return true;
    state.agents = agents.agents;
    state.skills = skills.skills;
    renderResources();
    if (!state.autosave.dirty.has("agents")) updateEditorStatus("agent", savedAgent);
    renderProjectPendingList();
    if (showToast) toast("Agent 草稿已保存到 Studio");
    return true;
  } catch (error) {
    if (!isCurrentProjectContext(context)) return false;
    if (isRevisionConflict(error)) showRevisionConflict("Agent");
    else toast(error.message, true);
    return false;
  }
}

function actionTemplate(kind = "blank") {
  const base = {
    schemaVersion: 1,
    id: "new-action",
    name: state.language === "zh" ? "新建 Action" : "New Action",
    description: state.language === "zh" ? "描述这个可重复执行的操作。" : "Describe this repeatable operation.",
    executor: "api",
    inputs: {},
    steps: [],
    success: {},
    outputs: {},
    timeoutSeconds: 60,
    errorHandling: { strategy: "stop", retries: 0 },
    credentialRefs: []
  };
  if (kind === "api") return {
    ...base,
    schemaVersion: 2,
    id: "api-request",
    name: "API Request",
    description: "通过 HTTP API 完成一个确定性操作。",
    executor: "api",
    inputs: { payload: "object" },
    connection: { kind: "http", endpoint: "https://api.example.com", healthCheck: { method: "GET", path: "/health", expectedStatuses: [200, 204] } },
    steps: [{ type: "http.request", method: "POST", path: "/v1/resource", body: "{{inputs.payload}}" }],
    success: { statusCodes: [200, 201, 204] },
    outputs: { response: "object" },
    credentialRefs: ["api-credential"]
  };
  if (kind === "mcp") return {
    ...base,
    schemaVersion: 2,
    id: "mcp-tool-call",
    name: "MCP Tool Call",
    description: "通过 Streamable HTTP 调用 MCP Server 中的工具。",
    executor: "mcp",
    inputs: { arguments: "object" },
    connection: { kind: "mcp", transport: "streamable-http", endpoint: "http://127.0.0.1:3000/mcp" },
    steps: [{ type: "mcp.call_tool", tool: "replace-with-tool-name", arguments: "{{inputs.arguments}}" }],
    success: { resultReceived: true },
    outputs: { result: "object" },
    credentialRefs: []
  };
  return base;
}

function resetActionConnectionStatus(message = tr("connectionNotChecked")) {
  state.actionConnection.sequence += 1;
  if (state.actionConnection.controller) state.actionConnection.controller.abort();
  state.actionConnection.controller = null;
  const card = $("#action-connection-status").closest(".action-connection-card");
  card.classList.remove("checking", "connected", "failed");
  $("#action-connection-status").textContent = message;
  $("#check-action-connection").disabled = false;
}

function uniqueActionId(baseId) {
  const used = new Set(state.actions.map(action => action.id));
  if (!used.has(baseId)) return baseId;
  let suffix = 2;
  while (used.has(`${baseId}-${suffix}`)) suffix += 1;
  return `${baseId}-${suffix}`;
}

function applyActionPreset(kind) {
  const current = $("#action-json").value.trim();
  const untouchedBlank = current === JSON.stringify(actionTemplate(), null, 2);
  if (current && !untouchedBlank && !window.confirm("应用预设会替换当前 Action JSON，是否继续？")) return;
  state.resourceLoadTokens.actions += 1;
  const draft = actionTemplate(kind);
  draft.id = uniqueActionId(draft.id);
  state.selectedAction = draft;
  showActionEditor(draft, kind === "mcp" ? "MCP 预设草稿 · 尚未保存" : "API 预设草稿 · 尚未保存");
  $("#action-json").focus();
}

async function checkActionConnection() {
  if (!state.selectedAction) {
    toast("请先打开或新建一个 Action。", true);
    return;
  }
  let action;
  let context;
  try {
    action = JSON.parse($("#action-json").value);
    context = requireProjectContext();
  } catch (error) {
    toast(error instanceof SyntaxError ? `Action JSON 无效：${error.message}` : error.message, true);
    return;
  }
  const card = $("#action-connection-status").closest(".action-connection-card");
  const button = $("#check-action-connection");
  if (state.actionConnection.controller) state.actionConnection.controller.abort();
  const controller = new AbortController();
  const sequence = state.actionConnection.sequence + 1;
  state.actionConnection = { sequence, controller };
  card.classList.remove("connected", "failed");
  card.classList.add("checking");
  button.disabled = true;
  $("#action-connection-status").textContent = "正在执行只读联通诊断…";
  try {
    const result = await projectApi(context.projectId, "/actions/check-connection", { method: "POST", signal: controller.signal, body: JSON.stringify(action) });
    if (state.actionConnection.sequence !== sequence || state.actionConnection.controller !== controller || !isCurrentProjectContext(context)) return;
    card.classList.remove("checking");
    card.classList.add(result.connected ? "connected" : (result.reachable ? "checking" : "failed"));
    const timing = Number.isFinite(result.durationMs) ? ` · ${result.durationMs} ms` : "";
    $("#action-connection-status").textContent = `${result.message}${timing}`;
  } catch (error) {
    if (state.actionConnection.sequence !== sequence || error.name === "AbortError" || !isCurrentProjectContext(context)) return;
    card.classList.remove("checking");
    card.classList.add("failed");
    $("#action-connection-status").textContent = `检测失败：${error.message}`;
  } finally {
    if (state.actionConnection.sequence === sequence && state.actionConnection.controller === controller) {
      state.actionConnection.controller = null;
      button.disabled = false;
    }
  }
}

function showActionEditor(action, path = "尚未保存", persistedId = null) {
  state.selectedAction = action;
  state.actionEditorSourceId = persistedId;
  $("#action-editor-title").textContent = action.name || action.id || "未命名 Action";
  $("#action-editor-path").textContent = path;
  $("#action-json").value = JSON.stringify(action, null, 2);
  renderActionJsonError();
  resetActionConnectionStatus();
  renderActionLibrary();
  updateEditorStatus("action", action);
  renderActionForm();
}

// ---- Structured Action form: a two-way view onto the Action JSON (the JSON
// textarea stays the source of truth for autosave and connection checks).
const actionFormStepTypes = { script: "process.exec", api: "http.request", mcp: "mcp.call_tool" };

function credentialEnvName(reference) {
  const name = String(reference).replace(/[^A-Za-z0-9]+/g, "_").replace(/^_+|_+$/g, "").toUpperCase();
  if (!name) return "ACTION_CREDENTIAL";
  return /^\d/.test(name) ? `CRED_${name}` : name;
}

function readActionJson() {
  try {
    const value = JSON.parse($("#action-json").value);
    return value && typeof value === "object" && !Array.isArray(value) ? value : null;
  } catch (_) {
    return null;
  }
}

// Autosave silently skips unparsable JSON, so say why right where it is being edited.
function renderActionJsonError() {
  const note = $("#action-json-error");
  if (!note) return;
  let message = "";
  try {
    const value = JSON.parse($("#action-json").value);
    if (!value || typeof value !== "object" || Array.isArray(value)) message = "Action JSON 必须是一个对象。";
  } catch (error) {
    message = `Action JSON 无效，修正前不会自动保存：${error.message}`;
  }
  note.textContent = message;
  note.classList.toggle("hidden", !message);
}

function formatFieldLines(fields) {
  return Object.entries(fields && typeof fields === "object" ? fields : {}).map(([key, type]) => `${key}: ${typeof type === "string" ? type : JSON.stringify(type)}`).join("\n");
}

function parseFieldLines(text) {
  const fields = {};
  String(text || "").split("\n").forEach(line => {
    const [rawKey, ...rest] = line.split(":");
    const key = rawKey.trim();
    if (key) fields[key] = rest.join(":").trim() || "string";
  });
  return fields;
}

function parseTemplateValue(text) {
  const value = String(text || "").trim();
  if (!value) return "";
  if (/^[[{]/.test(value)) {
    try { return JSON.parse(value); } catch (_) { /* keep as a template string */ }
  }
  return value;
}

function formatTemplateValue(value) {
  if (value === undefined || value === null) return "";
  return typeof value === "string" ? value : JSON.stringify(value);
}

function actionFormStepEditable(action) {
  const steps = Array.isArray(action.steps) ? action.steps : [];
  if (!steps.length) return true;
  const expected = actionFormStepTypes[action.executor];
  return steps.length === 1 && typeof steps[0] === "object" && expected && steps[0].type === expected;
}

function setActionMode(mode) {
  const formMode = mode !== "json";
  state.actionEditorMode = formMode ? "form" : "json";
  try { localStorage.setItem("workflow-studio-action-mode", state.actionEditorMode); } catch (_) { /* optional */ }
  $("#action-form")?.classList.toggle("hidden", !formMode);
  $("#action-json-pane")?.classList.toggle("hidden", formMode);
  [["#action-mode-form", formMode], ["#action-mode-json", !formMode]].forEach(([selector, active]) => {
    $(selector)?.classList.toggle("active", active);
    $(selector)?.setAttribute("aria-selected", active ? "true" : "false");
  });
  if (formMode) renderActionForm();
}

function renderActionForm() {
  const form = $("#action-form");
  if (!form) return;
  const action = readActionJson();
  const note = $("#af-note");
  const controls = [...form.querySelectorAll("input, select, textarea")];
  if (!action) {
    note.textContent = "Action JSON 目前无法解析，请切换到 JSON 修正后再用表单编辑。";
    note.classList.remove("hidden");
    controls.forEach(control => { control.disabled = true; });
    return;
  }
  controls.forEach(control => { control.disabled = false; });
  const executor = ["script", "api", "mcp"].includes(action.executor) ? action.executor : "api";
  const step = (Array.isArray(action.steps) && typeof action.steps[0] === "object" && action.steps[0]) || {};
  const connection = action.connection && typeof action.connection === "object" ? action.connection : {};
  const editable = actionFormStepEditable(action);
  const set = (selector, value) => { const element = $(selector); if (element && document.activeElement !== element) element.value = value; };
  set("#af-name", action.name || "");
  set("#af-description", action.description || "");
  set("#af-executor", executor);
  set("#af-command", step.command || "");
  set("#af-args", Array.isArray(step.args) ? step.args.join("\n") : "");
  set("#af-endpoint", connection.kind === "http" ? connection.endpoint || "" : "");
  set("#af-method", String(step.method || "GET").toUpperCase());
  set("#af-path", step.path || "");
  set("#af-headers", step.headers && typeof step.headers === "object" ? Object.entries(step.headers).map(([key, value]) => `${key}: ${value}`).join("\n") : "");
  set("#af-body", formatTemplateValue(step.body));
  set("#af-mcp-endpoint", connection.kind === "mcp" ? connection.endpoint || "" : "");
  set("#af-tool", step.tool || "");
  set("#af-arguments", formatTemplateValue(step.arguments));
  set("#af-inputs", formatFieldLines(action.inputs));
  set("#af-outputs", formatFieldLines(action.outputs));
  set("#af-timeout", action.timeoutSeconds ?? 60);
  set("#af-retries", action.errorHandling?.retries ?? 0);
  set("#af-strategy", action.errorHandling?.strategy === "continue" ? "continue" : "stop");
  set("#af-credentials", (action.credentialRefs || []).join(", "));
  const success = action.success || {};
  const successLabel = { script: "成功退出码", api: "成功状态码（逗号分隔）", mcp: "成功条件" }[executor];
  $("#af-success-label").textContent = successLabel;
  $("#af-success-wrap").classList.toggle("hidden", executor === "mcp");
  set("#af-success", executor === "script" ? String(success.exitCode ?? 0) : (success.statusCodes || [200]).join(", "));
  const stdin = $("#af-stdin");
  const inputNames = Object.keys(action.inputs || {});
  const stdinMatch = /^\{\{\s*inputs\.([\w-]+)\s*\}\}$/.exec(String(step.stdin || "").trim());
  stdin.innerHTML = `<option value="">不传入</option>${inputNames.map(name => `<option value="${escapeHtml(name)}">输入 ${escapeHtml(name)}</option>`).join("")}`;
  stdin.value = stdinMatch && inputNames.includes(stdinMatch[1]) ? stdinMatch[1] : "";
  ["script", "api", "mcp"].forEach(kind => {
    const group = $(`#af-${kind}`);
    group.classList.toggle("hidden", kind !== executor);
    group.disabled = !editable;
  });
  const stdio = executor === "mcp" && connection.transport === "stdio";
  if (stdio) $("#af-mcp-endpoint").disabled = true;
  const messages = [];
  if (!editable) messages.push("这个 Action 有多个或特殊的执行步骤，步骤只能在 JSON 中编辑；其他字段仍可在这里修改。");
  if (stdio) messages.push("这个 MCP 通过本地命令（stdio）连接，连接方式请在 JSON 中编辑。");
  note.textContent = messages.join(" ");
  note.classList.toggle("hidden", !messages.length);
  const references = action.credentialRefs || [];
  $("#af-env-hint").textContent = references.length
    ? `同步后由 Codex 按这里的声明执行；密钥从环境变量 ${references.map(item => credentialEnvName(item)).join("、")} 读取，不写进 Action。`
    : "同步后由 Codex 按这里的声明执行；需要密钥时填写凭据引用，密钥只从环境变量读取，不写进 Action。";
}

function actionFromForm(base) {
  const action = { ...base };
  const value = selector => $(selector).value;
  const previousExecutor = base.executor;
  action.name = value("#af-name").trim();
  action.description = value("#af-description").trim();
  action.executor = value("#af-executor");
  action.inputs = parseFieldLines(value("#af-inputs"));
  action.outputs = parseFieldLines(value("#af-outputs"));
  action.timeoutSeconds = Math.min(3600, Math.max(1, parseInt(value("#af-timeout"), 10) || 60));
  action.errorHandling = { ...(base.errorHandling || {}), strategy: value("#af-strategy"), retries: Math.min(10, Math.max(0, parseInt(value("#af-retries"), 10) || 0)) };
  action.credentialRefs = value("#af-credentials").split(/[,，、\s]+/).map(item => item.trim()).filter(Boolean);
  const executorChanged = previousExecutor !== action.executor;
  if (executorChanged || actionFormStepEditable(base)) {
    const previous = (!executorChanged && Array.isArray(base.steps) && typeof base.steps[0] === "object" && base.steps[0]) || {};
    if (action.executor === "script") {
      const stdin = value("#af-stdin");
      const step = { ...previous, type: "process.exec", command: value("#af-command").trim(), args: value("#af-args").split("\n").map(item => item.trim()).filter(Boolean) };
      if (stdin) step.stdin = `{{inputs.${stdin}}}`; else delete step.stdin;
      action.steps = [step];
      delete action.connection;
      action.success = { exitCode: parseInt(value("#af-success"), 10) || 0 };
    } else if (action.executor === "api") {
      const headers = {};
      value("#af-headers").split("\n").forEach(line => {
        const index = line.indexOf(":");
        if (index > 0) headers[line.slice(0, index).trim()] = line.slice(index + 1).trim();
      });
      const step = { ...previous, type: "http.request", method: value("#af-method"), path: value("#af-path").trim() || "/" };
      if (Object.keys(headers).length) step.headers = headers; else delete step.headers;
      const body = parseTemplateValue(value("#af-body"));
      if (body !== "") step.body = body; else delete step.body;
      action.steps = [step];
      const endpoint = value("#af-endpoint").trim();
      if (endpoint) action.connection = { ...(base.connection?.kind === "http" ? base.connection : {}), kind: "http", endpoint };
      else delete action.connection;
      const codes = value("#af-success").split(/[,，\s]+/).map(item => parseInt(item, 10)).filter(code => code >= 100 && code <= 599);
      action.success = { statusCodes: codes.length ? codes : [200] };
    } else {
      const step = { ...previous, type: "mcp.call_tool", tool: value("#af-tool").trim(), arguments: parseTemplateValue(value("#af-arguments")) || {} };
      action.steps = [step];
      if (base.connection?.transport === "stdio" && !executorChanged) action.connection = base.connection;
      else {
        const endpoint = value("#af-mcp-endpoint").trim();
        if (endpoint) action.connection = { kind: "mcp", transport: "streamable-http", endpoint };
        else delete action.connection;
      }
      action.success = { resultReceived: true };
    }
  }
  action.schemaVersion = action.connection ? 2 : 1;
  return action;
}

function writeActionFromForm() {
  const base = readActionJson();
  if (!base) return;
  const action = actionFromForm(base);
  $("#action-json").value = JSON.stringify(action, null, 2);
  $("#action-editor-title").textContent = action.name || action.id || "未命名 Action";
  $("#action-json").dispatchEvent(new Event("input", { bubbles: true }));
  renderActionForm();
}

async function openAction(actionId) {
  const loadToken = ++state.resourceLoadTokens.actions;
  let context;
  try {
    if (state.selectedAction?.id && state.selectedAction.id !== actionId && !await flushAutosaveKind("actions")) {
      throw new Error("当前 Action 草稿尚未保存，已取消切换。");
    }
    if (state.resourceLoadTokens.actions !== loadToken) return;
    context = requireProjectContext();
    const result = await projectApi(context.projectId, `/actions/${encodeURIComponent(actionId)}`);
    if (state.resourceLoadTokens.actions !== loadToken || !isCurrentProjectContext(context)) return;
    const selectedAction = resourceFrom(result, "action");
    if (!selectedAction) throw new Error("Action not found.");
    state.selectedAction = selectedAction;
    rememberResourceRevision("actions", selectedAction.id, revisionFrom(result, selectedAction));
    if (state.section !== "actions") setSection("actions");
    const summary = state.actions.find(item => item.id === actionId);
    showActionEditor(selectedAction, summary?.path || `.workflow-studio/actions/${actionId}.json`, selectedAction.id);
  } catch (error) {
    if (state.resourceLoadTokens.actions === loadToken && (!context || isCurrentProjectContext(context))) toast(error.message, true);
  }
}

async function newAction() {
  const loadToken = ++state.resourceLoadTokens.actions;
  if (state.selectedAction && !await flushAutosaveKind("actions")) {
    if (state.resourceLoadTokens.actions === loadToken) toast("当前 Action 草稿尚未保存，已取消新建。", true);
    return;
  }
  if (state.resourceLoadTokens.actions !== loadToken) return;
  const draft = actionTemplate();
  draft.id = uniqueActionId(draft.id);
  draft.status = "draft";
  state.selectedAction = draft;
  if (state.section !== "actions") setSection("actions");
  showActionEditor(draft, "新建草稿 · 自动保存到 Studio");
  $("#action-json").focus();
}

async function persistActionDraft(showToast = false) {
  if (!state.selectedAction) {
    toast("请先打开或新建一个 Action。", true);
    return;
  }
  let action;
  let context;
  try {
    action = JSON.parse($("#action-json").value);
    context = requireProjectContext();
  } catch (error) {
    if (showToast) toast(error instanceof SyntaxError ? `Action JSON 无效：${error.message}` : error.message, true);
    return false;
  }
  if (!action || typeof action !== "object" || Array.isArray(action)) {
    if (showToast) toast("Action JSON 必须是一个对象", true);
    return false;
  }
  const actionId = slugify(action.id || action.name || "action");
  const allowOverwrite = state.actionEditorSourceId === actionId;
  let revision = state.resourceRevisions.actions[actionId];
  try {
    if (state.actions.some(item => item.id === actionId) && (revision === undefined || revision === null || revision === "")) {
      // markEditorDraft lists a brand-new draft before its first save, so a 404 here means "create".
      const detail = await projectApi(context.projectId, `/actions/${encodeURIComponent(actionId)}`).catch(error => {
        if (error.status === 404) return null;
        throw error;
      });
      if (!isCurrentProjectContext(context)) return;
      if (detail) {
        revision = detail.revision;
        rememberResourceRevision("actions", actionId, revision);
      }
    }
    const persist = overwrite => projectApi(context.projectId, `/actions/${encodeURIComponent(actionId)}`, {
      method: "PUT",
      headers: revisionHeaders(revision, { "X-Workflow-Studio-Allow-Overwrite": overwrite ? "true" : "false" }),
      body: JSON.stringify(action)
    });
    const result = await persist(allowOverwrite);
    if (!isCurrentProjectContext(context)) return;
    const savedAction = resourceFrom(result, "action");
    if (!savedAction) throw new Error("Action 保存响应无效。");
    rememberResourceRevision("actions", savedAction.id, revisionFrom(result, savedAction));
    const actions = await projectApi(context.projectId, "/actions");
    if (!isCurrentProjectContext(context)) return;
    state.actions = actions.actions;
    if (!state.autosave.dirty.has("actions")) {
      state.selectedAction = savedAction;
      showActionEditor(savedAction, savedAction.path || `Studio 草稿 · ${savedAction.id}`, savedAction.id);
    } else {
      renderActionLibrary();
    }
    renderProjectPendingList();
    if (showToast) toast("Action 草稿已保存到 Studio；现在可以在 Agent 中授予调用权限");
    return true;
  } catch (error) {
    if (!isCurrentProjectContext(context)) return;
    if (isRevisionConflict(error)) showRevisionConflict("Action");
    else toast(error.message, true);
    return false;
  }
}

function jobStatus(job) {
  return normalizeTestStatus(job?.status || (job?.passed === true ? "passed" : job?.passed === false ? "failed" : "untested"));
}

function agentIdFromJob(job) {
  return job?.agentId || job?.resourceId || job?.agent?.id || "";
}

function agentJobMatchesCurrentDraft(job) {
  const agentId = agentIdFromJob(job);
  if (!agentId) return false;
  const summary = state.agents.find(agent => agent.id === agentId);
  const resource = state.selectedAgent?.id === agentId ? state.selectedAgent : summary;
  if (!resource) return true;
  const testedRevision = job?.resourceRevision ?? job?.testedRevision;
  const currentRevision = resource.studioRevision ?? state.resourceRevisions.agents[agentId];
  if (testedRevision !== undefined && testedRevision !== null && currentRevision !== undefined && currentRevision !== null
      && String(testedRevision) !== String(currentRevision)) return false;
  if (state.selectedAgent?.id === agentId
      && (state.autosave.dirty.has("agents") || Boolean(state.autosave.inFlight.agents))) return false;
  return true;
}

function rememberAgentJob(job) {
  const jobId = job?.jobId || job?.id;
  if (jobId) state.agentTests.jobs.set(jobId, job);
  const agentId = agentIdFromJob(job);
  if (!agentId) return false;
  if (!agentJobMatchesCurrentDraft(job)) return false;
  const status = jobStatus(job);
  const summary = state.agents.find(agent => agent.id === agentId);
  if (summary) summary.testStatus = status;
  if (state.selectedAgent?.id === agentId) {
    state.selectedAgent.testStatus = status;
    updateEditorStatus("agent", state.selectedAgent);
  }
  return true;
}

function notifyAgentJob(job) {
  const jobId = job?.jobId || job?.id;
  const status = jobStatus(job);
  if (!jobId || !["passed", "failed", "interrupted"].includes(status) || state.agentTests.notified.has(jobId)) return;
  state.agentTests.notified.add(jobId);
  while (state.agentTests.notified.size > 200) state.agentTests.notified.delete(state.agentTests.notified.values().next().value);
  persistStoredSet("workflow-studio-notified-agent-tests", state.agentTests.notified);
  const agent = state.agents.find(item => item.id === agentIdFromJob(job));
  if (!agentJobMatchesCurrentDraft(job)) {
    toast(`${agent?.name || "Agent"} 旧版本测试已完成，当前草稿需重测`);
    return;
  }
  toast(status === "passed" ? `${agent?.name || "Agent"} 测试通过` : `${agent?.name || "Agent"} 测试未通过`, status !== "passed");
}

async function acknowledgeAgentJob(context, job) {
  const jobId = job?.jobId || job?.id;
  if (!jobId || !isCurrentProjectContext(context)) return;
  try {
    await projectApi(
      context.projectId,
      `/agent-tests/${encodeURIComponent(jobId)}/seen`,
      { method: "POST", body: "{}" }
    );
  } catch (_) {
    // Leave the persisted result unseen so a later poll or page reopen retries it.
  }
}

async function pollAgentTests(silent = false) {
  if (state.agentTests.polling || !state.project) return;
  const context = captureProjectContext();
  let running = false;
  state.agentTests.polling = true;
  try {
    const payload = await projectApi(context.projectId, "/agent-tests");
    if (!isCurrentProjectContext(context)) return;
    const jobs = payload.jobs || payload.tests || (payload.job ? [payload.job] : []);
    jobs.forEach(rememberAgentJob);
    renderAgentLibrary();
    running = jobs.some(job => jobStatus(job) === "running");
    const unseenPayload = await projectApi(context.projectId, "/agent-tests?unseen=1");
    if (!isCurrentProjectContext(context)) return;
    const unseenJobs = unseenPayload.jobs || unseenPayload.tests || (unseenPayload.job ? [unseenPayload.job] : []);
    for (const job of unseenJobs) {
      if (!isCurrentProjectContext(context)) return;
      rememberAgentJob(job);
      notifyAgentJob(job);
      await acknowledgeAgentJob(context, job);
    }
  } catch (error) {
    if (!silent && isCurrentProjectContext(context)) toast(`无法读取 Agent 测试状态：${error.message}`, true);
  } finally {
    state.agentTests.polling = false;
    clearTimeout(state.agentTests.timer);
    state.agentTests.timer = running && isCurrentProjectContext(context)
      ? setTimeout(() => { void pollAgentTests(false); }, 1200)
      : null;
  }
}

async function testAgent() {
  if (!state.selectedAgent) return;
  const loadToken = state.resourceLoadTokens.agents;
  const agentId = state.selectedAgent.id;
  let context;
  try {
    context = requireProjectContext();
    if (!await flushAutosaveKind("agents")) throw new Error("Agent 草稿尚未保存，暂时不能测试。");
    if (!isCurrentProjectContext(context)
        || state.resourceLoadTokens.agents !== loadToken
        || state.selectedAgent?.id !== agentId) return;
    const tutorialInput = state.onboarding.active && context.projectId === tutorialProjectId
      ? state.onboarding.status?.sampleTask
      : "";
    const result = await projectApi(context.projectId, "/agent-tests", { method: "POST", body: JSON.stringify({ agentId, input: tutorialInput }) });
    if (!isCurrentProjectContext(context)
        || state.resourceLoadTokens.agents !== loadToken
        || state.selectedAgent?.id !== agentId) return;
    const job = result.job || result;
    rememberAgentJob({ ...job, agentId, status: job.status || "queued" });
    toast("Agent 测试已在后台开始");
    clearTimeout(state.agentTests.timer);
    state.agentTests.timer = setTimeout(() => { void pollAgentTests(false); }, 500);
  } catch (error) {
    if (!context || isCurrentProjectContext(context)) toast(error.message, true);
  }
}

async function openSkill(skillId) {
  const loadToken = ++state.resourceLoadTokens.skills;
  let context;
  try {
    if (state.selectedSkill?.id && state.selectedSkill.id !== skillId && !await flushAutosaveKind("skills")) {
      throw new Error("当前 Skill 草稿尚未保存，已取消切换。");
    }
    if (state.resourceLoadTokens.skills !== loadToken) return;
    context = requireProjectContext();
    const detail = await projectApi(context.projectId, `/skills/${encodeURIComponent(skillId)}`);
    if (state.resourceLoadTokens.skills !== loadToken || !isCurrentProjectContext(context)) return;
    const selectedSkill = resourceFrom(detail, "skill");
    if (!selectedSkill) throw new Error("Skill not found.");
    state.selectedSkill = selectedSkill;
    rememberResourceRevision("skills", selectedSkill.id, revisionFrom(detail, selectedSkill));
    if (state.section !== "skills") setSection("skills");
    const skill = state.selectedSkill;
    $("#skill-editor-title").textContent = skill.name;
    $("#skill-editor-path").textContent = skill.path;
    $("#skill-name").value = skill.name;
    $("#skill-description").value = skill.description;
    $("#skill-instructions").value = skill.instructions;
    $("#skill-type").value = skill.generated ? "Generated project skill" : "Project skill";
    renderSkillLibrary();
    updateEditorStatus("skill", skill);
  } catch (error) {
    if (state.resourceLoadTokens.skills === loadToken && (!context || isCurrentProjectContext(context))) toast(error.message, true);
  }
}

async function persistSkillDraft(showToast = false) {
  if (!state.selectedSkill) return;
  let context;
  try {
    context = requireProjectContext();
  } catch (error) {
    toast(error.message, true);
    return;
  }
  const skillId = state.selectedSkill.id;
  const payload = { name: $("#skill-name").value, description: $("#skill-description").value, instructions: $("#skill-instructions").value };
  try {
    const result = await projectApi(context.projectId, `/skills/${encodeURIComponent(skillId)}`, {
      method: "PUT",
      headers: revisionHeaders(state.resourceRevisions.skills[skillId]),
      body: JSON.stringify(payload)
    });
    if (!isCurrentProjectContext(context)) return;
    const savedSkill = resourceFrom(result, "skill");
    if (!savedSkill) throw new Error("Skill 保存响应无效。");
    rememberResourceRevision("skills", savedSkill.id, revisionFrom(result, savedSkill));
    if (!state.autosave.dirty.has("skills")) state.selectedSkill = savedSkill;
    const skills = await projectApi(context.projectId, "/skills");
    if (!isCurrentProjectContext(context)) return;
    state.skills = skills.skills;
    renderSkillLibrary();
    if (!state.autosave.dirty.has("skills")) updateEditorStatus("skill", savedSkill);
    renderProjectPendingList();
    if (showToast) toast("Skill 草稿已保存到 Studio");
    return true;
  } catch (error) {
    if (!isCurrentProjectContext(context)) return;
    if (isRevisionConflict(error)) showRevisionConflict("Skill");
    else toast(error.message, true);
    return false;
  }
}

const resourceMeta = {
  agents: { singular: "agent", label: "Agent" }, actions: { singular: "action", label: "Action" },
  skills: { singular: "skill", label: "Skill" }, workflows: { singular: "workflow", label: "Workflow" }
};

async function refreshStudioResources(context = captureProjectContext()) {
  if (!context) return false;
  const [agents, actions, skills, workflows] = await Promise.all([
    projectApi(context.projectId, "/agents"), projectApi(context.projectId, "/actions"),
    projectApi(context.projectId, "/skills"), projectApi(context.projectId, "/workflows")
  ]);
  if (!isCurrentProjectContext(context)) return false;
  state.agents = agents.agents || [];
  state.actions = actions.actions || [];
  state.skills = skills.skills || [];
  state.workflows = workflows.workflows || [];
  state.selectedAgent = mergeSummaryStatus(state.selectedAgent, state.agents);
  state.selectedAction = mergeSummaryStatus(state.selectedAction, state.actions);
  state.selectedSkill = mergeSummaryStatus(state.selectedSkill, state.skills);
  state.workflow = mergeSummaryStatus(state.workflow, state.workflows) || state.workflow;
  renderResources();
  renderSelectedProject();
  if (state.selectedAgent) updateEditorStatus("agent", state.selectedAgent);
  if (state.selectedAction) updateEditorStatus("action", state.selectedAction);
  if (state.selectedSkill) updateEditorStatus("skill", state.selectedSkill);
  updateResourceActionButtons("workflows", state.workflow);
  return true;
}

async function publishResource(kind, resourceId, button = null) {
  const meta = resourceMeta[kind];
  const loadToken = state.resourceLoadTokens[kind];
  let context;
  if (!meta || !resourceId) return false;
  try {
    context = requireProjectContext();
    if (!await flushAutosaveKind(kind)) throw new Error(`${meta.label} 草稿尚未保存，无法发布。`);
    if (!isCurrentProjectContext(context) || state.resourceLoadTokens[kind] !== loadToken) {
      throw new Error(`${meta.label} 已切换，请确认当前资源后重试。`);
    }
    resourceId = selectedResource(kind)?.id || resourceId;
    if (button) { button.disabled = true; button.textContent = "正在发布…"; }
    const current = selectedResource(kind);
    const revision = current?.studioRevision ?? state.resourceRevisions[kind][resourceId];
    const result = await projectApi(context.projectId, `/${kind}/${encodeURIComponent(resourceId)}/publish`, {
      method: "POST",
      headers: revisionHeaders(revision),
      body: "{}"
    });
    if (!isCurrentProjectContext(context)) return false;
    const resource = resourceFrom(result, meta.singular);
    if (resource) {
      updateSummaryResource(kind, resource);
      rememberResourceRevision(kind, resource.id, revisionFrom(result, resource));
    } else {
      const current = selectedResource(kind);
      if (current) current.status = result.status || result.resourceStatus || "ready";
    }
    await refreshStudioResources(context);
    toast(`${meta.label} 已发布到 Studio，尚未修改 Codex 文件`);
    return true;
  } catch (error) {
    if (!context || isCurrentProjectContext(context)) toast(error.message, true);
    return false;
  } finally {
    if (button) { button.disabled = false; button.textContent = tr("publishStudio"); }
  }
}

async function syncResource(kind, resourceId, button = null) {
  const meta = resourceMeta[kind];
  const loadToken = state.resourceLoadTokens[kind];
  let context;
  if (!meta || !resourceId) return false;
  try {
    context = requireProjectContext();
    if (!await flushAutosaveKind(kind)) throw new Error(`${meta.label} 草稿尚未保存，无法同步。`);
    if (!isCurrentProjectContext(context) || state.resourceLoadTokens[kind] !== loadToken) {
      throw new Error(`${meta.label} 已切换，请确认当前资源后重试。`);
    }
    resourceId = selectedResource(kind)?.id || resourceId;
    const current = selectedResource(kind);
    const deleting = resourceHasDeleteIntent(current);
    if (kind === "agents" && !deleting) {
      await pollAgentTests(true);
      if (!isCurrentProjectContext(context)
          || state.resourceLoadTokens[kind] !== loadToken
          || selectedResource(kind)?.id !== resourceId) return false;
      const latestAgent = state.agents.find(agent => agent.id === resourceId) || current;
      if (normalizeTestStatus(latestAgent?.testStatus) !== "passed") throw new Error("当前 Agent 草稿必须测试通过后才能同步到 Codex。");
    }
    if (deleting && !window.confirm(`确认从 Codex 项目删除这个 ${meta.label} 的已记录文件吗？Studio 会保留可恢复记录。`)) return false;
    if (button) { button.disabled = true; button.textContent = "正在同步…"; }
    const revision = current?.studioRevision ?? state.resourceRevisions[kind][resourceId];
    const result = await projectApi(context.projectId, `/${kind}/${encodeURIComponent(resourceId)}/sync`, {
      method: "POST",
      headers: revisionHeaders(revision),
      body: JSON.stringify({ confirmDelete: deleting })
    });
    if (!isCurrentProjectContext(context)) return false;
    const item = Array.isArray(result.results) ? result.results[0] : result;
    if (!item || item.status === "failed" || item.status === "blocked" || (result.failed || []).length || (result.blocked || []).length) {
      await refreshStudioResources(context);
      const reasons = (item?.blockedReasons || []).map(reason => reason.message || reason.code).filter(Boolean);
      throw new Error(item?.error || reasons.join("；") || `${meta.label} 同步未完成。`);
    }
    const resource = item.resource || resourceFrom(result, meta.singular);
    if (resource) {
      updateSummaryResource(kind, resource);
      rememberResourceRevision(kind, resource.id, revisionFrom(result, resource));
    }
    await refreshStudioResources(context);
    const files = item.syncedFiles || item.files || result.syncedFiles || result.files || [];
    toast(`${meta.label} 已同步到 Codex${files.length ? `（${files.length} 个文件）` : ""}`);
    return true;
  } catch (error) {
    if (!context || isCurrentProjectContext(context)) toast(error.message, true);
    return false;
  } finally {
    if (button) { button.disabled = false; button.textContent = tr("syncCodex"); }
  }
}

function publishAgent() { return state.selectedAgent && publishResource("agents", state.selectedAgent.id, $("#publish-agent")); }
function publishAction() { return state.selectedAction && publishResource("actions", state.selectedAction.id, $("#publish-action")); }
function publishSkill() { return state.selectedSkill && publishResource("skills", state.selectedSkill.id, $("#publish-skill")); }
function syncAgent() { return state.selectedAgent && syncResource("agents", state.selectedAgent.id, $("#save-agent")); }
function syncAction() { return state.selectedAction && syncResource("actions", state.selectedAction.id, $("#save-action")); }
function syncSkill() { return state.selectedSkill && syncResource("skills", state.selectedSkill.id, $("#save-skill")); }

async function stageResourceDelete(kind) {
  const resource = selectedResource(kind);
  const meta = resourceMeta[kind];
  const loadToken = state.resourceLoadTokens[kind];
  if (!resource || !meta) return;
  if (!window.confirm(`将 ${meta.label}「${resource.name || resource.id}」标记为待删除吗？此操作只保存到 Studio，之后同步时还会再次确认。`)) return;
  let context;
  try {
    context = requireProjectContext();
    if (!await flushAutosaveKind(kind)) throw new Error("草稿尚未保存，无法标记删除。");
    if (!isCurrentProjectContext(context)
        || state.resourceLoadTokens[kind] !== loadToken
        || selectedResource(kind)?.id !== resource.id) {
      throw new Error(`${meta.label} 已切换，未执行删除。`);
    }
    const current = selectedResource(kind);
    const result = await projectApi(context.projectId, `/${kind}/${encodeURIComponent(current.id)}`, {
      method: "DELETE",
      headers: revisionHeaders(current.studioRevision ?? state.resourceRevisions[kind][current.id])
    });
    if (!isCurrentProjectContext(context)) return;
    const staged = resourceFrom(result, meta.singular);
    if (staged) {
      rememberResourceRevision(kind, staged.id, revisionFrom(result, staged));
      updateSummaryResource(kind, staged);
    }
    await refreshStudioResources(context);
    toast(`${meta.label} 已标记为待删除；Codex 文件尚未改变`);
  } catch (error) {
    if (!context || isCurrentProjectContext(context)) toast(error.message, true);
  }
}

function conflictValue(value, exists) {
  if (!exists) return "（字段不存在）";
  const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  return text.length > 900 ? `${text.slice(0, 900)}…` : text;
}

function openConflictDialog(kind) {
  const resource = selectedResource(kind);
  const conflicts = resource?.conflicts || [];
  if (!conflicts.length) { toast("这个资源没有待解决的字段冲突。", true); return; }
  const cancelsDelete = (resource.syncIntent || resource.sync_intent) === "delete";
  state.conflictTarget = { kind, id: resource.id, cancelsDelete };
  const deleteNotice = cancelsDelete
    ? `<p class="hint">此资源原本待删除。保存冲突解决方案会取消待删除并恢复为 Studio 草稿；如仍需删除，请解决后重新点击“删除”。</p>`
    : "";
  $("#conflict-list").innerHTML = deleteNotice + conflicts.map((conflict, index) => {
    const studioUnavailable = cancelsDelete && conflict.studioExists === false;
    return `
    <section class="conflict-item" data-conflict-path="${escapeHtml(conflict.path)}"><code>${escapeHtml(conflict.path)}</code><div class="conflict-choices"><label><input type="radio" name="conflict-${index}" value="studio" ${cancelsDelete ? "" : "checked"} ${studioUnavailable ? "disabled" : ""}><span><strong>Studio 草稿</strong><pre>${escapeHtml(conflictValue(conflict.studio, conflict.studioExists))}</pre></span></label><label><input type="radio" name="conflict-${index}" value="codex" ${cancelsDelete ? "checked" : ""}><span><strong>Codex 当前值</strong><pre>${escapeHtml(conflictValue(conflict.codex, conflict.codexExists))}</pre></span></label></div></section>`;
  }).join("");
  $("#conflict-dialog").showModal();
}

async function resolveConflicts() {
  const target = state.conflictTarget;
  const context = captureProjectContext();
  if (!target || !context) return;
  const resource = selectedResource(target.kind);
  const resolutions = {};
  document.querySelectorAll("#conflict-list [data-conflict-path]").forEach(item => {
    const selected = item.querySelector("input:checked");
    if (selected) resolutions[item.dataset.conflictPath] = selected.value;
  });
  const button = $("#resolve-conflicts");
  button.disabled = true;
  try {
    const result = await projectApi(context.projectId, `/${target.kind}/${encodeURIComponent(target.id)}/conflicts/resolve`, {
      method: "POST",
      headers: revisionHeaders(resource?.studioRevision ?? state.resourceRevisions[target.kind][target.id]),
      body: JSON.stringify({ resolutions })
    });
    if (!isCurrentProjectContext(context)) return;
    $("#conflict-dialog").close();
    await refreshStudioResources(context);
    toast(target.cancelsDelete ? "冲突已解决，删除已取消；如仍需删除请重新点击删除" : "冲突已解决，结果保存在 Studio");
  } catch (error) {
    if (isCurrentProjectContext(context)) toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

function aiWelcome(kind, editing = false) {
  const labels = { agent: "Agent", skill: "Skill", action: "Action" };
  if (!state.ai.configured) return `AI 助手界面已经就绪，但还没有可用模型。点击右上角设置，填写 API 地址与 Key、获取并选择模型后，即可通过对话创建 ${labels[kind]}。`;
  if (editing) return `我会基于当前 ${labels[kind]} 生成调整草稿。告诉我你想修改什么；草稿会保存在 Studio，只有明确同步后才会写入 Codex。`;
  return `描述你想创建的 ${labels[kind]}。我会先确认关键边界，再生成一个可编辑、可测试的草稿。`;
}

function renderAIWorkspace() {
  const kind = state.ai.kind;
  document.querySelectorAll("[data-ai-kind]").forEach(button => {
    const selected = button.dataset.aiKind === kind;
    button.classList.toggle("active", selected);
    button.setAttribute("aria-selected", selected ? "true" : "false");
    button.tabIndex = selected ? 0 : -1;
  });
  $("#ai-workspace").setAttribute("aria-labelledby", `ai-kind-${kind}`);
  $("#ai-input").placeholder = {
    agent: "描述 Agent 的职责、输入输出和边界…",
    skill: "描述 Skill 在什么情况下触发，以及它要完成什么…",
    action: "描述这个固定 Action 要做什么…"
  }[kind];
  renderAIMessages();
  renderAIDraft();
  syncAIOrientation();
}

async function restoreLatestAIDraft(kind, { silent = false, preserveOnEmpty = false, expectedResourceId = "" } = {}) {
  const context = captureProjectContext();
  if (!context || !["agent", "skill", "action"].includes(kind)) return false;
  const generation = ++state.ai.draftLoadGeneration;
  try {
    const result = await projectApi(context.projectId, `/ai/draft?kind=${encodeURIComponent(kind)}`);
    if (generation !== state.ai.draftLoadGeneration || !isCurrentProjectContext(context) || state.ai.kind !== kind) return false;
    const draft = result.draft && typeof result.draft === "object" ? result.draft : null;
    const restoredResourceId = String(result.resourceId || result.studioResource?.id || result.resource?.id || draft?.targetResourceId || draft?.targetAgentId || "");
    if (expectedResourceId && restoredResourceId !== expectedResourceId) {
      state.ai.projectId = context.projectId;
      return true;
    }
    if (!draft && preserveOnEmpty) {
      state.ai.projectId = context.projectId;
      return true;
    }
    const resourceEnvelope = result.studioResource || result.resource || null;
    const studioResource = resourceEnvelope?.id ? resourceEnvelope : null;
    const targetId = restoredResourceId;
    state.ai.projectId = context.projectId;
    state.ai.targetId = targetId;
    state.ai.studioResource = studioResource ? { ...studioResource } : null;
    state.ai.draft = draft ? { ...draft, kind, targetAgentId: targetId, targetResourceId: targetId } : null;
    if (!state.ai.messages.length || (state.ai.messages.length === 1 && state.ai.messages[0].role === "assistant")) {
      state.ai.messages = [{ role: "assistant", content: aiWelcome(kind, Boolean(draft)) }];
    }
    if (studioResource?.id) {
      const collection = `${kind}s`;
      updateSummaryResource(collection, studioResource);
      rememberResourceRevision(collection, studioResource.id, revisionFrom(result, studioResource));
      renderResources();
      renderSelectedProject();
    }
    renderAIWorkspace();
    return true;
  } catch (error) {
    if (generation === state.ai.draftLoadGeneration && isCurrentProjectContext(context) && !silent) {
      toast(`无法恢复 AI 草稿：${error.message}`, true);
    }
    return false;
  }
}

function startAICreation(kind, existing = null, navigate = true) {
  if (state.ai.request) stopComposerRequest("ai", true);
  state.ai.attachmentGeneration += 1;
  state.ai.pendingAttachmentReads = 0;
  composerFileQueues.ai = Promise.resolve();
  setComposerStatus("ai", "");
  state.ai.kind = kind;
  state.ai.projectId = state.project?.id || null;
  state.ai.targetId = existing?.id || "";
  state.ai.studioResource = existing ? { ...existing } : null;
  state.ai.draft = existing ? {
    kind,
    name: existing.name || "",
    description: existing.description || "",
    instructions: existing.instructions || "",
    model: existing.model || "inherit",
    actions: Array.isArray(existing.actions) ? existing.actions.map(item => ({ ...item })) : [],
    allowedActions: Array.isArray(existing.allowedActions) ? [...existing.allowedActions] : [],
    actionJson: kind === "action" ? JSON.stringify(existing, null, 2) : "",
    skills: Array.isArray(existing.skills) ? [...existing.skills] : [],
    targetAgentId: existing.id || "",
    targetResourceId: existing.id || ""
  } : null;
  state.ai.messages = [{ role: "assistant", content: aiWelcome(kind, Boolean(existing)) }];
  state.ai.attachments = [];
  $("#ai-file-input").value = "";
  renderComposerAttachments("ai");
  updateComposerButton("ai");
  if (navigate && state.section !== "ai") setSection("ai");
  renderAIWorkspace();
  void restoreLatestAIDraft(kind, {
    preserveOnEmpty: Boolean(existing),
    expectedResourceId: existing?.id || ""
  });
}

function renderAIMessages() {
  $("#ai-messages").innerHTML = state.ai.messages.map(message => `
    <article class="ai-message ${message.role}${message.loading ? " loading" : ""}"><small>${message.role === "user" ? "You" : "AI Assistant"}</small><p>${escapeHtml(message.content || "已添加附件")}</p>${messageAttachmentHtml(message)}</article>
  `).join("");
  $("#ai-messages").scrollTop = $("#ai-messages").scrollHeight;
}

function renderAIDraft() {
  const draft = state.ai.draft;
  $("#ai-draft-empty").classList.toggle("hidden", Boolean(draft));
  $("#ai-draft-form").classList.toggle("hidden", !draft);
  $("#ai-draft-title").textContent = draft ? draft.name || "未命名草稿" : "等待生成草稿";
  if (!draft) return;
  $("#ai-draft-kind").value = ({agent: "Agent", skill: "Skill", action: "Action"})[draft.kind] || draft.kind;
  $("#ai-draft-name").value = draft.name || "";
  $("#ai-draft-description").value = draft.description || "";
  $("#ai-draft-instructions").value = draft.instructions || "";
  $("#ai-draft-actions").value = (draft.actions || []).map(action => `${action.name} | ${action.instruction}`).join("\n");
  $("#ai-draft-action-json").value = draft.actionJson || "";
  $("#ai-draft-skills").value = (draft.skills || []).join(", ");
  $("#ai-draft-allowed-actions").value = (draft.allowedActions || []).join(", ");
  const isAgent = draft.kind === "agent";
  const isAction = draft.kind === "action";
  $("#ai-target-wrap").classList.add("hidden");
  $("#ai-actions-wrap").classList.add("hidden");
  $("#ai-action-json-wrap").classList.toggle("hidden", !isAction);
  $("#ai-instructions-wrap").classList.toggle("hidden", isAction);
  $("#ai-skills-wrap").classList.toggle("hidden", !isAgent);
  $("#ai-allowed-actions-wrap").classList.toggle("hidden", !isAgent);
  $("#ai-test-box").classList.toggle("hidden", !isAgent);
}

function collectAIDraft() {
  if (!state.ai.draft) return null;
  const actionLines = $("#ai-draft-actions").value.split("\n").map(line => line.trim()).filter(Boolean);
  const actions = actionLines.map((line, index) => {
    const [name, ...instruction] = line.split("|");
    return { id: slugify(name || `action-${index + 1}`), name: (name || "Action").trim(), instruction: instruction.join("|").trim() };
  });
  state.ai.draft = {
    ...state.ai.draft,
    kind: state.ai.kind,
    name: $("#ai-draft-name").value.trim(),
    description: $("#ai-draft-description").value.trim(),
    instructions: $("#ai-draft-instructions").value.trim(),
    actions,
    allowedActions: $("#ai-draft-allowed-actions").value.split(",").map(value => value.trim()).filter(Boolean),
    actionJson: $("#ai-draft-action-json").value.trim(),
    skills: $("#ai-draft-skills").value.split(",").map(value => value.trim().replace(/^\$/, "")).filter(Boolean),
    targetAgentId: state.ai.targetId || "",
    targetResourceId: state.ai.targetId || ""
  };
  $("#ai-draft-title").textContent = state.ai.draft.name || "未命名草稿";
  return state.ai.draft;
}

async function sendAIMessage(event) {
  event.preventDefault();
  if (state.ai.busy || !state.ai.configured) return;
  if (state.ai.pendingAttachmentReads) {
    setComposerStatus("ai", "附件仍在读取，请稍候。");
    return;
  }
  const input = $("#ai-input").value.trim();
  if (!input && !state.ai.attachments.length) return;
  let context;
  try {
    context = requireProjectContext();
  } catch (error) {
    setComposerStatus("ai", error.message, true);
    return;
  }
  if (state.ai.projectId !== context.projectId) {
    setComposerStatus("ai", "项目已切换；请在当前项目重新开始 AI 草稿。", true);
    return;
  }
  const attachments = state.ai.attachments.splice(0);
  state.ai.messages.push({ role: "user", content: input, attachments });
  $("#ai-input").value = "";
  resizeComposerInput("ai");
  renderComposerAttachments("ai");
  const loadingId = uid("ai-loading");
  const requestId = uid("ai-request");
  const request = { id: requestId, loadingId, controller: new AbortController(), cancelled: false };
  state.ai.request = request;
  state.ai.messages.push({ id: loadingId, role: "assistant", content: "正在梳理需求并生成结构化草稿…", loading: true });
  setComposerBusy("ai", true);
  setComposerStatus("ai", "正在生成，可随时停止。");
  renderAIMessages();
  try {
    const result = await projectApi(context.projectId, "/ai/chat", { method: "POST", body: JSON.stringify({
      requestId,
      kind: state.ai.kind,
      messages: serializeMessages(state.ai.messages),
      draft: collectAIDraft(),
      targetAgentId: state.ai.targetId
    }), signal: request.controller.signal });
    if (state.ai.request !== request || !isCurrentProjectContext(context)) return;
    const questions = (result.questions || []).map((question, index) => `${index + 1}. ${question}`).join("\n");
    replaceLoadingMessage(state.ai, loadingId, [result.message, questions].filter(Boolean).join("\n\n"));
    if (result.status === "draft" && result.draft) {
      state.ai.draft = { ...result.draft, kind: state.ai.kind, targetAgentId: state.ai.targetId || "", targetResourceId: state.ai.targetId || "" };
      const generatedResource = result.studioResource?.id ? result.studioResource : null;
      state.ai.studioResource = generatedResource;
      if (generatedResource) {
        state.ai.targetId = generatedResource.id;
        state.ai.draft.targetAgentId = state.ai.targetId || "";
        state.ai.draft.targetResourceId = state.ai.targetId || "";
        const kind = `${state.ai.kind}s`;
        updateSummaryResource(kind, generatedResource);
        rememberResourceRevision(kind, generatedResource.id, revisionFrom(result, generatedResource));
        renderResources();
        renderSelectedProject();
      }
      renderAIDraft();
    }
    setComposerStatus("ai", "");
  } catch (error) {
    if (state.ai.request !== request || !isCurrentProjectContext(context)) return;
    replaceLoadingMessage(state.ai, loadingId, error.name === "AbortError" || request.cancelled ? "已停止生成。" : `生成失败：${error.message}`);
    if (error.name !== "AbortError" && !request.cancelled) setComposerStatus("ai", error.message, true);
  } finally {
    if (state.ai.request === request) {
      state.ai.request = null;
      setComposerBusy("ai", false);
      renderAIMessages();
    }
  }
}

function aiDraftResourcePayload(draft, studioResource) {
  if (draft.kind === "action") {
    try { return JSON.parse(draft.actionJson); } catch (_) { return null; }
  }
  if (draft.kind === "skill") return { ...studioResource, name: draft.name, description: draft.description, instructions: draft.instructions };
  return {
    ...studioResource,
    name: draft.name,
    description: draft.description,
    instructions: draft.instructions,
    model: draft.model || studioResource.model || "inherit",
    allowedActions: draft.allowedActions || [],
    skills: draft.skills || []
  };
}

async function persistAIDraftToStudio() {
  const draft = collectAIDraft();
  const studioResource = state.ai.studioResource;
  const context = captureProjectContext();
  if (!draft) return true;
  if (!context || state.ai.projectId !== context.projectId) return false;
  const kind = `${draft.kind}s`;
  const resourceId = studioResource?.id || state.ai.targetId || "";
  const studioRevision = studioResource?.studioRevision ?? (resourceId ? state.resourceRevisions[kind][resourceId] : null) ?? null;
  try {
    await projectApi(context.projectId, "/ai/draft", {
      method: "PUT",
      body: JSON.stringify({ draft, kind: draft.kind, resourceId, studioRevision })
    });
    if (!isCurrentProjectContext(context)) return true;
    if (!studioResource?.id) return true;
    const payload = aiDraftResourcePayload(draft, studioResource);
    if (!payload) return false;
    const result = await projectApi(context.projectId, `/${kind}/${encodeURIComponent(resourceId)}`, {
      method: "PUT",
      headers: revisionHeaders(studioRevision),
      body: JSON.stringify(payload)
    });
    if (!isCurrentProjectContext(context)) return true;
    const saved = resourceFrom(result, draft.kind);
    if (!saved) return false;
    state.ai.studioResource = saved;
    updateSummaryResource(kind, saved);
    rememberResourceRevision(kind, saved.id, revisionFrom(result, saved));
    renderResources();
    renderSelectedProject();
    return true;
  } catch (error) {
    if (isCurrentProjectContext(context) && isRevisionConflict(error)) showRevisionConflict("AI 草稿");
    return false;
  }
}

async function testAIDraft() {
  const draft = collectAIDraft();
  if (!draft) return;
  const draftKind = state.ai.kind;
  const draftGeneration = state.ai.draftLoadGeneration;
  let context;
  try {
    context = requireProjectContext();
  } catch (error) {
    toast(error.message, true);
    return;
  }
  if (state.ai.projectId !== context.projectId) {
    toast("项目已切换；请在当前项目重新生成草稿后再测试。", true);
    return;
  }
  $("#ai-test-agent").disabled = true;
  try {
    if (!await flushAutosaveKind("ai")) throw new Error("AI Agent 草稿尚未保存，请先补全必填字段。");
    if (!isCurrentProjectContext(context)
        || state.ai.projectId !== context.projectId
        || state.ai.kind !== draftKind
        || state.ai.draftLoadGeneration !== draftGeneration) return;
    const agentId = state.ai.studioResource?.id;
    if (draft.kind !== "agent" || !agentId) throw new Error("请先生成可保存的 Agent 草稿后再测试。");
    const result = await projectApi(context.projectId, "/agent-tests", { method: "POST", body: JSON.stringify({ agentId, input: $("#ai-test-input").value }) });
    if (!isCurrentProjectContext(context)
        || state.ai.projectId !== context.projectId
        || state.ai.kind !== draftKind
        || state.ai.draftLoadGeneration !== draftGeneration) return;
    const job = result.job || result;
    rememberAgentJob({ ...job, agentId, status: job.status || "queued" });
    $("#ai-test-output").className = "";
    $("#ai-test-output").textContent = "测试已转入后台；完成后会用提示框告知结果。";
    toast("Agent 测试已在后台开始");
    clearTimeout(state.agentTests.timer);
    state.agentTests.timer = setTimeout(() => { void pollAgentTests(false); }, 500);
  } catch (error) {
    if (!isCurrentProjectContext(context)) return;
    toast(error.message, true);
  } finally {
    $("#ai-test-agent").disabled = false;
  }
}

async function publishAIDraft() {
  let draft = collectAIDraft();
  if (!draft) return;
  const context = captureProjectContext();
  if (!context || !state.ai.projectId || state.ai.projectId !== context.projectId) {
    toast("项目已切换；请在当前项目重新生成草稿后再发布。", true);
    return;
  }
  const button = $("#ai-publish");
  button.disabled = true;
  button.textContent = "正在发布…";
  try {
    if (!await flushAutosaveKind("ai")) throw new Error("AI 草稿尚未保存，请检查字段后再发布。");
    if (!isCurrentProjectContext(context) || state.ai.projectId !== context.projectId) return;
    draft = collectAIDraft();
    if (!draft) throw new Error("AI 草稿已变更，请重新确认后再发布。");
    const revisionKind = { agent: "agents", action: "actions", skill: "skills" }[draft.kind];
    const resourceId = state.ai.studioResource?.id || state.ai.targetId || "";
    const revision = state.ai.studioResource?.studioRevision
      ?? (resourceId && revisionKind ? state.resourceRevisions[revisionKind][resourceId] : null);
    const result = await projectApi(context.projectId, "/ai/publish", {
      method: "POST",
      headers: revisionHeaders(revision),
      body: JSON.stringify({ ...draft, projectId: context.projectId })
    });
    if (!isCurrentProjectContext(context)) return;
    const publishedResource = result.resource || result[draft.kind] || null;
    if (revisionKind && publishedResource?.id) rememberResourceRevision(revisionKind, publishedResource.id, revisionFrom(result, publishedResource));
    const resources = await Promise.all([
      projectApi(context.projectId, "/agents"),
      projectApi(context.projectId, "/actions"),
      projectApi(context.projectId, "/skills")
    ]);
    if (!isCurrentProjectContext(context)) return;
    state.agents = resources[0].agents;
    state.actions = resources[1].actions;
    state.skills = resources[2].skills;
    toast(`已发布 ${draft.kind} 到 Studio，尚未修改 Codex 文件`);
    state.ai.messages.push({ role: "assistant", content: `已保存并发布到 Studio。需要写入项目时，请在资源页点击“同步到 Codex”。` });
    renderAIMessages();
    if (draft.kind === "agent" && publishedResource) { state.selectedAgent = publishedResource; setSection("agents"); openAgent(publishedResource.id); }
    else if (draft.kind === "skill" && publishedResource) { state.selectedSkill = publishedResource; setSection("skills"); openSkill(publishedResource.id); }
    else if (draft.kind === "action" && publishedResource) { state.selectedAction = publishedResource; setSection("actions"); openAction(publishedResource.id); }
  } catch (error) {
    if (isCurrentProjectContext(context)) toast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = "发布到 Studio";
  }
}

const tutorialProjectId = "workflow-studio-tutorial";
const tutorialStepOrder = [
  "connection", "authorize-import", "test-requirements", "publish-requirements",
  "test-reviewer", "publish-reviewer", "add-agents", "connect-agents",
  "handoff-condition", "test-workflow", "publish-workflow", "batch-sync"
];

const onboardingCopies = {
  zh: {
    inviteTitle: "亲手搭建你的第一个 A2A 工作流",
    inviteBody: "在隔离练习项目中测试两个 Agent、完成交接、Dry-run 和批量同步。冒烟测试会调用真实模型，消耗少量 Codex/API 额度。",
    resumeTitle: "继续上次教程？", resumeBody: "进度已安全保存在 Studio，可以从当前步骤继续。",
    completeTitle: "你已完成第一个 A2A 工作流",
    completeBody: "两个 Agent 测试、Workflow Dry-run 和批量同步都已成功。Studio 负责编辑与同步，Workflow 仍由 Codex 运行。",
    deleteTitle: "确定删除全部教程数据？", deleteBody: "只会删除 Workflow Studio 应用数据区中带有教程标记的隔离目录与 Studio 记录，不会触碰真实项目。"
  },
  en: {
    inviteTitle: "Build your first A2A Workflow hands-on",
    inviteBody: "Test two Agents in an isolated practice project, add a handoff, run a Dry-run, and batch sync. Smoke tests call a real model and use a small amount of your Codex/API allowance.",
    resumeTitle: "Continue your tutorial?", resumeBody: "Your Studio progress is saved. Continue from the current verified step.",
    completeTitle: "Your first A2A Workflow is complete",
    completeBody: "Both Agent smoke tests, the Workflow Dry-run, and batch sync succeeded. Studio edits and syncs the Workflow; Codex still runs it.",
    deleteTitle: "Delete all tutorial data?", deleteBody: "Only the marked isolated directory under Workflow Studio application data and its Studio records will be deleted. Real projects are never touched."
  }
};

const tutorialStepCopies = {
  zh: {
    "connection": ["连接一个活动模型", "选择 Codex 官方设备码登录，或使用你的 API。同时可用时请明确选择一个，Studio 不会自动回退。"],
    "authorize-import": ["授权并导入隔离项目", "亲手点击“授权并导入项目”。这一步只读导入，并在 Studio 数据库中预置三个草稿；此时不写 Codex 资源文件。"],
    "test-requirements": ["测试需求澄清员", "点击“一键测试”。将使用固定示例任务调用真实模型；失败后不会自动重试。"],
    "publish-requirements": ["发布需求澄清员", "测试已通过。点击“发布到 Studio”；这仍然不会写入 Codex 项目。"],
    "test-reviewer": ["测试方案审校员", "对第二个 Agent 执行真实模型冒烟测试。"],
    "publish-reviewer": ["发布方案审校员", "点击“发布到 Studio”，让它成为待同步资源。"],
    "add-agents": ["把两个 Agent 加入画布", "从左侧依次点击需求澄清员和方案审校员。"],
    "connect-agents": ["建立 A2A 交接", "从需求澄清员右侧端口拖到方案审校员左侧端口。"],
    "handoff-condition": ["选择交接预设", "选中连线，然后使用预设：“需求、范围、约束和验收标准已整理完成”。"],
    "test-workflow": ["执行 Workflow Dry-run", "Dry-run 只读检查图、依赖与交接，不会在 Studio 内运行 Workflow。"],
    "publish-workflow": ["发布 Workflow", "Dry-run 已通过。点击“发布到 Studio”。"],
    "batch-sync": ["预览并确认批量同步", "返回项目页，预览依赖与目标文件，再明确确认。只有这一步会写入 Codex 项目目录。"]
  },
  en: {
    "connection": ["Connect an active model", "Use official Codex device authorization or your API. If both work, choose one explicitly; Studio never auto-falls back."],
    "authorize-import": ["Authorize and import the isolated project", "Click Authorize & import yourself. This is read-only and seeds three drafts in Studio; no Codex resource files are written yet."],
    "test-requirements": ["Test the Requirements Clarifier", "Run the real-model smoke test with the fixed example task. Failures are never retried automatically."],
    "publish-requirements": ["Publish the Requirements Clarifier", "The test passed. Publish to Studio; this still does not write Codex files."],
    "test-reviewer": ["Test the Plan Reviewer", "Run a real-model smoke test for the second Agent."],
    "publish-reviewer": ["Publish the Plan Reviewer", "Publish it to Studio so it becomes ready to sync."],
    "add-agents": ["Add both Agents to the canvas", "Click Requirements Clarifier and Plan Reviewer in the left library."],
    "connect-agents": ["Create the A2A handoff", "Drag from the Requirements Clarifier's right port to the Plan Reviewer's left port."],
    "handoff-condition": ["Choose the handoff preset", "Select the edge and apply: “Requirements, scope, constraints, and acceptance criteria are complete.”"],
    "test-workflow": ["Run the Workflow Dry-run", "Dry-run validates the graph, dependencies, and handoff read-only. Studio does not run the Workflow."],
    "publish-workflow": ["Publish the Workflow", "The Dry-run passed. Publish it to Studio."],
    "batch-sync": ["Preview and confirm batch sync", "Return to the project page, inspect dependencies and target files, then explicitly confirm. This is the only step that writes Codex project files."]
  }
};

function renderOnboardingCopy() {
  const copy = onboardingCopies[state.language] || onboardingCopies.zh;
  document.querySelectorAll("[data-onboarding-copy]").forEach(element => {
    element.textContent = copy[element.dataset.onboardingCopy] || element.textContent;
  });
}

function clearTutorialTarget() {
  document.querySelectorAll(".tutorial-target").forEach(element => element.classList.remove("tutorial-target"));
  $("#tutorial-handoff-preset")?.classList.add("hidden");
}

function markTutorialTarget(selector) {
  clearTutorialTarget();
  const element = document.querySelector(selector);
  if (element) element.classList.add("tutorial-target");
  placeTutorialCoach(element);
  return element;
}

// The coach sits bottom-right; move it to the other side when it would cover the target.
function placeTutorialCoach(target) {
  const coach = document.querySelector(".tutorial-coach");
  if (!coach) return;
  coach.classList.remove("avoid-target");
  if (!target) return;
  const a = target.getBoundingClientRect();
  const b = coach.getBoundingClientRect();
  const overlaps = a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
  coach.classList.toggle("avoid-target", overlaps);
}

// ---- Sync targets: which coding agents the project is written for. Codex and
// OpenCode always read AGENTS.md and .agents/skills; others are opt-in.
async function loadProjectTargets(projectId) {
  try {
    const payload = await projectApi(projectId, "/targets");
    if (state.project?.id !== projectId) return;
    state.targets = { projectId, ...payload };
    renderProjectTargets();
  } catch (error) {
    $("#target-list").innerHTML = `<div class="pending-sync-empty">${escapeHtml(error.message)}</div>`;
  }
}

function renderProjectTargets() {
  const list = $("#target-list");
  if (!list || !state.targets) return;
  const enabled = new Set(state.targets.targets || []);
  list.innerHTML = (state.targets.options || []).map(option => {
    const checked = option.always || enabled.has(option.id);
    return `<label class="target-row${option.always ? " always" : ""}">
      <input type="checkbox" data-target-id="${escapeHtml(option.id)}" ${checked ? "checked" : ""} ${option.always ? "disabled" : ""}>
      <span class="target-copy"><strong>${escapeHtml(option.label)}</strong><small>${escapeHtml(`${tr(option.always ? "targetAlways" : "targetOnSync")} · `)}${escapeHtml((option.files || []).join("、"))}</small></span>
      ${option.detected ? `<span class="target-detected">${tr("targetDetected")}</span>` : ""}
    </label>`;
  }).join("");
  list.querySelectorAll("input[data-target-id]:not(:disabled)").forEach(input => input.addEventListener("change", () => updateProjectTargets(input)));
}

async function updateProjectTargets(changedInput) {
  const context = captureProjectContext();
  if (!context) return;
  const targets = [...$("#target-list").querySelectorAll("input[data-target-id]:not(:disabled)")].filter(input => input.checked).map(input => input.dataset.targetId);
  const newlyEnabled = changedInput.checked;
  try {
    const payload = await projectApi(context.projectId, "/targets", { method: "PUT", body: JSON.stringify({ targets }) });
    if (!isCurrentProjectContext(context)) return;
    state.targets = { projectId: context.projectId, ...payload };
    renderProjectTargets();
    const label = (payload.options || []).find(option => option.id === changedInput.dataset.targetId)?.label || "";
    if (!newlyEnabled) {
      toast(`已停止向 ${label} 同步；已写入的文件保持不变`);
      return;
    }
    if (!window.confirm(`现在把已同步的 Workflow 和 Agent 也写入 ${label} 读取的位置吗？\n这会修改项目文件；之后的同步会自动保持更新。`)) {
      toast(`已开启 ${label}，下次同步时写入`);
      return;
    }
    const applied = await projectApi(context.projectId, "/targets/apply", { method: "POST", body: "{}" });
    if (!isCurrentProjectContext(context)) return;
    toast(`已为 ${label} 写入 ${(applied.writtenFiles || []).length} 个文件`);
  } catch (error) {
    if (isCurrentProjectContext(context)) toast(error.message, true);
  }
}

// ---- Folder projects: any local folder can be a project, not only Codex's list.
async function addFolderProject() {
  try {
    let result = null;
    try {
      result = await globalApi("/api/codex/projects/choose-folder", { method: "POST", body: "{}" });
    } catch (_) {
      const path = window.prompt("输入项目文件夹的完整路径（以 / 开头）");
      if (!path) return;
      result = await globalApi("/api/codex/projects/folders", { method: "POST", body: JSON.stringify({ path }) });
    }
    if (!result || result.cancelled || !result.added) return;
    await refreshProjectCatalog(result.added.id);
    toast(`已添加项目「${result.added.title}」，授权导入后即可使用`);
  } catch (error) {
    toast(error.message, true);
  }
}

async function removeFolderProject() {
  const project = state.projects.find(item => item.id === state.selectedProjectId);
  if (!project || project.source !== "folder") return;
  if (!window.confirm(`从项目库移除「${project.title}」吗？不会删除文件夹或其中的任何文件。`)) return;
  try {
    await globalApi("/api/codex/projects/folders/remove", { method: "POST", body: JSON.stringify({ id: project.id }) });
    await refreshProjectCatalog();
    toast("已从项目库移除");
  } catch (error) {
    toast(error.message, true);
  }
}

async function refreshProjectCatalog(preferredId = null) {
  const payload = await globalApi("/api/codex/projects");
  state.projects = payload.projects || [];
  if (preferredId && state.projects.some(project => project.id === preferredId)) state.selectedProjectId = preferredId;
  else if (!state.projects.some(project => project.id === state.selectedProjectId)) state.selectedProjectId = state.projects[0]?.id || null;
  renderProjectList();
  renderSelectedProject();
}

async function ensureTutorialSelected() {
  await refreshProjectCatalog(tutorialProjectId);
  if (state.selectedProjectId !== tutorialProjectId || state.project?.id !== tutorialProjectId) await selectProject(tutorialProjectId);
}

function scheduleOnboardingPoll() {
  clearTimeout(state.onboarding.pollTimer);
  if (state.onboarding.active) state.onboarding.pollTimer = setTimeout(() => { void loadOnboarding(false); }, 1100);
}

async function loadOnboarding(initial = false) {
  try {
    const status = await globalApi("/api/onboarding");
    const previous = state.onboarding.status;
    state.onboarding.status = status;
    // Celebrate only a completion seen happening here; a fresh page load has no previous status.
    if (status.status === "completed" && previous && previous.status !== "completed") showOnboardingCompletion(true);
    else if (state.onboarding.active) await prepareTutorialStep(status);
    else if (initial && status.invitation === "pending" && status.status === "not_started") $("#onboarding-invite-dialog").showModal();
    else if (initial && status.status === "in_progress" && status.canResume) $("#onboarding-resume-dialog").showModal();
  } catch (error) {
    if (state.onboarding.active) showTutorialError(error.message);
  } finally {
    scheduleOnboardingPoll();
  }
}

async function startOnboarding(restart = false) {
  const route = restart ? "/api/onboarding/restart" : "/api/onboarding/start";
  try {
    const status = await globalApi(route, { method: "POST", body: JSON.stringify({ language: state.language }) });
    state.onboarding.startedHere = true;
    state.onboarding.status = status;
    ["#onboarding-invite-dialog", "#onboarding-resume-dialog"].forEach(selector => { if ($(selector).open) $(selector).close(); });
    if (restart && state.project?.id === tutorialProjectId) clearProjectClientContext();
    await continueOnboarding();
  } catch (error) { toast(error.message, true); }
}

async function continueOnboarding() {
  const status = state.onboarding.status || await globalApi("/api/onboarding");
  state.onboarding.status = status;
  if ($("#onboarding-resume-dialog").open) $("#onboarding-resume-dialog").close();
  await ensureTutorialSelected();
  if (status.status === "completed") {
    if (projectIsAuthorized(state.projects.find(project => project.id === tutorialProjectId))) await syncProject(tutorialProjectId, { silent: true });
    setSection("workflow");
    return;
  }
  state.onboarding.active = true;
  // Tutorial targets inside the canvas need an untransformed viewport.
  applyView();
  $("#tutorial-overlay").classList.remove("hidden");
  await prepareTutorialStep(status, true);
  scheduleOnboardingPoll();
}

async function prepareTutorialStep(status, force = false) {
  if (!state.onboarding.active || !status || status.status === "completed") return;
  const step = status.stepId;
  const changed = force || state.onboarding.preparedStep !== step;
  state.onboarding.preparedStep = step;
  const index = Math.max(0, tutorialStepOrder.indexOf(step));
  const copy = (tutorialStepCopies[state.language] || tutorialStepCopies.zh)[step] || [step, ""];
  $("#tutorial-step-count").textContent = `${index + 1} / ${tutorialStepOrder.length}`;
  $("#tutorial-progress-bar").style.width = `${Math.max(4, (index + 1) / tutorialStepOrder.length * 100)}%`;
  $("#tutorial-step-title").textContent = copy[0];
  $("#tutorial-step-body").textContent = copy[1];
  $("#tutorial-open-connections").classList.toggle("hidden", step !== "connection");
  const failure = status.failure?.message || status.failure || "";
  $("#tutorial-error").textContent = failure;
  $("#tutorial-error").classList.toggle("hidden", !failure);
  $("#tutorial-retry").classList.toggle("hidden", !failure);
  if (!changed) return;
  clearTutorialTarget();
  try {
    if (step === "connection") { markTutorialTarget("#ai-provider"); return; }
    await ensureTutorialSelected();
    if (step === "authorize-import") { setSection("projects"); markTutorialTarget(".project-sync-card"); return; }
    if (state.project?.id !== tutorialProjectId) await syncProject(tutorialProjectId, { silent: true });
    if (["test-requirements", "publish-requirements", "test-reviewer", "publish-reviewer"].includes(step)) {
      const agentId = step.includes("requirements") ? "requirements-clarifier" : "plan-reviewer";
      await openAgent(agentId);
      markTutorialTarget(step.startsWith("test-") ? "#test-agent" : "#publish-agent");
      return;
    }
    if (["add-agents", "connect-agents", "handoff-condition", "test-workflow", "publish-workflow"].includes(step)) {
      if (state.workflow?.id !== "a2a-requirement-review") await loadWorkflow("a2a-requirement-review");
      setSection("workflow");
      if (step === "add-agents") markTutorialTarget(".library-panel");
      if (step === "connect-agents") markTutorialTarget("#canvas");
      if (step === "handoff-condition") {
        const edge = state.workflow.edges.find(item => {
          const source = state.workflow.nodes.find(node => node.id === item.source);
          const target = state.workflow.nodes.find(node => node.id === item.target);
          return source?.agentId === "requirements-clarifier" && target?.agentId === "plan-reviewer";
        });
        if (edge) { state.selectedEdgeId = edge.id; state.selectedNodeId = null; render(); }
        markTutorialTarget("#workflow-inspector");
        $("#tutorial-handoff-preset").classList.remove("hidden");
      }
      if (step === "test-workflow") markTutorialTarget("#test-workflow");
      if (step === "publish-workflow") markTutorialTarget("#publish-workflow");
      return;
    }
    if (step === "batch-sync") { setSection("projects"); markTutorialTarget("#project-sync-center"); }
  } catch (error) { showTutorialError(error.message); }
}

function showTutorialError(message) {
  $("#tutorial-error").textContent = message;
  $("#tutorial-error").classList.remove("hidden");
  $("#tutorial-retry").classList.remove("hidden");
}

async function retryTutorialStep() {
  const step = state.onboarding.status?.stepId;
  if (["test-requirements", "test-reviewer"].includes(step)) await testAgent();
  else if (step === "test-workflow") await testWorkflow(true);
  else if (step === "connection") await openAIConfig();
  else if (step === "batch-sync") await openProjectSyncPreview();
}

async function pauseOnboarding() {
  try { await globalApi("/api/onboarding/pause", { method: "POST", body: "{}" }); } catch (_) { /* progress is already persisted */ }
  state.onboarding.active = false;
  clearTimeout(state.onboarding.pollTimer);
  clearTutorialTarget();
  $("#tutorial-overlay").classList.add("hidden");
  autoFitView();
}

function fireTutorialConfetti() {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const layer = $("#confetti-layer");
  layer.innerHTML = "";
  const colors = ["#80e6a8", "#c9baff", "#e9c46a", "#76b7ff", "#f38ba8"];
  for (let index = 0; index < 42; index += 1) {
    const piece = document.createElement("i");
    piece.className = "confetti-piece";
    piece.style.left = `${Math.random() * 100}%`;
    piece.style.background = colors[index % colors.length];
    piece.style.setProperty("--drift", `${Math.round(Math.random() * 180 - 90)}px`);
    piece.style.animationDelay = `${Math.random() * .45}s`;
    layer.append(piece);
  }
  setTimeout(() => { layer.innerHTML = ""; }, 3400);
}

function showOnboardingCompletion(celebrate = false) {
  state.onboarding.active = false;
  clearTimeout(state.onboarding.pollTimer);
  clearTutorialTarget();
  $("#tutorial-overlay").classList.add("hidden");
  autoFitView();
  if ($("#sync-preview-dialog").open) $("#sync-preview-dialog").close();
  if (celebrate && !state.onboarding.completionShown) fireTutorialConfetti();
  state.onboarding.completionShown = true;
  if (!$("#onboarding-complete-dialog").open) $("#onboarding-complete-dialog").showModal();
}

async function keepTutorialProject() {
  try {
    await globalApi("/api/onboarding/keep", { method: "POST", body: "{}" });
    $("#onboarding-complete-dialog").close();
    await ensureTutorialSelected();
    await syncProject(tutorialProjectId, { silent: true });
    setSection("workflow");
  } catch (error) { toast(error.message, true); }
}

async function deleteTutorialData() {
  const button = $("#confirm-delete-tutorial");
  button.disabled = true;
  try {
    const status = await globalApi("/api/onboarding/delete", { method: "POST", body: JSON.stringify({ confirm: true }) });
    state.onboarding.status = status;
    if ($("#delete-tutorial-dialog").open) $("#delete-tutorial-dialog").close();
    if ($("#onboarding-complete-dialog").open) $("#onboarding-complete-dialog").close();
    clearProjectClientContext();
    await refreshProjectCatalog();
    finishOnboardingToProjects();
  } catch (error) { toast(error.message, true); }
  finally { button.disabled = false; }
}

function finishOnboardingToProjects() {
  if ($("#onboarding-complete-dialog").open) $("#onboarding-complete-dialog").close();
  const ownProject = state.projects.find(project => !project.tutorial);
  if (ownProject) {
    state.selectedProjectId = ownProject.id;
    if (state.project?.id !== ownProject.id) clearProjectClientContext();
  }
  setSection("projects");
  renderProjectList();
  renderSelectedProject();
  const button = $("#sync-project-details");
  button?.classList.add("tutorial-cta-highlight");
  setTimeout(() => button?.classList.remove("tutorial-cta-highlight"), 4800);
}

async function openTutorialFromMenu() {
  closeProfileMenu();
  const status = await globalApi("/api/onboarding");
  state.onboarding.status = status;
  const copy = onboardingCopies[state.language] || onboardingCopies.zh;
  $("#onboarding-resume-dialog [data-onboarding-copy=resumeTitle]").textContent = copy.resumeTitle;
  $("#onboarding-resume-dialog [data-onboarding-copy=resumeBody]").textContent = copy.resumeBody;
  $("#resume-onboarding").textContent = tr("continue");
  if (status.status === "in_progress") {
    $("#onboarding-resume-dialog").showModal();
  } else if (status.status === "completed" && status.project) {
    $("#onboarding-resume-dialog [data-onboarding-copy=resumeTitle]").textContent = state.language === "zh" ? "教程已完成" : "Tutorial complete";
    $("#onboarding-resume-dialog [data-onboarding-copy=resumeBody]").textContent = state.language === "zh" ? "可以继续探索已保留的练习项目，或确认重新开始。" : "Explore the retained practice project, or confirm a fresh restart.";
    $("#resume-onboarding").textContent = state.language === "zh" ? "继续探索" : "Explore project";
    $("#onboarding-resume-dialog").showModal();
  } else {
    $("#onboarding-invite-dialog [data-onboarding-copy=inviteTitle]").textContent = copy.inviteTitle;
    $("#onboarding-invite-dialog").showModal();
  }
}

function bindEvents() {
  $("#profile-toggle").addEventListener("click", event => {
    event.stopPropagation();
    const menu = $("#profile-menu");
    const opening = menu.classList.contains("hidden");
    menu.classList.toggle("hidden", !opening);
    $("#profile-toggle").setAttribute("aria-expanded", String(opening));
  });
  document.querySelectorAll("[data-language]").forEach(button => button.addEventListener("click", event => {
    event.stopPropagation();
    applyLanguage(button.dataset.language);
    closeProfileMenu();
  }));
  document.addEventListener("click", closeProfileMenu);
  $("#profile-menu").addEventListener("click", event => event.stopPropagation());
  $("#profile-tutorial").addEventListener("click", () => { void openTutorialFromMenu(); });
  $("#profile-connections").addEventListener("click", () => { closeProfileMenu(); void openAIConfig(); });
  $("#profile-help").addEventListener("click", () => { closeProfileMenu(); openAppAssistant(); });
  $("#profile-about").addEventListener("click", () => { closeProfileMenu(); $("#about-dialog").showModal(); });
  $("#close-about").addEventListener("click", () => $("#about-dialog").close());
  $("#resource-search").addEventListener("input", renderResources);
  $("#add-folder-project")?.addEventListener("click", addFolderProject);
  $("#remove-folder-project")?.addEventListener("click", removeFolderProject);
  $("#refresh-resources").addEventListener("click", async () => {
    if (state.section === "projects") {
      const payload = await globalApi("/api/codex/projects");
      state.projects = payload.projects;
      if (!state.projects.some(project => project.id === state.selectedProjectId)) state.selectedProjectId = state.projects[0]?.id || null;
      renderResources();
      toast(tr("projectsInLibrary", state.projects.length));
      return;
    }
    if (!state.project) { setSection("projects"); return; }
    await syncProject(state.project.id);
  });
  document.querySelectorAll("[data-section]").forEach(button => button.addEventListener("click", () => navigateToSection(button.dataset.section)));
  $("#open-ai-assistant").addEventListener("click", openAppAssistant);
  $("#ai-provider").addEventListener("click", openAIConfig);
  $("#close-ai-config").addEventListener("click", () => $("#ai-config-dialog").close());
  $("#fetch-ai-models").addEventListener("click", fetchAIModels);
  $("#ai-config-form").addEventListener("submit", saveAIConfig);
  $("#start-device-auth").addEventListener("click", startDeviceAuth);
  $("#cancel-device-auth").addEventListener("click", cancelDeviceAuth);
  $("#use-codex-provider").addEventListener("click", useCodexProvider);
  $("#forget-api-key").addEventListener("click", forgetAPIKey);
  $("#close-app-assistant").addEventListener("click", () => $("#app-assistant-dialog").close());
  $("#guide-composer").addEventListener("submit", sendGuideMessage);
  setupComposerEvents("guide");
  $("#sync-project-details").addEventListener("click", () => state.selectedProjectId && syncProject(state.selectedProjectId));
  $("#dismiss-onboarding").addEventListener("click", async () => {
    try { state.onboarding.status = await globalApi("/api/onboarding/invitation/dismiss", { method: "POST", body: "{}" }); } catch (_) { /* dismissal is best effort */ }
    $("#onboarding-invite-dialog").close();
  });
  $("#start-onboarding").addEventListener("click", () => { void startOnboarding(false); });
  $("#resume-onboarding").addEventListener("click", () => { void continueOnboarding(); });
  $("#restart-onboarding").addEventListener("click", () => { void startOnboarding(true); });
  $("#resume-later").addEventListener("click", () => $("#onboarding-resume-dialog").close());
  $("#pause-onboarding").addEventListener("click", pauseOnboarding);
  $("#tutorial-open-connections").addEventListener("click", openAIConfig);
  $("#tutorial-retry").addEventListener("click", retryTutorialStep);
  $("#keep-tutorial").addEventListener("click", keepTutorialProject);
  // The shade blocks the page during the tutorial; say so instead of ignoring the click.
  document.querySelector(".tutorial-shade")?.addEventListener("click", () => {
    const highlighted = [document.querySelector(".tutorial-coach"), ...document.querySelectorAll(".tutorial-target")].filter(Boolean);
    highlighted.forEach(element => {
      element.classList.remove("tutorial-cta-highlight");
      void element.offsetWidth;
      element.classList.add("tutorial-cta-highlight");
    });
    toast(state.language === "zh" ? "教程进行中：请先完成高亮的步骤，或点击“稍后继续”退出。" : "Tutorial in progress: finish the highlighted step, or choose Continue later to leave.");
  });
  $("#delete-tutorial").addEventListener("click", () => $("#delete-tutorial-dialog").showModal());
  $("#cancel-delete-tutorial").addEventListener("click", () => $("#delete-tutorial-dialog").close());
  $("#confirm-delete-tutorial").addEventListener("click", deleteTutorialData);
  $("#finish-onboarding").addEventListener("click", finishOnboardingToProjects);
  $("#preview-project-sync").addEventListener("click", openProjectSyncPreview);
  $("#close-sync-preview").addEventListener("click", () => $("#sync-preview-dialog").close());
  $("#cancel-project-sync").addEventListener("click", () => $("#sync-preview-dialog").close());
  $("#confirm-sync-deletes").addEventListener("change", event => {
    $("#run-project-sync").disabled = $("#run-project-sync").dataset.canSync !== "true" || (state.syncPreviewHasDelete && !event.target.checked);
  });
  $("#run-project-sync").addEventListener("click", runProjectSync);
  $("#close-conflict-dialog").addEventListener("click", () => $("#conflict-dialog").close());
  $("#cancel-conflict").addEventListener("click", () => $("#conflict-dialog").close());
  $("#resolve-conflicts").addEventListener("click", resolveConflicts);
  document.querySelectorAll("[data-open-project-resource]").forEach(button => button.addEventListener("click", () => navigateToSection(button.dataset.openProjectResource)));
  $("#ai-agent").addEventListener("click", async () => {
    if (!await flushAutosaves()) { toast("当前 Studio 草稿尚未保存，无法进入 AI 工作台。", true); return; }
    startAICreation("agent", state.selectedAgent);
  });
  $("#ai-skill").addEventListener("click", async () => {
    if (!await flushAutosaves()) { toast("当前 Studio 草稿尚未保存，无法进入 AI 工作台。", true); return; }
    startAICreation("skill", state.selectedSkill);
  });
  $("#ai-action").addEventListener("click", async () => {
    if (!await flushAutosaves()) { toast("当前 Studio 草稿尚未保存，无法进入 AI 工作台。", true); return; }
    startAICreation("action", state.selectedAction);
  });
  $("#new-action").addEventListener("click", newAction);
  $("#action-preset-api").addEventListener("click", () => applyActionPreset("api"));
  $("#action-preset-mcp").addEventListener("click", () => applyActionPreset("mcp"));
  $("#check-action-connection").addEventListener("click", checkActionConnection);
  $("#action-json").addEventListener("input", () => { resetActionConnectionStatus(); renderActionJsonError(); markEditorDraft("actions"); });
  $("#action-mode-form")?.addEventListener("click", () => setActionMode("form"));
  $("#action-mode-json")?.addEventListener("click", () => setActionMode("json"));
  $("#action-form")?.addEventListener("input", event => { if (event.target.id !== "af-executor") writeActionFromForm(); });
  $("#action-form")?.addEventListener("change", event => { if (["SELECT"].includes(event.target.tagName) || event.target.type === "number") writeActionFromForm(); });
  $("#action-editor-form")?.addEventListener("submit", event => event.preventDefault());
  try { setActionMode(localStorage.getItem("workflow-studio-action-mode") || "form"); } catch (_) { setActionMode("form"); }
  $("#publish-action").addEventListener("click", publishAction);
  $("#save-action").addEventListener("click", () => publishAndReviewSync("actions"));
  $("#delete-action").addEventListener("click", () => stageResourceDelete("actions"));
  $("#resolve-action").addEventListener("click", () => openConflictDialog("actions"));
  const aiKindTabs = [...document.querySelectorAll("[data-ai-kind]")];
  aiKindTabs.forEach((button, index) => {
    button.addEventListener("click", async () => {
      if (!await flushAutosaveKind("ai")) {
        toast("AI 草稿尚未保存，已取消切换。", true);
        return;
      }
      startAICreation(button.dataset.aiKind, null, false);
    });
    button.addEventListener("keydown", event => {
      let targetIndex = null;
      if (event.key === "ArrowRight") targetIndex = (index + 1) % aiKindTabs.length;
      if (event.key === "ArrowLeft") targetIndex = (index - 1 + aiKindTabs.length) % aiKindTabs.length;
      if (event.key === "Home") targetIndex = 0;
      if (event.key === "End") targetIndex = aiKindTabs.length - 1;
      if (targetIndex === null) return;
      event.preventDefault();
      aiKindTabs[targetIndex].focus();
      aiKindTabs[targetIndex].click();
    });
  });
  $("#ai-composer").addEventListener("submit", sendAIMessage);
  setupComposerEvents("ai");
  $("#ai-draft-form").addEventListener("input", () => { collectAIDraft(); scheduleAutosave("ai"); });
  $("#ai-draft-form").addEventListener("change", () => { collectAIDraft(); scheduleAutosave("ai"); });
  $("#ai-test-agent").addEventListener("click", testAIDraft);
  $("#ai-publish").addEventListener("click", publishAIDraft);
  $("#publish-agent").addEventListener("click", publishAgent);
  $("#save-agent").addEventListener("click", () => publishAndReviewSync("agents"));
  $("#delete-agent").addEventListener("click", () => stageResourceDelete("agents"));
  $("#resolve-agent").addEventListener("click", () => openConflictDialog("agents"));
  $("#test-agent").addEventListener("click", testAgent);
  $("#publish-skill").addEventListener("click", publishSkill);
  $("#save-skill").addEventListener("click", () => publishAndReviewSync("skills"));
  $("#delete-skill").addEventListener("click", () => stageResourceDelete("skills"));
  $("#resolve-skill").addEventListener("click", () => openConflictDialog("skills"));
  $("#agent-editor-form").addEventListener("input", () => markEditorDraft("agents"));
  $("#agent-editor-form").addEventListener("change", () => markEditorDraft("agents"));
  $("#skill-editor-form").addEventListener("input", () => markEditorDraft("skills"));
  $("#skill-editor-form").addEventListener("change", () => markEditorDraft("skills"));
  ["agent-editor-form", "action-editor-form", "skill-editor-form"].forEach(id => $("#" + id).addEventListener("submit", event => event.preventDefault()));
  $("#workflow-name").addEventListener("input", event => { state.workflow.name = event.target.value; markDirty(); });
  $("#select-tool").addEventListener("click", () => setMode("select"));
  $("#connect-tool").addEventListener("click", () => setMode("connect"));
  $("#auto-layout").addEventListener("click", autoLayout);
  $("#fit-view").addEventListener("click", fitView);
  $("#test-workflow").addEventListener("click", () => testWorkflow(true));
  $("#publish-workflow").addEventListener("click", publishWorkflow);
  $("#save-workflow").addEventListener("click", () => publishAndReviewSync("workflows"));
  $("#delete-workflow").addEventListener("click", () => stageResourceDelete("workflows"));
  $("#resolve-workflow").addEventListener("click", () => openConflictDialog("workflows"));
  $("#copy-run").addEventListener("click", openRunDialog);
  $("#copy-command").addEventListener("click", event => { event.preventDefault(); copyCommand(); });
  $("#edge-delete-popover").addEventListener("click", event => { event.stopPropagation(); $("#remove-edge").click(); });
  $("#tutorial-handoff-preset").addEventListener("click", () => {
    const condition = state.onboarding.status?.handoffCondition || (state.language === "zh" ? "需求、范围、约束和验收标准已整理完成" : "Requirements, scope, constraints, and acceptance criteria are complete.");
    $("#edge-condition").value = condition;
    $("#edge-condition").dispatchEvent(new Event("input", { bubbles: true }));
  });
  bindCanvasPanZoom();
  // On narrow windows the inspector is a sheet; this opens it on the Workflow settings.
  $("#workflow-settings-toggle")?.addEventListener("click", () => {
    const panel = $("#workflow-inspector");
    const open = !panel.classList.contains("settings-open");
    if (open) {
      state.selectedNodeId = null;
      state.selectedEdgeId = null;
      render();
    }
    panel.classList.toggle("settings-open", open);
    $("#workflow-settings-toggle").setAttribute("aria-expanded", open ? "true" : "false");
    if (open) $("#workflow-start-phrases")?.focus({ preventScroll: true });
  });
  $("#close-inspector").addEventListener("click", () => {
    $("#workflow-inspector").classList.remove("settings-open");
    $("#workflow-settings-toggle")?.setAttribute("aria-expanded", "false");
    if (state.mode === "connect") cancelConnection(false);
    state.selectedNodeId = null;
    state.selectedEdgeId = null;
    render();
    canvas.focus({ preventScroll: true });
  });
  canvas.addEventListener("dragover", event => { event.preventDefault(); event.dataTransfer.dropEffect = "copy"; });
  canvas.addEventListener("pointermove", event => {
    if (state.mode === "connect" && state.connectSource && !state.connectionDrag) updateDraftConnection(event.clientX, event.clientY);
  });
  canvas.addEventListener("drop", event => {
    event.preventDefault();
    const agentId = event.dataTransfer.getData("text/agent-id");
    const actionId = event.dataTransfer.getData("text/action-id");
    // Convert to graph space first; the half-node offset (95, 46) is in graph units.
    const pointer = clientToGraph(event.clientX, event.clientY);
    const dropped = clampNodePosition(pointer.x - 95, pointer.y - 46);
    const position = { x: Math.round(dropped.x), y: Math.round(dropped.y) };
    if (actionId) addActionNode(actionId, position);
    else if (agentId) addAgent(agentId, position);
  });
  canvas.addEventListener("keydown", handleCanvasKeydown);
  // Focusing an off-screen node or port must never scroll the canvas: all
  // pointer math assumes the layers sit at the canvas origin.
  canvas.addEventListener("scroll", () => {
    if (canvas.scrollLeft || canvas.scrollTop) { canvas.scrollLeft = 0; canvas.scrollTop = 0; }
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape") { cancelConnection(); closeLanguageMenu(); }
    // Delete acts on the selection only when keyboard focus is not parked on a different node or edge.
    const focusedCanvasItem = document.activeElement?.closest?.(".workflow-node, .edge-group");
    const focusMatchesSelection = !focusedCanvasItem || (focusedCanvasItem.dataset.edgeId
      ? focusedCanvasItem.dataset.edgeId === state.selectedEdgeId
      : focusedCanvasItem.dataset.nodeId === state.selectedNodeId && !state.selectedEdgeId);
    if ((event.key === "Backspace" || event.key === "Delete") && canvasOwnsDeleteKey() && focusMatchesSelection && (state.selectedEdgeId || state.selectedNodeId)) {
      event.preventDefault();
      if (state.selectedEdgeId) $("#remove-edge").click();
      else if (state.selectedNodeId) $("#remove-node").click();
    }
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      if (state.section === "workflow") flushAutosaveKind("workflows").then(saved => toast(saved ? "Workflow 草稿已保存到 Studio" : "Workflow 草稿保存失败", !saved));
      else if (state.section === "agents") flushAutosaveKind("agents").then(saved => toast(saved ? "Agent 草稿已保存到 Studio" : "Agent 草稿保存失败", !saved));
      else if (state.section === "actions") flushAutosaveKind("actions").then(saved => toast(saved ? "Action 草稿已保存到 Studio" : "Action 草稿保存失败", !saved));
      else if (state.section === "skills") flushAutosaveKind("skills").then(saved => toast(saved ? "Skill 草稿已保存到 Studio" : "Skill 草稿保存失败", !saved));
      else if (state.section === "ai") publishAIDraft();
    }
  });
  let resizeFitTimer = null;
  window.addEventListener("resize", () => {
    clearTimeout(resizeFitTimer);
    resizeFitTimer = setTimeout(() => { if (!state.viewTouched) autoFitView(); }, 120);
  });
  window.addEventListener("pagehide", () => { void flushAutosaves(); });
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden") void flushAutosaves(); });
  let lastFocusImport = 0;
  window.addEventListener("focus", async () => {
    if (!state.project || !projectIsAuthorized(state.projects.find(item => item.id === state.project.id))) return;
    if (Date.now() - lastFocusImport < 1500) return;
    lastFocusImport = Date.now();
    await syncProject(state.project.id, { silent: true });
  });
  bindInspector();
}

bindEvents();
applyLanguage(state.language);
loadAIStatus();
loadProject();
loadOnboarding(true);
setInterval(loadAIStatus, 15000);
