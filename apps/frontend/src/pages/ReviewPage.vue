<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import DropdownSelect from "../components/DropdownSelect.vue";
import EmptyState from "../components/EmptyState.vue";
import type { DropdownSelectOption } from "../components/dropdown";
import { api, ApiError } from "../lib/api";
import { reviewManageReason } from "../lib/disabledReasons";
import { humanDate } from "../lib/format";
import type { PublishTarget, ReviewRequest, SkillDetail, ToastState } from "../types";

const props = defineProps<{ skill: SkillDetail }>();
const emit = defineEmits<{ toast: [toast: ToastState]; refresh: [] }>();

const loading = ref(false);
const busy = ref(false);
const reviews = ref<ReviewRequest[]>([]);
const targets = ref<PublishTarget[]>([]);
const selectedVersionId = ref(props.skill.skill.current_version_id ?? props.skill.versions[0]?.id ?? "");
const selectedTargets = ref<string[]>([]);

const canManage = computed(() => Boolean(props.skill.capabilities?.permissions["review.manage"]));
const manageReason = computed(() => reviewManageReason(canManage.value));
const versionOptions = computed<DropdownSelectOption[]>(() =>
  props.skill.versions.map((version) => ({
    value: version.id,
    label: version.version,
    description: version.display_name || version.change_summary,
  })),
);
const orderedReviews = computed(() => [...reviews.value].sort((a, b) => (b.created_at || "").localeCompare(a.created_at || "")));
const openReviews = computed(() => orderedReviews.value.filter((review) => review.status === "open"));
const closedReviews = computed(() => orderedReviews.value.filter((review) => review.status === "closed"));
const selectedVersion = computed(() => props.skill.versions.find((version) => version.id === selectedVersionId.value) ?? null);

onMounted(() => void load());

async function load(): Promise<void> {
  loading.value = true;
  try {
    const [nextReviews, publish] = await Promise.all([api.listSkillReviews(props.skill.skill.id), api.getSkillPublishOverview(props.skill.skill.id)]);
    reviews.value = nextReviews;
    targets.value = publish.publish_targets.filter((target) => target.enabled);
  } catch (error) {
    showError(error);
  } finally {
    loading.value = false;
  }
}

async function createReview(): Promise<void> {
  if (!selectedVersionId.value) return;
  busy.value = true;
  try {
    await api.createReviewRequest(props.skill.skill.id, {
      skill_version_id: selectedVersionId.value,
      publish_targets: selectedTargets.value.map((publish_target_id) => ({ publish_target_id, auto_submit_on_pass: true })),
    });
    emit("toast", { tone: "success", message: "评审已发起。" });
    selectedTargets.value = [];
    await load();
  } catch (error) {
    showError(error);
  } finally {
    busy.value = false;
  }
}

async function closeReview(review: ReviewRequest): Promise<void> {
  if (!confirm("关闭评审后将锁定评分，并按门禁检查自动提交待确认发布单。是否继续？")) return;
  busy.value = true;
  try {
    await api.closeReview(review.id);
    emit("toast", { tone: "success", message: "评审已关闭。" });
    emit("refresh");
    await load();
  } catch (error) {
    showError(error);
  } finally {
    busy.value = false;
  }
}

function toggleTarget(targetId: string): void {
  selectedTargets.value = selectedTargets.value.includes(targetId)
    ? selectedTargets.value.filter((id) => id !== targetId)
    : [...selectedTargets.value, targetId];
}

function responseCount(review: ReviewRequest): string {
  return `${review.responses.length} / ${review.reviewers.length}`;
}

function autoTargetText(review: ReviewRequest): string {
  const names = review.publish_targets.filter((item) => item.auto_submit_on_pass).map((item) => item.name);
  return names.length ? names.join("、") : "未设置";
}

function reviewerText(review: ReviewRequest): string {
  return review.reviewers.map((item) => item.reviewer_actor).join("、") || "无";
}

function reviewStatusText(review: ReviewRequest): string {
  if (review.status === "open") return "进行中";
  if (review.status === "closed") return "已关闭";
  return "已取消";
}

function scoreLabel(score: -1 | 0 | 1): string {
  if (score === 1) return "+1 通过";
  if (score === 0) return "0 保留";
  return "-1 不通过";
}

function scoreTone(score: -1 | 0 | 1): string {
  if (score === 1) return "positive";
  if (score === 0) return "neutral";
  return "negative";
}

function showError(error: unknown): void {
  emit("toast", { tone: "danger", message: error instanceof ApiError || error instanceof Error ? error.message : "操作失败。" });
}
</script>

<template>
  <div class="review-page review-manager-page">
    <section class="primary-panel review-hero review-manager-hero">
      <div>
        <span class="section-kicker">评审</span>
        <h1>版本评审</h1>
        <p>针对特定 Skill 版本发起评审，评审人来自 reviewer 角色授权快照。</p>
      </div>
      <div class="review-manager-hero-actions">
        <span class="tag-chip">{{ orderedReviews.length }} 条评审记录</span>
        <button class="secondary-button" type="button" :disabled="loading" @click="load">{{ loading ? "刷新中..." : "刷新" }}</button>
      </div>
    </section>

    <section class="review-manager-summary" aria-label="评审概览">
      <div class="primary-panel review-manager-stat">
        <span>进行中</span>
        <strong>{{ openReviews.length }}</strong>
      </div>
      <div class="primary-panel review-manager-stat">
        <span>已关闭</span>
        <strong>{{ closedReviews.length }}</strong>
      </div>
      <div class="primary-panel review-manager-stat">
        <span>启用发布源</span>
        <strong>{{ targets.length }}</strong>
      </div>
      <div class="primary-panel review-manager-stat wide">
        <span>当前选择版本</span>
        <strong>{{ selectedVersion?.version || "未选择" }}</strong>
      </div>
    </section>

    <section class="review-manager-layout">
      <aside class="primary-panel review-launch-panel">
        <div class="review-panel-head">
          <div>
            <h2>发起评审</h2>
            <p>选择版本和自动提交发布源。</p>
          </div>
        </div>

        <div v-if="canManage" class="review-launch-form">
          <label class="field-label">
            <span>Skill 版本</span>
            <DropdownSelect v-model="selectedVersionId" :options="versionOptions" compact />
          </label>

          <div v-if="selectedVersion" class="review-selected-version">
            <span>将评审</span>
            <strong>{{ selectedVersion.version }}</strong>
            <p>{{ selectedVersion.display_name || selectedVersion.change_summary || "当前版本没有备注。" }}</p>
          </div>

          <div class="field-label">
            <span>自动提交发布源</span>
            <div class="review-target-list">
              <button
                v-for="target in targets"
                :key="target.id"
                type="button"
                :class="['review-target-row', { active: selectedTargets.includes(target.id) }]"
                @click="toggleTarget(target.id)"
              >
                <span class="review-target-main">
                  <strong>{{ target.name }}</strong>
                  <small>{{ target.description || target.target_key }}</small>
                </span>
                <span class="review-target-state">{{ selectedTargets.includes(target.id) ? "已选" : "可选" }}</span>
              </button>
              <span v-if="!targets.length" class="field-help">后台还没有启用的发布源。</span>
            </div>
          </div>

          <button class="primary-button full-width" type="button" :disabled="busy || !selectedVersionId" :title="manageReason || (!selectedVersionId ? '需要先选择一个 Skill 版本。' : '')" @click="createReview">发起评审</button>
        </div>
        <p v-else class="field-help permission-hint review-launch-permission">当前身份需要 maintainer、owner 或 admin 才能发起评审。</p>
      </aside>

      <section class="primary-panel review-records-panel">
        <div class="review-panel-head">
          <div>
            <h2>评审记录</h2>
            <p>查看每次评审的评审人、回复和关闭后的门禁结果。</p>
          </div>
          <span class="tag-chip muted">{{ orderedReviews.length }} 条</span>
        </div>

        <div class="review-record-list">
          <article v-for="review in orderedReviews" :key="review.id" class="review-record-card">
            <div class="review-record-card-head">
              <div>
                <span class="review-record-version">版本 {{ review.skill_version.version }}</span>
                <h3>{{ reviewStatusText(review) }}</h3>
                <p>发起 {{ humanDate(review.created_at) }} · 发起人 {{ review.created_by }}</p>
              </div>
              <span :class="['tag-chip', review.status === 'open' ? '' : 'muted']">{{ reviewStatusText(review) }}</span>
            </div>

            <div class="review-record-metrics">
              <div>
                <span>回复进度</span>
                <strong>{{ responseCount(review) }}</strong>
              </div>
              <div>
                <span>评审人</span>
                <strong>{{ reviewerText(review) }}</strong>
              </div>
              <div>
                <span>自动发布源</span>
                <strong>{{ autoTargetText(review) }}</strong>
              </div>
            </div>

            <div v-if="review.check_results.length" class="review-check-grid">
              <span v-for="check in review.check_results" :key="check.check_id" :class="['review-check-chip', { passed: check.passed, failed: !check.passed }]">
                {{ check.label || check.check_id }} · {{ check.passed ? "通过" : "未通过" }}
              </span>
            </div>

            <div class="review-response-list review-record-response-list">
              <div v-for="response in review.responses" :key="response.reviewer_actor" class="review-response-row review-record-response-row">
                <strong>{{ response.reviewer_actor }}</strong>
                <span :class="['my-review-score-pill', scoreTone(response.score)]">{{ scoreLabel(response.score) }}</span>
                <p>{{ response.comment || "未填写意见" }}</p>
              </div>
              <div v-if="!review.responses.length" class="review-record-empty">还没有评审人提交反馈。</div>
            </div>

            <div v-if="review.status === 'open' && canManage" class="button-row review-record-actions">
              <button class="primary-button" type="button" :disabled="busy" :title="busy ? '正在处理上一项操作，请稍候。' : ''" @click="closeReview(review)">结束评审</button>
            </div>
          </article>

          <EmptyState
            v-if="!orderedReviews.length"
            title="还没有评审记录"
            description="发起一次版本评审后，评审进度、反馈和门禁结果会出现在这里。"
            :action-label="canManage ? '发起评审' : undefined"
            @action="createReview"
          />
        </div>
      </section>
    </section>
  </div>
</template>
