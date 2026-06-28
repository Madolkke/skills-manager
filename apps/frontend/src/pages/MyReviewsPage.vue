<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import EmptyState from "../components/EmptyState.vue";
import { api, ApiError } from "../lib/api";
import { humanDate } from "../lib/format";
import type { ReviewRequest, ReviewResponse, ToastState } from "../types";

const emit = defineEmits<{ toast: [toast: ToastState]; openSkill: [skillId: string] }>();
const props = defineProps<{ actor: string }>();

const loading = ref(false);
const selectedReviewId = ref("");
const reviews = ref<ReviewRequest[]>([]);
const drafts = reactive<Record<string, { score: -1 | 0 | 1; comment: string }>>({});

const scoreOptions = [
  { value: 1 as const, label: "通过", hint: "+1", description: "认可当前版本可继续推进" },
  { value: 0 as const, label: "保留", hint: "0", description: "需要补充信息或进一步观察" },
  { value: -1 as const, label: "不通过", hint: "-1", description: "存在阻断发布的问题" },
];

const openReviews = computed(() => sortReviews(reviews.value.filter((review) => review.status === "open")));
const closedReviews = computed(() => sortReviews(reviews.value.filter((review) => review.status !== "open")));
const orderedReviews = computed(() => [...openReviews.value, ...closedReviews.value]);
const selectedReview = computed(() => orderedReviews.value.find((review) => review.id === selectedReviewId.value) ?? orderedReviews.value[0] ?? null);
const selectedDraft = computed(() => (selectedReview.value ? drafts[selectedReview.value.id] ?? null : null));
const hasReviews = computed(() => orderedReviews.value.length > 0);

onMounted(() => void load());

async function load(): Promise<void> {
  const previousSelection = selectedReviewId.value;
  loading.value = true;
  try {
    const nextReviews = await api.listMyReviews();
    reviews.value = nextReviews;
    syncDrafts(nextReviews);
    selectedReviewId.value = nextReviews.some((review) => review.id === previousSelection) ? previousSelection : nextDefaultSelection(nextReviews);
  } catch (error) {
    showError(error);
  } finally {
    loading.value = false;
  }
}

async function submit(review: ReviewRequest): Promise<void> {
  const draft = ensureDraft(review);
  const currentSelection = selectedReviewId.value;
  try {
    await api.submitReviewResponse(review.id, draft);
    emit("toast", { tone: "success", message: "评审意见已提交。" });
    await load();
    selectedReviewId.value = currentSelection;
  } catch (error) {
    showError(error);
  }
}

function syncDrafts(nextReviews: ReviewRequest[]): void {
  const liveIds = new Set(nextReviews.map((review) => review.id));
  for (const key of Object.keys(drafts)) {
    if (!liveIds.has(key)) delete drafts[key];
  }
  for (const review of nextReviews) ensureDraft(review);
}

function ensureDraft(review: ReviewRequest): { score: -1 | 0 | 1; comment: string } {
  const own = ownResponse(review);
  drafts[review.id] ??= { score: own?.score ?? 1, comment: own?.comment ?? "" };
  return drafts[review.id];
}

function nextDefaultSelection(items: ReviewRequest[]): string {
  return sortReviews(items).find((review) => review.status === "open")?.id ?? sortReviews(items)[0]?.id ?? "";
}

function sortReviews(items: ReviewRequest[]): ReviewRequest[] {
  return [...items].sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
}

function selectReview(review: ReviewRequest): void {
  selectedReviewId.value = review.id;
  ensureDraft(review);
}

function ownResponse(review: ReviewRequest): ReviewResponse | undefined {
  return review.responses.find((item) => item.reviewer_actor === props.actor);
}

function responseCount(review: ReviewRequest): string {
  return `${review.responses.length} / ${review.reviewers.length}`;
}

function autoTargetText(review: ReviewRequest): string {
  const names = review.publish_targets.filter((target) => target.auto_submit_on_pass).map((target) => target.name);
  return names.length ? names.join("、") : "未设置";
}

function statusLabel(review: ReviewRequest): string {
  if (review.status === "open") return "待评审";
  if (review.status === "closed") return "已结束";
  return "已取消";
}

function scoreLabel(score?: -1 | 0 | 1): string {
  if (score === 1) return "+1 通过";
  if (score === 0) return "0 保留";
  if (score === -1) return "-1 不通过";
  return "未评分";
}

function scoreTone(score?: -1 | 0 | 1): string {
  if (score === 1) return "positive";
  if (score === 0) return "neutral";
  if (score === -1) return "negative";
  return "muted";
}

function setSelectedScore(score: -1 | 0 | 1): void {
  if (selectedDraft.value) selectedDraft.value.score = score;
}

function showError(error: unknown): void {
  emit("toast", { tone: "danger", message: error instanceof ApiError || error instanceof Error ? error.message : "操作失败。" });
}
</script>

<template>
  <div class="review-page my-reviews-page">
    <section class="primary-panel review-hero my-reviews-hero">
      <div>
        <span class="section-kicker">我的评审</span>
        <h1>评审工作台</h1>
        <p>处理分配给当前身份的 Skill 版本评审，提交分数和意见后用于发布门禁判断。</p>
      </div>
      <div class="my-reviews-hero-side">
        <div class="my-reviews-actor">
          <span>当前身份</span>
          <strong>{{ actor }}</strong>
        </div>
        <div class="button-row">
          <button class="secondary-button" type="button" :disabled="loading" @click="load">{{ loading ? "刷新中..." : "刷新" }}</button>
        </div>
      </div>
    </section>

    <section class="my-reviews-summary" aria-label="评审摘要">
      <div class="primary-panel my-review-stat">
        <span>待处理</span>
        <strong>{{ openReviews.length }}</strong>
      </div>
      <div class="primary-panel my-review-stat">
        <span>已结束</span>
        <strong>{{ closedReviews.length }}</strong>
      </div>
      <div class="primary-panel my-review-stat wide">
        <span>当前队列</span>
        <strong>{{ hasReviews ? `${openReviews.length} 个待处理 · ${closedReviews.length} 个已归档` : "暂无评审任务" }}</strong>
      </div>
    </section>

    <section v-if="hasReviews" class="my-reviews-workbench">
      <aside class="primary-panel my-reviews-sidebar">
        <div class="my-reviews-sidebar-head">
          <div>
            <h2>评审队列</h2>
            <p>{{ orderedReviews.length }} 条记录</p>
          </div>
        </div>

        <div v-if="openReviews.length" class="my-review-queue-section">
          <span class="my-review-section-label">待处理</span>
          <button
            v-for="review in openReviews"
            :key="review.id"
            type="button"
            :class="['my-review-queue-item', { active: selectedReview?.id === review.id }]"
            @click="selectReview(review)"
          >
            <span class="my-review-item-main">
              <strong>{{ review.skill.slug }}</strong>
              <small>{{ review.skill_version.version }} · 回复 {{ responseCount(review) }}</small>
            </span>
            <span :class="['my-review-score-pill', scoreTone(ownResponse(review)?.score)]">{{ scoreLabel(ownResponse(review)?.score) }}</span>
          </button>
        </div>

        <div v-if="closedReviews.length" class="my-review-queue-section">
          <span class="my-review-section-label">已结束</span>
          <button
            v-for="review in closedReviews"
            :key="review.id"
            type="button"
            :class="['my-review-queue-item', { active: selectedReview?.id === review.id }]"
            @click="selectReview(review)"
          >
            <span class="my-review-item-main">
              <strong>{{ review.skill.slug }}</strong>
              <small>{{ review.skill_version.version }} · {{ statusLabel(review) }}</small>
            </span>
            <span :class="['my-review-score-pill', scoreTone(ownResponse(review)?.score)]">{{ scoreLabel(ownResponse(review)?.score) }}</span>
          </button>
        </div>
      </aside>

      <article v-if="selectedReview && selectedDraft" class="primary-panel my-review-detail">
        <header class="my-review-detail-head">
          <div>
            <span :class="['tag-chip', selectedReview.status === 'open' ? '' : 'muted']">{{ statusLabel(selectedReview) }}</span>
            <h2>{{ selectedReview.skill.slug }}</h2>
            <p>{{ selectedReview.skill_version.version }} · 发起人 {{ selectedReview.created_by }}</p>
          </div>
          <button class="secondary-button" type="button" @click="emit('openSkill', selectedReview.skill_id)">查看 Skill</button>
        </header>

        <div class="my-review-meta-strip">
          <div>
            <span>发起时间</span>
            <strong>{{ humanDate(selectedReview.created_at) }}</strong>
          </div>
          <div>
            <span>评审进度</span>
            <strong>{{ responseCount(selectedReview) }}</strong>
          </div>
          <div>
            <span>自动发布源</span>
            <strong>{{ autoTargetText(selectedReview) }}</strong>
          </div>
        </div>

        <section class="my-review-section">
          <div class="my-review-section-head">
            <div>
              <h3>{{ selectedReview.status === "open" ? "提交评审" : "我的评审结果" }}</h3>
              <p>{{ selectedReview.status === "open" ? "选择一个分数，并补充可执行的评审意见。" : "评审已结束，评分和意见已锁定。" }}</p>
            </div>
            <span :class="['my-review-score-pill large', scoreTone(ownResponse(selectedReview)?.score)]">{{ scoreLabel(ownResponse(selectedReview)?.score) }}</span>
          </div>

          <div v-if="selectedReview.status === 'open'" class="my-review-form">
            <div class="my-review-score-grid" role="radiogroup" aria-label="评审评分">
              <button
                v-for="option in scoreOptions"
                :key="option.value"
                type="button"
                :class="['my-review-score-option', scoreTone(option.value), { active: selectedDraft.score === option.value }]"
                @click="setSelectedScore(option.value)"
              >
                <span>{{ option.hint }}</span>
                <strong>{{ option.label }}</strong>
                <small>{{ option.description }}</small>
              </button>
            </div>
            <label class="field-label">
              <span>评审意见</span>
              <textarea v-model="selectedDraft.comment" rows="6" placeholder="补充评审依据、风险、阻断问题或后续建议" />
            </label>
            <div class="button-row my-review-actions">
              <button class="secondary-button" type="button" @click="emit('openSkill', selectedReview.skill_id)">查看 Skill</button>
              <button class="primary-button" type="button" :disabled="loading" @click="submit(selectedReview)">
                {{ ownResponse(selectedReview) ? "更新评审" : "提交评审" }}
              </button>
            </div>
          </div>

          <div v-else class="my-review-readonly-response">
            <strong>{{ scoreLabel(ownResponse(selectedReview)?.score) }}</strong>
            <p>{{ ownResponse(selectedReview)?.comment || "未填写意见" }}</p>
          </div>
        </section>

        <section class="my-review-section">
          <div class="my-review-section-head">
            <div>
              <h3>评审人反馈</h3>
              <p>{{ selectedReview.responses.length }} 位评审人已提交。</p>
            </div>
          </div>
          <div class="review-response-list my-review-response-list">
            <div v-for="response in selectedReview.responses" :key="response.reviewer_actor" class="review-response-row my-review-response-row">
              <strong>{{ response.reviewer_actor }}</strong>
              <span :class="['my-review-score-pill', scoreTone(response.score)]">{{ scoreLabel(response.score) }}</span>
              <p>{{ response.comment || "未填写意见" }}</p>
            </div>
            <div v-if="!selectedReview.responses.length" class="my-review-muted-box">还没有评审人提交反馈。</div>
          </div>
        </section>
      </article>
    </section>

    <section v-else class="primary-panel my-reviews-empty">
      <EmptyState
        title="当前没有评审任务"
        description="当有人将你加入 reviewer 角色并发起评审后，任务会出现在这里。"
        action-label="刷新"
        @action="load"
      />
    </section>
  </div>
</template>
