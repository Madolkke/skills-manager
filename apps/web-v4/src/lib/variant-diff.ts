import type { BundleFile } from "../types";

export type BundleDiffStatus = "added" | "changed" | "removed" | "unchanged";

export type BundleDiffFile = {
  path: string;
  status: BundleDiffStatus;
  current?: BundleFile;
  previous?: BundleFile;
};

export type BundleDiffSummary = {
  added: number;
  changed: number;
  removed: number;
  unchanged: number;
  total: number;
};

export type BundleDiffResult = {
  summary: BundleDiffSummary;
  files: BundleDiffFile[];
};

/**
 * Compares two immutable bundle file lists by path and stable file fingerprint.
 */
export function summarizeBundleDiff(currentFiles: BundleFile[] = [], previousFiles: BundleFile[] = []): BundleDiffResult {
  const currentByPath = indexByPath(currentFiles);
  const previousByPath = indexByPath(previousFiles);
  const paths = [...new Set([...currentByPath.keys(), ...previousByPath.keys()])];
  const files = paths.map((path) => {
    const current = currentByPath.get(path);
    const previous = previousByPath.get(path);
    return {
      path,
      status: diffStatus(current, previous),
      current,
      previous,
    };
  }).sort(compareDiffFiles);

  return {
    files,
    summary: {
      added: files.filter((file) => file.status === "added").length,
      changed: files.filter((file) => file.status === "changed").length,
      removed: files.filter((file) => file.status === "removed").length,
      unchanged: files.filter((file) => file.status === "unchanged").length,
      total: files.length,
    },
  };
}

function indexByPath(files: BundleFile[]): Map<string, BundleFile> {
  return new Map(files.map((file) => [file.path, file]));
}

function diffStatus(current?: BundleFile, previous?: BundleFile): BundleDiffStatus {
  if (current && !previous) return "added";
  if (!current && previous) return "removed";
  if (!current || !previous) return "unchanged";
  return fileFingerprint(current) === fileFingerprint(previous) ? "unchanged" : "changed";
}

function fileFingerprint(file: BundleFile): string {
  return file.sha256 ?? file.content_text ?? file.content_base64 ?? `${file.size_bytes ?? 0}:${file.binary ? "binary" : "text"}`;
}

function compareDiffFiles(left: BundleDiffFile, right: BundleDiffFile): number {
  const order: Record<BundleDiffStatus, number> = { changed: 0, added: 1, removed: 2, unchanged: 3 };
  return order[left.status] - order[right.status] || left.path.localeCompare(right.path);
}
