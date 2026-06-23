<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { api, ApiError } from "../lib/api";
import type { ReviewRequest, ToastState } from "../types";

const emit = defineEmits<{ toast: [toast: ToastState]; openSkill: [skillId: string] }>();
const props = defineProps<{ actor: string }>();

const loading = ref(false);
const reviews = ref<ReviewRequest[]>([]);
const drafts = reactive<Record<string, { score: -1 | 0 | 1; comment: string }>>({});

const openReviews = computed(() => reviews.value.filter((review) => review.status === "open"));
const closedReviews = computed(() => reviews.value.filter((review) => review.status !== "open"));

onMounted(() => void load());

async function load(): Promise<void> {
  loading.value = true;
  try {
    reviews.value = await api.listMyReviews();
    for (const review of reviews.value) {
      const own = review.responses.find((item) => item.reviewer_actor === props.actor);
      drafts[review.id] = { score: own?.score ?? 1, comment: own?.comment ?? "" };
    }
  } catch (error) {
    showError(error);
  } finally {
    loading.value = false;
  }
}

async function submit(review: ReviewRequest): Promise<void> {
  const draft = drafts[review.id] ?? { score: 1 as const, comment: "" };
  try {
    await api.submitReviewResponse(review.id, draft);
    emit("toast", { tone: "success", message: "评审意见已提交。" });
    await load();
  } catch (error) {
    showError(error);
  }
}

function showError(error: unknown): void {
  emit("toast", { tone: "danger", message: error instanceof ApiError || error instanceof Error ? error.message : "操作失败。" });
}
</script>

<template>
  <div class="review-page">
    <section class="primary-panel review-hero">
      <div>
        <span class="section-kicker">我的评审</span>
        <h1>待处理评审</h1>
      </div>
      <button class="secondary-button" type="button" :disabled="loading" @click="load">{{ loading ? "刷新中..." : "刷新" }}</button>
    </section>

    <section class="review-list">
      <article v-for="review in openReviews" :key="review.id" class="primary-panel review-card">
        <div class="review-card-head">
          <div>
            <h2>{{ review.skill.slug }}</h2>
            <p>{{ review.skill_version.version }} · {{ review.reviewers.length }} 位评审人</p>
          </div>
          <span class="tag-chip">进行中</span>
        </div>
        <label class="field-label">
          <span>评分</span>
          <select v-model.number="drafts[review.id].score">
            <option :value="1">1 通过</option>
            <option :value="0">0 保留意见</option>
            <option :value="-1">-1 不通过</option>
          </select>
        </label>
        <label class="field-label">
          <span>评审意见</span>
          <textarea v-model="drafts[review.id].comment" rows="4" placeholder="补充评审依据、风险或建议" />
        </label>
        <div class="button-row">
          <button class="secondary-button" type="button" @click="emit('openSkill', review.skill_id)">查看 Skill</button>
          <button class="primary-button" type="button" @click="submit(review)">提交评审</button>
        </div>
      </article>
      <div v-if="!openReviews.length" class="primary-panel empty-panel">当前没有待处理评审。</div>
    </section>

    <section v-if="closedReviews.length" class="review-list">
      <h2>已结束</h2>
      <article v-for="review in closedReviews" :key="review.id" class="primary-panel review-card compact">
        <div class="review-card-head">
          <div>
            <h3>{{ review.skill.slug }}</h3>
            <p>{{ review.skill_version.version }}</p>
          </div>
          <span class="tag-chip muted">已结束</span>
        </div>
      </article>
    </section>
  </div>
</template>
