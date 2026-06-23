<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import DropdownSelect from "../components/DropdownSelect.vue";
import type { DropdownSelectOption } from "../components/dropdown";
import { api, ApiError } from "../lib/api";
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
const versionOptions = computed<DropdownSelectOption[]>(() =>
  props.skill.versions.map((version) => ({
    value: version.id,
    label: version.version,
    description: version.display_name || version.change_summary,
  })),
);
const orderedReviews = computed(() => [...reviews.value].sort((a, b) => (b.created_at || "").localeCompare(a.created_at || "")));

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

function showError(error: unknown): void {
  emit("toast", { tone: "danger", message: error instanceof ApiError || error instanceof Error ? error.message : "操作失败。" });
}
</script>

<template>
  <div class="review-page">
    <section class="primary-panel review-hero">
      <div>
        <span class="section-kicker">评审</span>
        <h1>版本评审</h1>
        <p>针对特定 Skill 版本发起评审，评审人来自 reviewer 角色授权快照。</p>
      </div>
      <button class="secondary-button" type="button" :disabled="loading" @click="load">{{ loading ? "刷新中..." : "刷新" }}</button>
    </section>

    <section class="primary-panel review-create-panel">
      <div class="panel-title-row">
        <div>
          <h2>发起评审</h2>
          <p>可同时勾选发布源作为自动提交目标；评审通过后仍需后台确认发布。</p>
        </div>
      </div>
      <div v-if="canManage" class="review-create-grid">
        <label class="field-label">
          <span>Skill 版本</span>
          <DropdownSelect v-model="selectedVersionId" :options="versionOptions" compact />
        </label>
        <div class="field-label">
          <span>自动提交发布源</span>
          <div class="review-target-grid">
            <button
              v-for="target in targets"
              :key="target.id"
              type="button"
              :class="['review-target-option', { active: selectedTargets.includes(target.id) }]"
              @click="toggleTarget(target.id)"
            >
              <strong>{{ target.name }}</strong>
              <small>{{ target.description || target.target_key }}</small>
            </button>
            <span v-if="!targets.length" class="field-help">后台还没有启用的发布源。</span>
          </div>
        </div>
        <button class="primary-button" type="button" :disabled="busy || !selectedVersionId" @click="createReview">发起评审</button>
      </div>
      <p v-else class="field-help permission-hint">当前身份需要 maintainer、owner 或 admin 才能发起评审。</p>
    </section>

    <section class="review-list">
      <article v-for="review in orderedReviews" :key="review.id" class="primary-panel review-card">
        <div class="review-card-head">
          <div>
            <h2>{{ review.skill_version.version }}</h2>
            <p>回复 {{ responseCount(review) }} · 发起人 {{ review.created_by }}</p>
          </div>
          <span :class="['tag-chip', review.status === 'open' ? '' : 'muted']">{{ review.status === "open" ? "进行中" : "已关闭" }}</span>
        </div>
        <div class="review-meta-grid">
          <div>
            <span>评审人</span>
            <strong>{{ review.reviewers.map((item) => item.reviewer_actor).join(", ") || "无" }}</strong>
          </div>
          <div>
            <span>自动发布源</span>
            <strong>{{ review.publish_targets.filter((item) => item.auto_submit_on_pass).map((item) => item.name).join(", ") || "未设置" }}</strong>
          </div>
        </div>
        <div v-if="review.check_results.length" class="review-check-grid">
          <span v-for="check in review.check_results" :key="check.check_id" :class="['review-check-chip', { passed: check.passed, failed: !check.passed }]">
            {{ check.check_id }} · {{ check.passed ? "通过" : "未通过" }}
          </span>
        </div>
        <div class="review-response-list">
          <div v-for="response in review.responses" :key="response.reviewer_actor" class="review-response-row">
            <strong>{{ response.reviewer_actor }}</strong>
            <span>{{ response.score }}</span>
            <p>{{ response.comment || "未填写意见" }}</p>
          </div>
        </div>
        <div v-if="review.status === 'open' && canManage" class="button-row">
          <button class="primary-button" type="button" :disabled="busy" @click="closeReview(review)">结束评审</button>
        </div>
      </article>
      <div v-if="!orderedReviews.length" class="primary-panel empty-panel">还没有评审记录。</div>
    </section>
  </div>
</template>
