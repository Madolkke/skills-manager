export type BundleFile = {
  path: string;
  sha256?: string;
  size_bytes?: number;
  content_text?: string | null;
  content_base64?: string | null;
  binary?: boolean;
};

export type BundleDiffStatus = "added" | "changed" | "removed" | "unchanged";

export type BundleDiffLine = {
  kind: "context" | "added" | "removed";
  old_line: number | null;
  new_line: number | null;
  text: string;
};

export type BundleDiffFile = {
  path: string;
  status: BundleDiffStatus;
  binary: boolean;
  left_digest: string | null;
  right_digest: string | null;
  left_size_bytes: number | null;
  right_size_bytes: number | null;
  hunks?: Array<{
    lines: BundleDiffLine[];
  }>;
};

export type BundleDiff = {
  left: {
    skill_version_id: string;
    version_number: number;
    version: string;
    content_digest: string;
  };
  right: {
    skill_version_id: string;
    version_number: number;
    version: string;
    content_digest: string;
  };
  summary: {
    added: number;
    changed: number;
    removed: number;
    unchanged: number;
    binary: number;
  };
  files: BundleDiffFile[];
};

export type BundleSource =
  | { kind: "files"; name: string; files: Array<{ path: string; content_text?: string; content_base64?: string }> }
  | { kind: "zip"; name: string; zip_base64: string };
