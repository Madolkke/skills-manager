import JSZip from "jszip";

export const GENERATED_WORKSPACE_NAME = "workspace.generated.zip";

export type WorkspaceFileDraft = {
  id: string;
  path: string;
  content: string;
};

export type WorkspaceValidationResult = {
  valid: boolean;
  errors: Record<string, string>;
};

export function defaultWorkspaceFile(index = 0): WorkspaceFileDraft {
  return {
    id: `workspace-file-${Date.now()}-${index}`,
    path: index === 0 ? "README.md" : `file-${index + 1}.txt`,
    content: "",
  };
}

export function validateWorkspaceFiles(files: WorkspaceFileDraft[]): WorkspaceValidationResult {
  const errors: Record<string, string> = {};
  const seen = new Map<string, string>();
  for (const file of files) {
    const pathError = validateWorkspacePath(file.path);
    if (pathError) {
      errors[file.id] = pathError;
      continue;
    }
    const normalized = file.path.trim();
    const previous = seen.get(normalized);
    if (previous) {
      errors[file.id] = "文件路径重复。";
      errors[previous] = errors[previous] || "文件路径重复。";
      continue;
    }
    seen.set(normalized, file.id);
  }
  return { valid: Object.keys(errors).length === 0, errors };
}

export function validateWorkspacePath(path: string): string {
  const value = path.trim();
  if (!value) return "填写文件路径。";
  if (value.includes("\\") || value.includes("\0")) return "路径只能使用 / 分隔。";
  if (value.startsWith("/") || /^[A-Za-z]:/.test(value)) return "路径必须是相对路径。";
  const parts = value.split("/");
  if (parts.some((part) => !part || part === "." || part === "..")) return "路径不能包含空目录、. 或 ..。";
  return "";
}

export function workspaceDraftSize(files: WorkspaceFileDraft[]): number {
  const encoder = new TextEncoder();
  return files.reduce((total, file) => total + encoder.encode(file.content).length, 0);
}

export function formatWorkspaceSize(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

export async function workspaceFilesToBase64(files: WorkspaceFileDraft[]): Promise<string> {
  const validation = validateWorkspaceFiles(files);
  if (!validation.valid) throw new Error(Object.values(validation.errors)[0] || "工作区文件路径无效。");
  const zip = new JSZip();
  for (const file of files) {
    zip.file(file.path.trim(), file.content);
  }
  const base64 = await zip.generateAsync({ type: "base64", compression: "DEFLATE" });
  return base64;
}
