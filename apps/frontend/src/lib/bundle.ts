import type { BundleFile, BundleSource } from "../types";

export type BundleTreeFile = BundleFile & { id?: string };

export type BundleFolderNode = {
  type: "folder";
  name: string;
  path: string;
  children: BundleTreeNode[];
};

export type BundleTreeNode =
  | BundleFolderNode
  | {
    type: "file";
    name: string;
    path: string;
    file: BundleTreeFile;
  };

export async function sourceFromFiles(folderFiles: File[], zipFile?: File | null): Promise<BundleSource> {
  if (zipFile && folderFiles.length > 0) throw new Error("文件夹和 zip 只能选择一种。");
  if (zipFile) return { kind: "zip", name: zipFile.name.replace(/\.zip$/i, ""), zip_base64: await fileToBase64(zipFile) };
  if (folderFiles.length === 0) throw new Error("请选择包含 SKILL.md 的文件夹，或上传 zip。");
  return { kind: "files", name: rootName(folderFiles[0]), files: await Promise.all(folderFiles.map(filePayload)) };
}

export function groupBundleFiles(files: BundleTreeFile[]): Array<{ folder: string; files: BundleTreeFile[] }> {
  const groups = new Map<string, BundleTreeFile[]>();
  for (const file of files) {
    const parts = file.path.split("/");
    const folder = parts.length > 1 ? parts.slice(0, -1).join("/") : ".";
    groups.set(folder, [...(groups.get(folder) ?? []), file]);
  }
  return Array.from(groups, ([folder, folderFiles]) => ({ folder, files: folderFiles }));
}

export function buildBundleTree(files: BundleTreeFile[], rootLabel = "bundle"): BundleFolderNode {
  const rootName = cleanRootLabel(rootLabel);
  const root: BundleFolderNode = { type: "folder", name: rootName, path: rootName, children: [] };

  for (const file of files) {
    const parts = file.path.split("/").filter(Boolean);
    const visibleParts = parts[0] === rootName ? parts.slice(1) : parts;
    insertTreeFile(root, visibleParts.length ? visibleParts : [file.path], file);
  }

  sortTree(root);
  return root;
}

export function preferredBundleFile<T extends BundleTreeFile>(files: T[]): T | null {
  return files.find((file) => file.path.endsWith("SKILL.md")) ?? files.find((file) => !file.binary) ?? null;
}

function insertTreeFile(root: BundleFolderNode, parts: string[], file: BundleTreeFile): void {
  let current = root;
  let currentPath = root.path;

  for (const name of parts.slice(0, -1)) {
    currentPath = `${currentPath}/${name}`;
    const existing = current.children.find((node): node is BundleFolderNode => node.type === "folder" && node.name === name);
    if (existing) {
      current = existing;
      continue;
    }

    const folder: BundleTreeNode = { type: "folder", name, path: currentPath, children: [] };
    current.children.push(folder);
    current = folder;
  }

  current.children.push({
    type: "file",
    name: parts.at(-1) ?? file.path,
    path: file.path,
    file,
  });
}

function sortTree(node: BundleTreeNode): void {
  if (node.type !== "folder") return;
  node.children.sort((left, right) => {
    if (left.type !== right.type) return left.type === "file" ? -1 : 1;
    return left.name.localeCompare(right.name);
  });
  node.children.forEach(sortTree);
}

function cleanRootLabel(value: string): string {
  return value.replace(/\/+$/g, "") || "bundle";
}

export function bundleFileText(file?: BundleTreeFile | null): string {
  if (!file) return "选择左侧文件查看内容。";
  if (file.binary) return "这是二进制文件，暂不在页面内预览。";
  return file.content_text ?? "";
}

async function filePayload(file: File): Promise<{ path: string; content_text?: string; content_base64?: string }> {
  const path = (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;
  const bytes = new Uint8Array(await file.arrayBuffer());
  try {
    const text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
    if (!text.includes("\x00")) return { path, content_text: text };
  } catch {
    // 二进制文件转 base64，让后端保留完整 bundle。
  }
  return { path, content_base64: bytesToBase64(bytes) };
}

async function fileToBase64(file: File): Promise<string> {
  return bytesToBase64(new Uint8Array(await file.arrayBuffer()));
}

function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  for (let index = 0; index < bytes.length; index += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(index, index + 0x8000));
  }
  return btoa(binary);
}

function rootName(file: File): string {
  const path = (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;
  return path.split("/")[0]?.replace(/\.zip$/i, "") || "skill-bundle";
}
