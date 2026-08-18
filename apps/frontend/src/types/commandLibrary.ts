export type CommandLibrarySample = {
  id: string;
  name: string;
  command: string;
  stdout: string;
};

export type CommandLibrarySearchResult = {
  id: string;
  source: "system" | "user";
  key: string;
  name?: string;
  description?: string;
  expression: string;
  normalizedExpression?: string;
  metadata: Record<string, unknown>;
  versions?: string[];
  samples?: CommandLibrarySample[];
  outputSchema?: Record<string, unknown>;
  ttp?: string;
  enabled?: boolean;
  complete?: boolean;
  captures?: Record<string, unknown>;
  alternatives?: Array<Record<string, unknown>>;
  alternativeIndex?: number;
  captureSchema?: Record<string, unknown>;
  consumedTokens?: number;
  nextTokens?: string[];
  ambiguous?: boolean;
  collectionDefinitionId?: string | null;
  collectionRevision?: number | null;
  sourceSystemCommandId?: string | null;
};

export type SystemCommand = CommandLibrarySearchResult & {
  source: "system";
  createdAt?: string;
  updatedAt?: string;
};
