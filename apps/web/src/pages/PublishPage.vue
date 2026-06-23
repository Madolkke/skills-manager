<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api, ApiError } from "../lib/api";
import type { PublishGateExpression, PublishTarget, ReviewRequest, SkillDetail, SkillPublishOverview, ToastState } from "../types";

const props = defineProps<{ skill: SkillDetail }>();
const emit = defineEmits<{ toast: [toast: ToastState] }>();

const loading = ref(false);
const busy = ref(false);
const overview = ref<SkillPublishOverview | null>(null);

const canRequestPublish = computed(() => Boolean(props.skill.capabilities?.permissions["publish.request"]));
const versions = computed(() => overview.value?.versions ?? []);
const targets = computed(() => (overview.value?.publish_targets ?? []).filter((target) => target.enabled));
const records = computed(() => overview.value?.publish_records ?? []);

onMounted(() => void load());

async function load(): Promise<void> {
  loading.value = true;
  try {
    overview.value = await api.getSkillPublishOverview(props.skill.skill.id);
  } catch (error) {
    showError(error);
  } finally {
    loading.value = false;
  }
}

async function requestPublish(review: ReviewRequest, target: PublishTarget): Promise<void> {
  busy.value = true;
  try {
    await api.createPublishRecord(props.skill.skill.id, {
      skill_version_id: review.skill_version_id,
      review_request_id: review.id,
      publish_target_id: target.id,
    });
    emit("toast", { tone: "success", message: "已提交后台待确认发布单。" });
    await load();
  } catch (error) {
    showError(error);
  } finally {
    busy.value = false;
  }
}

function recordFor(versionId: string, targetId: string): string {
  const record = records.value.find((item) => item.skill_version_id === versionId && item.publish_target_id === targetId);
  if (!record) return "未提交";
  if (record.status === "pending_confirmation") return "待后台确认";
  if (record.status === "released") return "已发布";
  if (record.status === "cancelled") return "已取消";
  return "发布失败";
}

function canSubmit(review: ReviewRequest | null, target: PublishTarget): boolean {
  if (!review || review.status !== "closed") return false;
  return !records.value.some((item) => item.skill_version_id === review.skill_version_id && item.publish_target_id === target.id);
}

function gateSummary(expression: PublishGateExpression): string {
  if (expression.type === "check") return expression.check_id;
  const op = expression.op === "and" ? "全部满足" : "任一满足";
  return `${op} · ${expression.children.length} 条门禁`;
}

function showError(error: unknown): void {
  emit("toast", { tone: "danger", message: error instanceof ApiError || error instanceof Error ? error.message : "操作失败。" });
}
</script>

<template>
  <div class="review-page">
    <section class="primary-panel review-hero">
      <div>
        <span class="section-kicker">发布</span>
        <h1>发布门禁与确认单</h1>
        <p>通过评审后提交后台待确认发布单，真实发布由后台管理员确认。</p>
      </div>
      <button class="secondary-button" type="button" :disabled="loading" @click="load">{{ loading ? "刷新中..." : "刷新" }}</button>
    </section>

    <section class="review-list">
      <article v-for="item in versions" :key="item.version.id" class="primary-panel review-card">
        <div class="review-card-head">
          <div>
            <h2>{{ item.version.version }}</h2>
            <p>{{ item.version.display_name || item.version.change_summary }}</p>
          </div>
          <span :class="['tag-chip', item.review?.status === 'closed' ? '' : 'muted']">
            {{ item.review ? (item.review.status === "closed" ? "评审已关闭" : "评审中") : "未评审" }}
          </span>
        </div>
        <div v-if="item.review?.check_results.length" class="review-check-grid">
          <span v-for="check in item.review.check_results" :key="check.check_id" :class="['review-check-chip', { passed: check.passed, failed: !check.passed }]">
            {{ check.check_id }} · {{ check.passed ? "通过" : "未通过" }}
          </span>
        </div>
        <div class="publish-target-table">
          <div class="publish-target-head">
            <span>发布源</span>
            <span>门禁</span>
            <span>状态</span>
            <span></span>
          </div>
          <div v-for="target in targets" :key="target.id" class="publish-target-row">
            <strong>{{ target.name }}</strong>
            <span>{{ gateSummary(target.gate_expression) }}</span>
            <span>{{ recordFor(item.version.id, target.id) }}</span>
            <button
              class="secondary-button"
              type="button"
              :disabled="busy || !canRequestPublish || !canSubmit(item.review, target)"
              @click="item.review && requestPublish(item.review, target)"
            >
              提交确认单
            </button>
          </div>
          <p v-if="!targets.length" class="field-help">后台还没有启用的发布源。</p>
        </div>
      </article>
      <div v-if="!versions.length" class="primary-panel empty-panel">还没有可发布版本。</div>
    </section>
  </div>
</template>
