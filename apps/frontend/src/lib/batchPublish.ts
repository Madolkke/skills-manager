import type { PublishRecord } from "../types";

export type BatchPublishSelection = {
  selectedIds: Set<string>;
};

export type BatchPublishResult = {
  total: number;
  succeeded: number;
  failed: number;
};

export function pendingPublishRecords(records: PublishRecord[]): PublishRecord[] {
  return records.filter((record) => record.status === "pending_confirmation");
}

export function selectedPendingRecords(records: PublishRecord[], selectedIds: Set<string>): PublishRecord[] {
  return pendingPublishRecords(records).filter((record) => selectedIds.has(record.id));
}

export function summarizeBatchResults(results: Array<{ ok: boolean }>): BatchPublishResult {
  return {
    total: results.length,
    succeeded: results.filter((item) => item.ok).length,
    failed: results.filter((item) => !item.ok).length,
  };
}
