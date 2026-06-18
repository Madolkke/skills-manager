export type ContentRef = {
  kind: string;
  locator: string;
  digest: string;
  path?: string | null;
};

export type SessionInfo = {
  actor: string;
  subject_type: string;
};

export type ArtifactRef = {
  id: string;
  kind: string;
  namespace: string;
  locator: string;
  digest: string;
  media_type: string;
  size_bytes: number;
  content_text?: string | null;
  created_at?: string;
  created_by: string;
};
