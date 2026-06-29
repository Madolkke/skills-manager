<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import EmptyState from "../components/EmptyState.vue";
import { api, ApiError } from "../lib/api";
import { publishRequestReason } from "../lib/disabledReasons";
import { humanDate } from "../lib/format";
import type { PublishRecord, PublishTarget, ReviewRequest, SkillDetail, SkillPublishOverview, ToastState } from "../types";

const props = defineProps<{ skill: SkillDetail }>();
const emit = defineEmits<{ toast: [toast: ToastState] }>();

const loading = ref(false);
const busy = ref(false);
const overview = ref<SkillPublishOverview | null>(null);
const expandedGroupKeys = ref<Set<string>>(new Set());

type PublishRecordGroup = {
  key: string;
  version: string;
  latestCreatedAt: string;
  records: PublishRecord[];
};

const canRequestPublish = computed(() => Boolean(props.skill.capabilities?.permissions["publish.request"]));
const versions = computed(() => overview.value?.versions ?? []);
const targets = computed(() => (overview.value?.publish_targets ?? []).filter((target) => target.enabled));
const records = computed(() => overview.value?.publish_records ?? []);
const selectedRecordId = ref("");
const closedReviewCount = computed(() => versions.value.filter((item) => item.review?.status === "closed").length);
const pendingRecordCount = computed(() => records.value.filter((record) => record.status === "pending_confirmation").length);
const releasedRecordCount = computed(() => records.value.filter((record) => record.status === "released").length);
const orderedRecords = computed(() => [...records.value].sort((a, b) => (b.created_at || "").localeCompare(a.created_at || "")));
const groupedRecords = computed(() => groupRecords(orderedRecords.value));
const selectedRecord = computed(() => orderedRecords.value.find((record) => record.id === selectedRecordId.value) ?? orderedRecords.value[0] ?? null);
const publishCandidates = computed(() =>
  versions.value.flatMap((item) => {
    if (!item.review || item.review.status !== "closed") return [];
    return targets.value
      .filter((target) => !target.auto_publish_enabled)
      .filter((target) => canSubmit(item.review, target))
      .map((target) => ({
        id: `${item.version.id}:${target.id}`,
        version: item.version,
        review: item.review as ReviewRequest,
        target,
      }));
  }),
);

onMounted(() => void load());

async function load(): Promise<void> {
  const previousSelection = selectedRecordId.value;
  loading.value = true;
  try {
    overview.value = await api.getSkillPublishOverview(props.skill.skill.id);
    selectedRecordId.value = records.value.some((record) => record.id === previousSelection) ? previousSelection : orderedRecords.value[0]?.id ?? "";
  } catch (error) {
    showError(error);
  } finally {
    loading.value = false;
  }
}

async function requestPublish(review: ReviewRequest, target: PublishTarget): Promise<void> {
  busy.value = true;
  try {
    const record = await api.createPublishRecord(props.skill.skill.id, {
      skill_version_id: review.skill_version_id,
      review_request_id: review.id,
      publish_target_id: target.id,
    });
    selectedRecordId.value = record.id;
    emit("toast", { tone: "success", message: "已提交后台待确认发布单。" });
    await load();
    selectedRecordId.value = record.id;
  } catch (error) {
    showError(error);
  } finally {
    busy.value = false;
  }
}

function recordStatusText(record: PublishRecord): string {
  if (record.status === "pending_confirmation") return "待后台确认";
  if (record.status === "released") return "已发布";
  if (record.status === "cancelled") return "已取消";
  return "发布失败";
}

function recordStatusTone(record?: PublishRecord): string {
  if (!record) return "muted";
  if (record.status === "released") return "positive";
  if (record.status === "pending_confirmation") return "neutral";
  if (record.status === "failed") return "negative";
  return "muted";
}

function groupRecords(items: PublishRecord[]): PublishRecordGroup[] {
  const groups = new Map<string, PublishRecordGroup>();
  for (const record of items) {
    const key = `${record.skill_id}:${record.skill_version_id}`;
    const group = groups.get(key) ?? {
      key,
      version: recordVersionText(record),
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

function selectRecord(record: PublishRecord): void {
  selectedRecordId.value = record.id;
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

function recordSequence(record: PublishRecord): number {
  const chronological = [...records.value].sort((a, b) => (a.created_at || "").localeCompare(b.created_at || ""));
  return chronological.findIndex((item) => item.id === record.id) + 1;
}

function recordVersionText(record: PublishRecord): string {
  const version = record.skill_version?.version ?? versions.value.find((item) => item.version.id === record.skill_version_id)?.version.version;
  return version || record.skill_version_id;
}

function recordCreatedText(record: PublishRecord): string {
  return humanDate(record.created_at);
}

function recordConfirmText(record: PublishRecord): string {
  if (record.confirmed_at) return `${humanDate(record.confirmed_at)} · ${record.confirmed_by || "-"}`;
  return "尚未确认";
}

function recordPublishModeText(record: PublishRecord): string {
  return record.confirmed_by === "system:auto_publish" || record.metadata?.auto_publish === true ? "自动发布" : "人工确认";
}

function recordFailureText(record: PublishRecord): string {
  const error = record.metadata?.release_error;
  return typeof error === "string" && error ? error : "发布执行失败，请联系后台管理员。";
}

function recordTargetText(record: PublishRecord): string {
  return record.publish_target?.name ?? record.target_name ?? record.publish_target_id;
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

function groupTargetsText(group: PublishRecordGroup): string {
  return group.records.map(recordTargetText).join("、");
}

function recordReview(record: PublishRecord): ReviewRequest | null {
  return record.review ?? versions.value.find((item) => item.review?.id === record.review_request_id)?.review ?? null;
}

function reviewStatusText(review: ReviewRequest | null): string {
  if (!review) return "未评审";
  if (review.status === "closed") return "评审已关闭";
  if (review.status === "open") return "评审中";
  return "评审已取消";
}

function reviewMetaText(review: ReviewRequest | null): string {
  if (!review) return "需要先在评审 Tab 发起并关闭评审。";
  const closed = review.closed_at ? ` · 关闭 ${humanDate(review.closed_at)}` : "";
  return `回复 ${review.responses.length} / ${review.reviewers.length}${closed}`;
}

function checkSummary(review: ReviewRequest | null): string {
  if (!review?.check_results.length) return "暂无门禁结果";
  const passed = review.check_results.filter((check) => check.passed).length;
  return `${passed} / ${review.check_results.length} 通过`;
}

function candidateHint(review: ReviewRequest): string {
  return publishRequestReason({ canRequest: canRequestPublish.value, reviewClosed: review.status === "closed" }) || "可提交后台确认";
}

function canSubmit(review: ReviewRequest | null, target: PublishTarget): boolean {
  if (!review || review.status !== "closed") return false;
  return !records.value.some((item) => item.skill_version_id === review.skill_version_id && item.publish_target_id === target.id);
}

function candidateDisabledReason(review: ReviewRequest, target: PublishTarget): string {
  return publishRequestReason({
    canRequest: canRequestPublish.value,
    reviewClosed: review.status === "closed",
    duplicate: records.value.some((item) => item.skill_version_id === review.skill_version_id && item.publish_target_id === target.id),
  });
}

function showError(error: unknown): void {
  emit("toast", { tone: "danger", message: error instanceof ApiError || error instanceof Error ? error.message : "操作失败。" });
}
</script>

<template>
  <div class="review-page publish-page">
    <section class="primary-panel review-hero publish-hero">
      <div>
        <span class="section-kicker">发布</span>
        <h1>发布门禁与确认单</h1>
        <p>通过评审后提交后台待确认发布单，真实发布由后台管理员确认。</p>
      </div>
      <div class="publish-hero-actions">
        <span class="tag-chip">{{ records.length }} 条发布记录</span>
        <button class="secondary-button" type="button" :disabled="loading" @click="load">{{ loading ? "刷新中..." : "刷新" }}</button>
      </div>
    </section>

    <section class="publish-summary" aria-label="发布概览">
      <div class="primary-panel publish-stat">
        <span>Skill 版本</span>
        <strong>{{ versions.length }}</strong>
      </div>
      <div class="primary-panel publish-stat">
        <span>已关闭评审</span>
        <strong>{{ closedReviewCount }}</strong>
      </div>
      <div class="primary-panel publish-stat">
        <span>待后台确认</span>
        <strong>{{ pendingRecordCount }}</strong>
      </div>
      <div class="primary-panel publish-stat wide">
        <span>发布记录</span>
        <strong>{{ releasedRecordCount }} 条已发布 · {{ records.length }} 条总记录</strong>
      </div>
    </section>

    <section class="publish-record-layout">
      <aside class="primary-panel publish-record-sidebar">
        <div class="publish-panel-head">
          <div>
            <h2>发布记录</h2>
            <p>按 Skill 版本聚合，展开后选择具体发布记录。</p>
          </div>
        </div>
        <div class="publish-record-list">
          <article v-for="group in groupedRecords" :key="group.key" class="publish-record-group">
            <button type="button" class="publish-record-group-head" @click="toggleGroup(group)">
              <span class="publish-record-caret">{{ isExpanded(group) ? "⌄" : "›" }}</span>
              <span class="publish-record-main">
                <strong>{{ group.version }}</strong>
                <small>{{ group.records.length }} 条发布记录 · {{ groupTargetsText(group) }}</small>
              </span>
              <span :class="['publish-status-pill compact', groupStatusTone(group)]">{{ groupStatusText(group) }}</span>
            </button>
            <div v-if="isExpanded(group)" class="publish-record-group-body">
              <button
                v-for="record in group.records"
                :key="record.id"
                type="button"
                :class="['publish-record-item nested', { active: selectedRecord?.id === record.id }]"
                @click="selectRecord(record)"
              >
                <span class="publish-record-index">#{{ recordSequence(record) }}</span>
                <span class="publish-record-main">
                  <strong>{{ recordTargetText(record) }}</strong>
                  <small>{{ recordStatusText(record) }} · {{ recordCreatedText(record) }}</small>
                </span>
                <span :class="['publish-status-pill compact', recordStatusTone(record)]">{{ recordStatusText(record) }}</span>
              </button>
            </div>
          </article>
          <EmptyState
            v-if="!groupedRecords.length"
            title="还没有发布记录"
            description="评审通过并关闭后，可以提交后台待确认发布单。"
          />
        </div>

        <div v-if="publishCandidates.length" class="publish-candidate-list">
          <span class="publish-candidate-title">可提交确认单</span>
          <button
            v-for="candidate in publishCandidates"
            :key="candidate.id"
            class="publish-candidate-item"
            type="button"
            :disabled="busy || !canRequestPublish"
            :title="candidateDisabledReason(candidate.review, candidate.target)"
            @click="requestPublish(candidate.review, candidate.target)"
          >
            <span>
              <strong>{{ candidate.version.version }}</strong>
              <small>{{ candidateHint(candidate.review) }}</small>
            </span>
            <b>提交</b>
          </button>
        </div>
      </aside>

      <section class="primary-panel publish-record-detail-panel">
        <template v-if="selectedRecord">
          <div class="publish-panel-head">
            <div>
              <h2>发布记录 #{{ recordSequence(selectedRecord) }}</h2>
              <p>{{ recordVersionText(selectedRecord) }} · {{ recordCreatedText(selectedRecord) }}</p>
            </div>
            <span :class="['publish-status-pill', recordStatusTone(selectedRecord)]">{{ recordStatusText(selectedRecord) }}</span>
          </div>

          <div class="publish-record-detail">
            <div class="publish-record-meta">
              <div>
                <span>Skill 版本</span>
                <strong>{{ recordVersionText(selectedRecord) }}</strong>
              </div>
              <div>
                <span>创建时间</span>
                <strong>{{ recordCreatedText(selectedRecord) }}</strong>
              </div>
              <div>
                <span>提交人</span>
                <strong>{{ selectedRecord.created_by }}</strong>
              </div>
              <div>
                <span>后台确认</span>
                <strong>{{ recordConfirmText(selectedRecord) }}</strong>
              </div>
              <div>
                <span>发布方式</span>
                <strong>{{ recordPublishModeText(selectedRecord) }}</strong>
              </div>
            </div>

            <section class="publish-record-section">
              <div class="publish-record-section-head">
                <h3>关联评审</h3>
                <span class="tag-chip muted">{{ reviewStatusText(recordReview(selectedRecord)) }}</span>
              </div>
              <div class="publish-record-meta two">
                <div>
                  <span>评审进度</span>
                  <strong>{{ reviewMetaText(recordReview(selectedRecord)) }}</strong>
                </div>
                <div>
                  <span>门禁结果</span>
                  <strong>{{ checkSummary(recordReview(selectedRecord)) }}</strong>
                </div>
              </div>
            </section>

            <section class="publish-record-section">
              <div class="publish-record-section-head">
                <h3>门禁快照</h3>
                <span class="tag-chip muted">{{ selectedRecord.check_snapshot.length }} 项</span>
              </div>
              <div v-if="selectedRecord.check_snapshot.length" class="review-check-grid">
                <span
                  v-for="check in selectedRecord.check_snapshot"
                  :key="check.check_id"
                  :class="['review-check-chip', { passed: check.passed, failed: !check.passed }]"
                >
                  {{ check.label || check.check_id }} · {{ check.passed ? "通过" : "未通过" }}
                </span>
              </div>
              <div v-else class="publish-empty-box">这条发布记录没有保存门禁快照。</div>
            </section>

            <section class="publish-record-section">
              <div class="publish-record-section-head">
                <h3>后台状态</h3>
              </div>
              <div class="publish-record-meta two">
                <div>
                  <span>当前状态</span>
                  <strong>{{ recordStatusText(selectedRecord) }}</strong>
                </div>
                <div>
                  <span>发布结果</span>
                  <strong>{{ selectedRecord.status === "released" ? "后台已确认发布" : selectedRecord.status === "pending_confirmation" ? "等待后台确认" : recordStatusText(selectedRecord) }}</strong>
                </div>
                <div v-if="selectedRecord.status === 'failed'">
                  <span>失败原因</span>
                  <strong>{{ recordFailureText(selectedRecord) }}</strong>
                </div>
              </div>
            </section>
          </div>
        </template>

        <EmptyState
          v-else
          title="还没有发布记录"
          description="评审关闭后提交后台确认单，发布记录会出现在这里。"
        />
      </section>
    </section>

    <section v-if="versions.length" class="primary-panel publish-version-strip">
      <div class="publish-panel-head">
        <div>
          <h2>版本状态</h2>
          <p>用于判断哪些版本已完成评审并可提交发布记录。</p>
        </div>
        <span class="tag-chip muted">{{ versions.length }} 个版本</span>
      </div>
      <div class="publish-version-strip-list">
        <article v-for="item in versions" :key="item.version.id" class="publish-version-mini-card">
          <div>
            <strong>{{ item.version.version }}</strong>
            <p>{{ item.version.display_name || item.version.change_summary || "当前版本没有备注。" }}</p>
          </div>
          <div class="publish-version-mini-meta">
            <span :class="['tag-chip', item.review?.status === 'closed' ? '' : 'muted']">{{ reviewStatusText(item.review) }}</span>
            <small>{{ checkSummary(item.review) }}</small>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>
