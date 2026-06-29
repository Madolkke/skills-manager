<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { PublishRecord } from "../../types";
import { humanDate } from "../../lib/format";
import { pendingPublishRecords, selectedPendingRecords } from "../../lib/batchPublish";

const props = defineProps<{ records: PublishRecord[] }>();
const emit = defineEmits<{
  confirmRecord: [record: PublishRecord];
  cancelRecord: [record: PublishRecord];
  batchConfirm: [records: PublishRecord[]];
  batchCancel: [records: PublishRecord[]];
}>();

const statusFilter = ref("all");
const keyword = ref("");
const pageSize = ref(10);
const page = ref(1);
const expandedGroupKeys = ref<Set<string>>(new Set());
const selectedRecordIds = ref<Set<string>>(new Set());

type PublishRecordGroup = {
  key: string;
  skill: string;
  version: string;
  latestCreatedAt: string;
  records: PublishRecord[];
};

const statusOptions = [
  { value: "all", label: "全部" },
  { value: "pending_confirmation", label: "待确认" },
  { value: "released", label: "已发布" },
  { value: "cancelled", label: "已取消" },
  { value: "failed", label: "失败" },
];

const orderedRecords = computed(() => [...props.records].sort((a, b) => (b.created_at || "").localeCompare(a.created_at || "")));
const filteredRecords = computed(() => {
  const query = keyword.value.trim().toLowerCase();
  return orderedRecords.value.filter((record) => {
    const statusMatched = statusFilter.value === "all" || record.status === statusFilter.value;
    if (!statusMatched) return false;
    if (!query) return true;
    return searchText(record).includes(query);
  });
});
const groupedRecords = computed(() => groupRecords(filteredRecords.value));
const totalPages = computed(() => Math.max(1, Math.ceil(groupedRecords.value.length / pageSize.value)));
const pagedGroups = computed(() => groupedRecords.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value));
const pendingCount = computed(() => props.records.filter((record) => record.status === "pending_confirmation").length);
const releasedCount = computed(() => props.records.filter((record) => record.status === "released").length);
const visiblePendingRecords = computed(() => pendingPublishRecords(filteredRecords.value));
const selectedPending = computed(() => selectedPendingRecords(props.records, selectedRecordIds.value));
const allVisiblePendingSelected = computed(() => visiblePendingRecords.value.length > 0 && visiblePendingRecords.value.every((record) => selectedRecordIds.value.has(record.id)));
const rangeText = computed(() => {
  if (!groupedRecords.value.length) return "0 / 0";
  const start = (page.value - 1) * pageSize.value + 1;
  const end = Math.min(page.value * pageSize.value, groupedRecords.value.length);
  return `${start}-${end} / ${groupedRecords.value.length}`;
});

watch([groupedRecords, pageSize], () => {
  if (page.value > totalPages.value) page.value = totalPages.value;
});

watch([statusFilter, keyword], () => {
  page.value = 1;
});

watch(() => props.records, () => {
  selectedRecordIds.value = new Set([...selectedRecordIds.value].filter((id) => props.records.some((record) => record.id === id && record.status === "pending_confirmation")));
});

function groupRecords(records: PublishRecord[]): PublishRecordGroup[] {
  const groups = new Map<string, PublishRecordGroup>();
  for (const record of records) {
    const key = `${record.skill_id}:${record.skill_version_id}`;
    const group = groups.get(key) ?? {
      key,
      skill: skillText(record),
      version: versionText(record),
      latestCreatedAt: record.created_at || "",
      records: [],
    };
    group.records.push(record);
    if ((record.created_at || "") > group.latestCreatedAt) group.latestCreatedAt = record.created_at || "";
    groups.set(key, group);
  }
  return [...groups.values()]
    .map((group) => ({ ...group, records: [...group.records].sort((a, b) => (b.created_at || "").localeCompare(a.created_at || "")) }))
    .sort((a, b) => b.latestCreatedAt.localeCompare(a.latestCreatedAt));
}

function searchText(record: PublishRecord): string {
  return [
    record.skill?.slug,
    record.skill_id,
    record.skill_version?.version,
    record.skill_version_id,
    record.publish_target?.name,
    record.target_name,
    record.publish_target_id,
    record.status,
    record.created_by,
    record.confirmed_by,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function statusText(record: PublishRecord): string {
  if (record.status === "pending_confirmation") return "待确认";
  if (record.status === "released") return "已发布";
  if (record.status === "cancelled") return "已取消";
  return "失败";
}

function statusTone(record: PublishRecord): string {
  if (record.status === "released") return "positive";
  if (record.status === "pending_confirmation") return "neutral";
  if (record.status === "failed") return "negative";
  return "muted";
}

function skillText(record: PublishRecord): string {
  return record.skill?.slug ?? record.skill_id;
}

function versionText(record: PublishRecord): string {
  return record.skill_version?.version ?? record.skill_version_id;
}

function targetText(record: PublishRecord): string {
  return record.publish_target?.name ?? record.target_name ?? record.publish_target_id;
}

function confirmText(record: PublishRecord): string {
  if (record.confirmed_at) return `${humanDate(record.confirmed_at)} · ${record.confirmed_by || "-"}`;
  return "尚未确认";
}

function publishModeText(record: PublishRecord): string {
  return isAutoPublishRecord(record) ? "自动发布" : "人工确认";
}

function isAutoPublishRecord(record: PublishRecord): boolean {
  return record.confirmed_by === "system:auto_publish" || record.metadata?.auto_publish === true;
}

function failureText(record: PublishRecord): string {
  const error = record.metadata?.release_error;
  return typeof error === "string" && error ? error : "发布执行失败，请查看发布 hook 日志。";
}

function groupStatusText(group: PublishRecordGroup): string {
  const pending = group.records.filter((record) => record.status === "pending_confirmation").length;
  const released = group.records.filter((record) => record.status === "released").length;
  const failed = group.records.filter((record) => record.status === "failed").length;
  if (pending) return `${pending} 待确认`;
  if (failed) return `${failed} 失败`;
  if (released === group.records.length) return "全部已发布";
  return `${released} 已发布`;
}

function groupStatusTone(group: PublishRecordGroup): string {
  if (group.records.some((record) => record.status === "pending_confirmation")) return "neutral";
  if (group.records.some((record) => record.status === "failed")) return "negative";
  if (group.records.every((record) => record.status === "released")) return "positive";
  return "muted";
}

function groupTargetText(group: PublishRecordGroup): string {
  return group.records.map(targetText).join("、");
}

function isExpanded(group: PublishRecordGroup): boolean {
  return expandedGroupKeys.value.has(group.key);
}

function toggleGroup(group: PublishRecordGroup): void {
  const next = new Set(expandedGroupKeys.value);
  if (next.has(group.key)) next.delete(group.key);
  else next.add(group.key);
  expandedGroupKeys.value = next;
}

function setPage(nextPage: number): void {
  page.value = Math.min(Math.max(1, nextPage), totalPages.value);
}

function isSelected(record: PublishRecord): boolean {
  return selectedRecordIds.value.has(record.id);
}

function toggleRecord(record: PublishRecord): void {
  if (record.status !== "pending_confirmation") return;
  const next = new Set(selectedRecordIds.value);
  if (next.has(record.id)) next.delete(record.id);
  else next.add(record.id);
  selectedRecordIds.value = next;
}

function toggleGroupSelection(group: PublishRecordGroup): void {
  const pending = pendingPublishRecords(group.records);
  const next = new Set(selectedRecordIds.value);
  const allSelected = pending.length > 0 && pending.every((record) => next.has(record.id));
  for (const record of pending) {
    if (allSelected) next.delete(record.id);
    else next.add(record.id);
  }
  selectedRecordIds.value = next;
}

function toggleVisibleSelection(): void {
  const next = new Set(selectedRecordIds.value);
  for (const record of visiblePendingRecords.value) {
    if (allVisiblePendingSelected.value) next.delete(record.id);
    else next.add(record.id);
  }
  selectedRecordIds.value = next;
}

function emitBatchConfirm(): void {
  emit("batchConfirm", selectedPending.value);
  selectedRecordIds.value = new Set();
}

function emitBatchCancel(): void {
  emit("batchCancel", selectedPending.value);
  selectedRecordIds.value = new Set();
}
</script>

<template>
  <div class="admin-publish-layout">
    <aside class="primary-panel admin-card admin-publish-filter-panel">
      <div class="panel-title-row">
        <div>
          <h2>发布确认</h2>
          <p>按状态、Skill、版本或发布目标过滤记录。</p>
        </div>
      </div>
      <div class="admin-publish-filter-stack">
        <label class="field-label compact">
          <span>搜索</span>
          <input v-model="keyword" type="search" placeholder="Skill、版本、发布目标、提交人" />
        </label>
        <label class="field-label compact">
          <span>状态</span>
          <select v-model="statusFilter">
            <option v-for="option in statusOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
          </select>
        </label>
        <label class="field-label compact">
          <span>每页数量</span>
          <select v-model.number="pageSize">
            <option :value="5">5</option>
            <option :value="10">10</option>
            <option :value="20">20</option>
          </select>
        </label>
      </div>

      <div class="admin-publish-filter-stats">
        <div>
          <span>总记录</span>
          <strong>{{ records.length }}</strong>
        </div>
        <div>
          <span>待确认</span>
          <strong>{{ pendingCount }}</strong>
        </div>
        <div>
          <span>已发布</span>
          <strong>{{ releasedCount }}</strong>
        </div>
      </div>
      <div class="admin-publish-batch-box">
        <strong>{{ selectedPending.length }} 条已选择</strong>
        <p>只会批量处理待确认发布单。</p>
        <button class="secondary-button full-width" type="button" :disabled="!visiblePendingRecords.length" @click="toggleVisibleSelection">
          {{ allVisiblePendingSelected ? "取消选择当前筛选" : "选择当前筛选" }}
        </button>
        <button class="primary-button full-width" type="button" :disabled="!selectedPending.length" @click="emitBatchConfirm">批量确认</button>
        <button class="secondary-button full-width" type="button" :disabled="!selectedPending.length" @click="emitBatchCancel">批量取消</button>
      </div>
    </aside>

    <section class="primary-panel admin-card admin-publish-results-panel">
      <div class="panel-title-row">
        <div>
          <h2>发布记录</h2>
          <p>当前显示 {{ rangeText }} 个 Skill 版本分组</p>
        </div>
        <span class="tag-chip muted">{{ filteredRecords.length }} 条发布记录</span>
      </div>

      <TransitionGroup name="list-motion" tag="div" class="admin-publish-group-list">
        <article v-for="group in pagedGroups" :key="group.key" class="admin-publish-group">
          <div class="admin-publish-group-head">
            <label class="admin-publish-check" @click.stop>
              <input type="checkbox" :checked="pendingPublishRecords(group.records).length > 0 && pendingPublishRecords(group.records).every((record) => isSelected(record))" :disabled="pendingPublishRecords(group.records).length === 0" @change="toggleGroupSelection(group)" />
            </label>
            <button type="button" class="admin-publish-group-toggle" @click="toggleGroup(group)">
              <span class="admin-publish-group-caret">{{ isExpanded(group) ? "⌄" : "›" }}</span>
              <span class="admin-publish-record-main">
                <strong>{{ group.skill }}</strong>
                <span>{{ group.version }} · {{ group.records.length }} 条发布记录</span>
                <small>{{ groupTargetText(group) }}</small>
              </span>
              <span :class="['admin-publish-status', groupStatusTone(group)]">{{ groupStatusText(group) }}</span>
            </button>
          </div>

          <div v-if="isExpanded(group)" class="admin-publish-table">
            <div class="admin-publish-table-head">
              <span>选择</span>
              <span>发布记录</span>
              <span>状态</span>
              <span>确认信息</span>
              <span></span>
            </div>
            <TransitionGroup name="list-motion" tag="div" class="admin-publish-table-body">
              <div v-for="record in group.records" :key="record.id" class="admin-publish-table-row">
                <label class="admin-publish-check">
                  <input type="checkbox" :checked="isSelected(record)" :disabled="record.status !== 'pending_confirmation'" @change="toggleRecord(record)" />
                </label>
                <div class="admin-publish-record-main">
                  <strong>{{ targetText(record) }}</strong>
                  <span>{{ versionText(record) }}</span>
                  <small>提交 {{ humanDate(record.created_at) }} · {{ record.created_by }} · {{ publishModeText(record) }}</small>
                  <small v-if="record.status === 'failed'" class="admin-publish-error">{{ failureText(record) }}</small>
                </div>
                <span :class="['admin-publish-status', statusTone(record)]">{{ statusText(record) }}</span>
                <span class="admin-publish-confirm">{{ confirmText(record) }}</span>
                <div class="button-row admin-publish-actions">
                  <button v-if="record.status === 'pending_confirmation'" class="secondary-button" type="button" @click="emit('cancelRecord', record)">取消</button>
                  <button v-if="record.status === 'pending_confirmation'" class="primary-button" type="button" @click="emit('confirmRecord', record)">确认发布</button>
                </div>
              </div>
            </TransitionGroup>
          </div>
        </article>
        <p v-if="!pagedGroups.length" class="field-help admin-publish-empty">没有匹配的发布记录。</p>
      </TransitionGroup>

      <div class="admin-publish-pagination">
        <button class="secondary-button" type="button" :disabled="page <= 1" @click="setPage(page - 1)">上一页</button>
        <span>第 {{ page }} / {{ totalPages }} 页</span>
        <button class="secondary-button" type="button" :disabled="page >= totalPages" @click="setPage(page + 1)">下一页</button>
      </div>
    </section>
  </div>
</template>
