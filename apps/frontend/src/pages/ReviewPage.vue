<script setup lang="ts">
import type { SkillCore } from "../lib/api/paginationApi";

import { computed, nextTick, onMounted, ref, watch, toRefs } from "vue";
import { Copy } from "lucide-vue-next";
import EmptyState from "../components/EmptyState.vue";
import { api, ApiError } from "../lib/api";
import { reviewManageReason } from "../lib/disabledReasons";
import { humanDate } from "../lib/format";
import { reviewShareUrl } from "../lib/navigation";
import { buildReviewerSources, selectedReviewerCount } from "../lib/reviewerSelection";
import type { PublishTarget, ReviewerCandidateOverview, ReviewRequest, ToastState } from "../types";
import { useListFilters } from "../composables/useListFilters";
import PaginationBar from "../components/PaginationBar.vue";
import { usePagedQuery } from "../composables/usePagedQuery";
import { paginationApi, type ReviewSummary } from "../lib/api/paginationApi";
import { responseCount, autoTargetText, reviewerText, reviewStatusText, scoreLabel, scoreTone } from "./review/reviewLabels";
import ReviewLaunchPanel from "./review/ReviewLaunchPanel.vue";

const props = defineProps<{ skill: SkillCore; selectedReviewId: string | null }>();
const emit = defineEmits<{ toast: [toast: ToastState]; refresh: [] }>();

const loading = ref(false);
const busy = ref(false);
const details = ref<Record<string, ReviewRequest>>({});
const { status } = toRefs(useListFilters("reviews", { status: "" }));
const targets = ref<PublishTarget[]>([]);
const reviewerCandidates = ref<ReviewerCandidateOverview | null>(null);
const selectedVersionId = ref(props.skill.skill.current_version_id ?? props.skill.highest_version?.id ?? "");
const selectedTargets = ref<string[]>([]);
const selectedReviewerGroupIds = ref<string[]>([]);
const directReviewerInput = ref("");

const canManage = computed(() => Boolean(props.skill.capabilities?.permissions["review.manage"]));
const manageReason = computed(() => reviewManageReason(canManage.value));
const { page, pageSize, items: summaries, total, loading: listLoading, error: listError, reload, result } = usePagedQuery("reviews",
  () => ({ status: status.value, skill: props.skill.skill.id }),
  (params, signal) => paginationApi.reviews(props.skill.skill.id, { page: params.page, page_size: params.page_size, status: params.status }, signal));
const selectedVersion = ref(props.skill.summary.current_version);
const orderedReviews = computed(() => summaries.value);
const counts = computed(() => result.value?.counts ?? {});
const focusedDetail = ref<ReviewRequest | null>(null);
const focusedError = ref("");
const focusedRetry = ref(0);
async function expandReview(review: ReviewSummary) {
  try { details.value[review.id] = await paginationApi.review(review.id); }
  catch (caught) { showError(caught); }
}
watch([() => props.selectedReviewId, focusedRetry], async ([id], _, cleanup) => {
  const controller = new AbortController(); cleanup(() => controller.abort()); focusedDetail.value = null;
  focusedError.value = "";
  if (!id) return;
  try { const detail = await paginationApi.review(id, controller.signal); if (!controller.signal.aborted) { focusedDetail.value = detail; details.value[id] = detail; } }
  catch (caught) { if (!controller.signal.aborted) focusedError.value = caught instanceof Error ? caught.message : "评审详情加载失败"; }
}, { immediate: true });
const visibleReviews = computed(() => {
  const rows = orderedReviews.value.map(item => details.value[item.id] ?? item);
  return focusedDetail.value && !rows.some(row => row.id === focusedDetail.value?.id) ? [focusedDetail.value, ...rows] : rows;
});
const reviewerGroups = computed(() => reviewerCandidates.value?.groups ?? []);
const explicitReviewerCount = computed(() => selectedReviewerCount(selectedReviewerGroupIds.value, directReviewerInput.value, reviewerCandidates.value));

onMounted(() => void load());
watch(() => props.selectedReviewId, () => void focusSelectedReview());

async function load(): Promise<void> {
  loading.value = true;
  try {
    const [publishTargets, candidates] = await Promise.all([
      paginationApi.targets(),
      canManage.value ? api.listReviewerCandidates(props.skill.skill.id) : Promise.resolve({ skill_id: props.skill.skill.id, groups: [] }),
    ]);
    targets.value = publishTargets;
    await reload();
    const visibleIds = new Set([...summaries.value.map(item => item.id), ...(props.selectedReviewId ? [props.selectedReviewId] : [])]);
    await Promise.all(Object.keys(details.value).filter(id => visibleIds.has(id)).map(async id => {
      details.value[id] = await paginationApi.review(id);
      if (focusedDetail.value?.id === id) focusedDetail.value = details.value[id];
    }));
    reviewerCandidates.value = candidates;
    await nextTick();
    await focusSelectedReview();
  } catch (error) {
    showError(error);
  } finally {
    loading.value = false;
  }
}

async function focusSelectedReview(): Promise<void> {
  if (!props.selectedReviewId) return;
  await nextTick();
  document.getElementById(`review-${props.selectedReviewId}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
}

async function copyReviewLink(review: ReviewSummary): Promise<void> {
  try {
    await navigator.clipboard.writeText(reviewShareUrl(props.skill.skill.id, review.id));
    emit("toast", { tone: "success", message: "评审链接已复制。" });
  } catch {
    emit("toast", { tone: "danger", message: "复制评审链接失败，请检查浏览器权限。" });
  }
}

async function createReview(): Promise<void> {
  if (!selectedVersionId.value) return;
  busy.value = true;
  try {
    const reviewerSources = buildReviewerSources(selectedReviewerGroupIds.value, directReviewerInput.value);
    await api.createReviewRequest(props.skill.skill.id, {
      skill_version_id: selectedVersionId.value,
      publish_targets: selectedTargets.value.map((publish_target_id) => ({ publish_target_id, auto_submit_on_pass: true })),
      ...(reviewerSources.length ? { reviewer_sources: reviewerSources } : {}),
    });
    emit("toast", { tone: "success", message: "评审已发起。" });
    selectedTargets.value = [];
    selectedReviewerGroupIds.value = [];
    directReviewerInput.value = "";
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
    details.value[review.id] = await api.closeReview(review.id);
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

function toggleReviewerGroup(groupId: string): void {
  selectedReviewerGroupIds.value = selectedReviewerGroupIds.value.includes(groupId)
    ? selectedReviewerGroupIds.value.filter((id) => id !== groupId)
    : [...selectedReviewerGroupIds.value, groupId];
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
        <span class="tag-chip">{{ total }} 条评审记录</span>
        <button class="secondary-button" type="button" :disabled="loading" @click="load">{{ loading ? "刷新中..." : "刷新" }}</button>
      </div>
    </section>

    <section class="review-manager-summary" aria-label="评审概览">
      <div class="primary-panel review-manager-stat">
        <span>进行中</span>
        <strong>{{ counts.open ?? 0 }}</strong>
      </div>
      <div class="primary-panel review-manager-stat">
        <span>已关闭</span>
        <strong>{{ counts.closed ?? 0 }}</strong>
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
      <ReviewLaunchPanel
        v-model:selected-version-id="selectedVersionId"
        v-model:direct-reviewer-input="directReviewerInput"
        :can-manage="canManage"
        :busy="busy"
        :manage-reason="manageReason"
        :skill-id="skill.skill.id"
        :selected-version="selectedVersion"
        :targets="targets"
        :selected-targets="selectedTargets"
        :reviewer-groups="reviewerGroups"
        :selected-reviewer-group-ids="selectedReviewerGroupIds"
        :explicit-reviewer-count="explicitReviewerCount"
        @version-selected="selectedVersion = $event"
        @toggle-reviewer-group="toggleReviewerGroup"
        @toggle-target="toggleTarget"
        @create="createReview"
      />

      <section class="primary-panel review-records-panel">
        <div class="review-panel-head">
          <div>
            <h2>评审记录</h2>
            <p>查看每次评审的评审人、回复和关闭后的门禁结果。</p>
          </div>
          <span class="tag-chip muted">{{ total }} 条</span>
        </div>

        <select v-model="status" aria-label="筛选评审状态"><option value="">全部</option><option value="open">进行中</option><option value="closed">已关闭</option></select>
        <PaginationBar v-model:page="page" v-model:page-size="pageSize" :total="total" :loading="listLoading" :error="listError" @retry="reload" />
        <p v-if="focusedError" role="alert">{{ focusedError }} <button class="secondary-button" type="button" @click="focusedRetry++">重试评审详情</button></p>
        <div class="review-record-list">
          <article
            v-for="review in visibleReviews"
            :id="`review-${review.id}`"
            :key="review.id"
            :class="['review-record-card', { 'review-record-card-target': review.id === selectedReviewId }]"
          >
            <div class="review-record-card-head">
              <div>
                <span class="review-record-version">版本 {{ review.skill_version.version }}</span>
                <h3>{{ reviewStatusText(review) }}</h3>
                <p>发起 {{ humanDate(review.created_at) }} · 发起人 {{ review.created_by }}</p>
              </div>
              <div class="review-record-card-tools">
                <button class="icon-button compact-button" type="button" :aria-label="`复制${reviewStatusText(review)}评审链接`" title="复制评审链接" @click="copyReviewLink(review)"><Copy :size="15" /></button>
                <span :class="['tag-chip', review.status === 'open' ? '' : 'muted']">{{ reviewStatusText(review) }}</span>
              </div>
            </div>

            <button v-if="!('responses' in review)" type="button" class="secondary-button" @click="expandReview(review)">查看详情</button>
            <template v-if="'responses' in review">
              <div class="review-record-metrics">
                <div>
                  <span>回复进度</span>
                  <strong>{{ responseCount(review) }}</strong>
                </div>
                <div>
                  <span>评审人</span>
                  <strong>{{ reviewerText(review, reviewerCandidates) }}</strong>
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
            </template>
          </article>

          <EmptyState
            v-if="!listLoading && !listError && !focusedError && !visibleReviews.length"
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
