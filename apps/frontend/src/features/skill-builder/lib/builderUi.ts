import DOMPurify, { type Config as DomPurifyConfig } from "dompurify";
import MarkdownIt from "markdown-it";
import type { DropdownSelectOption } from "../../../components/dropdown";
import {
  buildBundleSourceFromDraftFiles,
  type SkillBundleDraftFile,
  type SkillBundleValidationResult,
  validateBundleDraftFiles,
  validateBundlePath,
} from "../../../lib/skillBundleDraft";
import type { OpencodeProviderOption, SkillBuilderSession } from "../../../types";

export type BuilderSubmitFileMapping = {
  id: string;
  sourcePath: string;
  targetPath: string;
  selected: boolean;
  content_text: string;
};

export type BuilderProgressStep = {
  stage: string;
  label: string;
  state: "done" | "active" | "pending";
};

const builderProgressStages = [
  { stage: "queued", label: "排队中" },
  { stage: "claimed", label: "已认领" },
  { stage: "preparing_workspace", label: "准备工作区" },
  { stage: "checking_opencode", label: "检查 Opencode" },
  { stage: "creating_opencode_session", label: "创建会话" },
  { stage: "loading_message_history", label: "读取历史" },
  { stage: "sending_message", label: "等待模型返回" },
  { stage: "scanning_workspace", label: "扫描工作区" },
  { stage: "saving_result", label: "保存结果" },
];

const markdown = new MarkdownIt({
  breaks: true,
  html: false,
  linkify: true,
  typographer: false,
});
const defaultLinkOpenRenderer = markdown.renderer.rules.link_open;
const defaultValidateLink = markdown.validateLink;
const sanitizeConfig: DomPurifyConfig = {
  ADD_ATTR: ["target", "rel"],
  FORBID_TAGS: ["iframe", "object", "embed", "style"],
};

markdown.validateLink = (url) => {
  const normalized = url.trim().toLowerCase();
  if (normalized.startsWith("javascript:") || normalized.startsWith("vbscript:") || normalized.startsWith("data:")) return false;
  return defaultValidateLink.call(markdown, url);
};

markdown.renderer.rules.link_open = (tokens, index, options, env, self) => {
  const token = tokens[index];
  token.attrSet("target", "_blank");
  token.attrSet("rel", "noopener noreferrer");
  return defaultLinkOpenRenderer ? defaultLinkOpenRenderer(tokens, index, options, env, self) : self.renderToken(tokens, index, options);
};

/** 将消息文本渲染为已净化的 Markdown HTML。 */
export function renderMarkdown(source: string): string {
  const rendered = markdown.render(source || "");
  return sanitizeHtml(rendered);
}

/** 生成人类可读的模型等待耗时文案。 */
export function builderRunningElapsedLabel(startedAt?: string | null, now = Date.now()): string {
  if (!startedAt) return "正在等待模型返回";
  const timestamp = Date.parse(startedAt);
  if (Number.isNaN(timestamp)) return "正在等待模型返回";
  const elapsedSeconds = Math.max(0, Math.floor((now - timestamp) / 1000));
  if (elapsedSeconds < 5) return "刚刚开始";
  if (elapsedSeconds < 60) return `已等待 ${elapsedSeconds} 秒`;
  const minutes = Math.floor(elapsedSeconds / 60);
  const seconds = elapsedSeconds % 60;
  return seconds > 0 ? `已等待 ${minutes} 分 ${seconds} 秒` : `已等待 ${minutes} 分钟`;
}

export function builderSessionStatusText(session: SkillBuilderSession | null): string {
  if (!session) return "未选择会话";
  if (session.status === "running") return "Agent 正在处理";
  if (session.status === "draft_ready") return "工作区已更新";
  if (session.status === "created") return "Skill 已创建";
  if (session.status === "failed") return "执行失败";
  return "等待输入";
}

export function builderRecoveryNotice(session: SkillBuilderSession | null): { title: string; message: string; tone: "running" | "failed" } | null {
  if (!session) return null;
  if (session.status === "running") {
    return { title: "Agent 运行中", message: builderProgressStageText(session.run_progress?.stage || "queued"), tone: "running" };
  }
  const lastError = session.last_error?.trim();
  if (lastError) {
    return { title: "上次运行未完成", message: lastError, tone: "failed" };
  }
  return null;
}

export function builderProgressStageText(stage?: string | null): string {
  return builderProgressStages.find((item) => item.stage === stage)?.label ?? "处理中";
}

export function builderProgressSteps(session: SkillBuilderSession | null): BuilderProgressStep[] {
  if (session?.status !== "running") return [];
  const currentStage = session?.run_progress?.stage || (session?.status === "running" ? "queued" : "");
  const currentIndex = Math.max(0, builderProgressStages.findIndex((item) => item.stage === currentStage));
  return builderProgressStages.map((item, index) => ({
    ...item,
    state: index < currentIndex ? "done" : index === currentIndex ? "active" : "pending",
  }));
}

export function builderProviderOptions(providers: OpencodeProviderOption[]): DropdownSelectOption[] {
  return [
    { value: "", label: "使用 Opencode 默认模型", description: "不指定 provider/model" },
    ...providers.map((provider) => ({
      value: provider.id,
      label: provider.name,
      description: `${activeBuilderModels(provider).length} 个可用模型`,
    })),
  ];
}

export function builderModelOptions(providers: OpencodeProviderOption[], providerId?: string): DropdownSelectOption[] {
  const provider = providers.find((item) => item.id === providerId);
  return activeBuilderModels(provider).map((model) => ({
    value: model.id,
    label: model.name,
    description: [model.family, model.status].filter(Boolean).join(" · "),
  }));
}

export function activeBuilderProviders(providers: OpencodeProviderOption[]): OpencodeProviderOption[] {
  return providers.filter((provider) => activeBuilderModels(provider).length > 0);
}

export function activeBuilderModels(provider?: OpencodeProviderOption | null) {
  return (provider?.models ?? []).filter((model) => !model.status || model.status === "active");
}

export function defaultBuilderModelId(provider: OpencodeProviderOption): string {
  const models = activeBuilderModels(provider);
  const configured = models.find((model) => model.id === provider.default_model_id);
  return (configured ?? models[0]).id;
}

export function builderDraftFilesFromSession(session: SkillBuilderSession): SkillBundleDraftFile[] {
  return builderWorkspaceFilesFromSession(session);
}

export function builderWorkspaceFilesFromSession(session: SkillBuilderSession): SkillBundleDraftFile[] {
  return (session.workspace_files ?? session.draft_files).map((file, index) => ({
    id: `builder-workspace-${index}-${file.path.replace(/[^a-zA-Z0-9_-]+/g, "-")}`,
    path: file.path,
    binary: false,
    content_text: file.content_text,
  }));
}

export function builderDraftPayload(files: SkillBundleDraftFile[]) {
  buildBundleSourceFromDraftFiles(files, "builder-draft");
  return files.map((file) => ({ path: file.path.trim(), content_text: file.content_text ?? "" }));
}

export function validateBuilderWorkspaceFiles(files: SkillBundleDraftFile[]): SkillBundleValidationResult {
  const errors: Record<string, string> = {};
  const seen = new Map<string, string>();
  for (const file of files) {
    const pathError = validateBundlePath(file.path);
    if (pathError) {
      errors[file.id] = pathError;
      continue;
    }
    const path = file.path.trim();
    const previous = seen.get(path);
    if (previous) {
      errors[file.id] = "文件路径重复。";
      errors[previous] = errors[previous] || "文件路径重复。";
      continue;
    }
    seen.set(path, file.id);
    if (file.binary) errors[file.id] = "Builder 工作区只支持 UTF-8 文本文件。";
  }
  return { valid: Object.keys(errors).length === 0, errors, globalErrors: [] };
}

export function builderWorkspacePayload(files: SkillBundleDraftFile[]) {
  const validation = validateBuilderWorkspaceFiles(files);
  if (!validation.valid) throw new Error(Object.values(validation.errors)[0] || "工作区文件信息不完整。");
  return files.map((file) => ({ path: file.path.trim(), content_text: file.content_text ?? "" }));
}

export function builderSubmitMappingsFromFiles(files: SkillBundleDraftFile[]): BuilderSubmitFileMapping[] {
  return files.map((file) => ({
    id: file.id,
    sourcePath: file.path,
    targetPath: file.path,
    selected: true,
    content_text: file.content_text ?? "",
  }));
}

export function builderSubmitDraftFiles(mappings: BuilderSubmitFileMapping[]): SkillBundleDraftFile[] {
  return mappings
    .filter((item) => item.selected)
    .map((item, index) => ({
      id: `submit-${index}-${item.id}`,
      path: item.targetPath,
      binary: false,
      content_text: item.content_text,
    }));
}

export function validateBuilderSubmitMappings(mappings: BuilderSubmitFileMapping[]): SkillBundleValidationResult {
  const selected = builderSubmitDraftFiles(mappings);
  if (!selected.length) return { valid: false, errors: {}, globalErrors: ["至少选择一个工作区文件。"] };
  return validateBundleDraftFiles(selected);
}

export function builderSubmitPayloadFiles(mappings: BuilderSubmitFileMapping[]) {
  const files = builderSubmitDraftFiles(mappings);
  buildBundleSourceFromDraftFiles(files, "builder-submit");
  return files.map((file) => ({ path: file.path.trim(), content_text: file.content_text ?? "" }));
}

function sanitizeHtml(html: string): string {
  const purifier = DOMPurify as unknown as {
    sanitize?: (dirty: string, config?: DomPurifyConfig) => string;
    (window: Window): { sanitize: (dirty: string, config?: DomPurifyConfig) => string };
  };
  if (typeof purifier.sanitize === "function") return purifier.sanitize(html, sanitizeConfig);
  if (typeof window !== "undefined" && window.document && typeof purifier === "function") {
    return purifier(window).sanitize(html, sanitizeConfig);
  }
  return fallbackSanitize(html);
}

function fallbackSanitize(html: string): string {
  return html
    .replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, "")
    .replace(/<style[\s\S]*?>[\s\S]*?<\/style>/gi, "")
    .replace(/\son[a-z]+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)/gi, "")
    .replace(/\s(?:href|src)\s*=\s*(?:"\s*javascript:[^"]*"|'\s*javascript:[^']*'|\s*javascript:[^\s>]*)/gi, "");
}
