import type { BundleFile, BundleSource } from "../types";

export const SKILL_ENTRY_PATH = "SKILL.md";
export const SKILL_NAME_PATTERN = /^[a-z0-9][a-z0-9-]{0,63}$/;

export type BlankSkillDraft = {
  slug: string;
  description: string;
};

export type SkillBundleDraftFile = {
  id: string;
  path: string;
  binary: boolean;
  content_text?: string;
  content_base64?: string;
};

export type SkillBundleValidationResult = {
  valid: boolean;
  errors: Record<string, string>;
  globalErrors: string[];
};

export type BlankSkillValidationResult = {
  valid: boolean;
  errors: {
    slug?: string;
    description?: string;
  };
};

export function validateBlankSkillDraft(draft: BlankSkillDraft): BlankSkillValidationResult {
  const errors: BlankSkillValidationResult["errors"] = {};
  const slugError = validateSkillSlug(draft.slug);
  if (slugError) errors.slug = slugError;
  const description = normalizeSingleLine(draft.description);
  if (!description) errors.description = "填写 Skill 描述。";
  else if (description.length > 1024) errors.description = "Skill 描述最多 1024 个字符。";
  return { valid: Object.keys(errors).length === 0, errors };
}

export function validateSkillSlug(value: string): string {
  const slug = value.trim();
  if (!slug) return "填写 Skill ID。";
  if (!SKILL_NAME_PATTERN.test(slug)) return "只能使用小写字母、数字和连字符，且必须以字母或数字开头，最多 64 个字符。";
  return "";
}

export function createBlankSkillSource(draft: BlankSkillDraft): BundleSource {
  const validation = validateBlankSkillDraft(draft);
  if (!validation.valid) throw new Error(Object.values(validation.errors)[0] || "空白 Skill 信息不完整。");
  const slug = draft.slug.trim();
  const description = normalizeSingleLine(draft.description);
  return {
    kind: "files",
    name: slug,
    files: [
      {
        path: SKILL_ENTRY_PATH,
        content_text: `---\nname: ${slug}\ndescription: ${description}\n---\n\n# ${slug}\n`,
      },
    ],
  };
}

export function bundleFilesToDraftFiles(files: BundleFile[]): SkillBundleDraftFile[] {
  return files.map((file, index) => ({
    id: `bundle-file-${index}-${stableFileKey(file.path)}`,
    path: file.path,
    binary: Boolean(file.binary),
    content_text: file.binary ? undefined : file.content_text ?? "",
    content_base64: file.content_base64 ?? undefined,
  }));
}

export function defaultSkillBundleDraftFile(existingFiles: SkillBundleDraftFile[], preferredPath = "notes.md"): SkillBundleDraftFile {
  return {
    id: `bundle-file-new-${Date.now()}-${existingFiles.length}`,
    path: nextAvailablePath(existingFiles, preferredPath),
    binary: false,
    content_text: "",
  };
}

export function validateBundleDraftFiles(files: SkillBundleDraftFile[]): SkillBundleValidationResult {
  const errors: Record<string, string> = {};
  const globalErrors: string[] = [];
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
    if (file.binary && !file.content_base64) errors[file.id] = "二进制文件缺少原始内容，无法保存。";
  }

  const entry = files.find((file) => file.path.trim() === SKILL_ENTRY_PATH);
  if (!entry) globalErrors.push("必须保留根目录 SKILL.md。");
  else if (entry.binary) globalErrors.push("SKILL.md 必须是 UTF-8 文本文件。");
  else if (!entry.content_text?.trim()) globalErrors.push("SKILL.md 不能为空。");

  return { valid: Object.keys(errors).length === 0 && globalErrors.length === 0, errors, globalErrors };
}

export function validateBundlePath(path: string): string {
  const value = path.trim();
  if (!value) return "填写文件路径。";
  if (value.includes("\\") || value.includes("\0")) return "路径只能使用 / 分隔。";
  if (value.startsWith("/") || /^[A-Za-z]:/.test(value)) return "路径必须是相对路径。";
  const parts = value.split("/");
  if (parts.some((part) => !part || part === "." || part === "..")) return "路径不能包含空目录、. 或 ..。";
  return "";
}

export function buildBundleSourceFromDraftFiles(files: SkillBundleDraftFile[], name: string): BundleSource {
  const validation = validateBundleDraftFiles(files);
  if (!validation.valid) {
    throw new Error(validation.globalErrors[0] || Object.values(validation.errors)[0] || "Bundle 文件信息不完整。");
  }
  return {
    kind: "files",
    name,
    files: files.map((file) => {
      const path = file.path.trim();
      if (file.binary) return { path, content_base64: file.content_base64 ?? "" };
      return { path, content_text: file.content_text ?? "" };
    }),
  };
}

function nextAvailablePath(files: SkillBundleDraftFile[], preferredPath: string): string {
  const used = new Set(files.map((file) => file.path.trim()).filter(Boolean));
  if (!used.has(preferredPath)) return preferredPath;
  const dotIndex = preferredPath.lastIndexOf(".");
  const base = dotIndex > 0 ? preferredPath.slice(0, dotIndex) : preferredPath;
  const suffix = dotIndex > 0 ? preferredPath.slice(dotIndex) : "";
  for (let index = 2; index < 1000; index += 1) {
    const candidate = `${base}-${index}${suffix}`;
    if (!used.has(candidate)) return candidate;
  }
  return `new-file-${Date.now()}.md`;
}

function stableFileKey(path: string): string {
  return path.replace(/[^a-zA-Z0-9_-]+/g, "-").replace(/^-+|-+$/g, "") || "file";
}

function normalizeSingleLine(value: string): string {
  return value.trim().replace(/\s+/g, " ");
}
