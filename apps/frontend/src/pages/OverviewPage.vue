<script setup lang="ts">
import type { SkillCore } from "../lib/api/paginationApi";

import { ExternalLink, GitCompareArrows, Workflow } from "lucide-vue-next";
import { computed, onMounted, ref, watch } from "vue";
import BundleBrowser from "../components/BundleBrowser.vue";
import InlineLoading from "../components/InlineLoading.vue";
import { paginationApi, type GuidanceReview, type GuidancePublish } from "../lib/api/paginationApi";
import type { SkillVersion, EvalRunRecord } from "../types";
import { compactText, humanDate, scoreKind, scoreLabel, versionName } from "../lib/format";
import type { RouteState } from "../lib/navigation";
import { buildSkillSuggestions, buildVersionFlowItems } from "../lib/skillGuidance";
import { skillSecondaryName } from "../lib/skillIdentity";
import { tagLabel } from "../lib/skillTags";

const props = withDefaults(defineProps<{ skill: SkillCore; evaluationsVisible?: boolean }>(), { evaluationsVisible: true });
const emit = defineEmits<{ navigate: [next: Partial<RouteState>] }>();
const reviews = ref<GuidanceReview[]>([]);
const publishRecords = ref<GuidancePublish[]>([]);
const guidanceLoading = ref(false);

const version = ref<SkillVersion | null>(null);
const versionError = ref("");
const versionLoading = ref(false);
const versionRetry = ref(0);
const guidanceError = ref("");
const flowVersions = ref<SkillVersion[]>([]);
const flowRuns = ref<EvalRunRecord[]>([]);
watch([() => props.skill.summary.current_version?.id, versionRetry], async ([id], _, cleanup) => {
  const controller = new AbortController(); cleanup(() => controller.abort()); version.value = null;
  versionError.value = ""; versionLoading.value = Boolean(id);
  if (id) try { const detail = await paginationApi.version(id, controller.signal); if (!controller.signal.aborted) version.value = detail.version; }
  catch (error) { if (!controller.signal.aborted) versionError.value = error instanceof Error ? error.message : "内容加载失败"; }
  finally { if (!controller.signal.aborted) versionLoading.value = false; }
}, { immediate: true });
const evalSet = computed(() => props.skill.summary.primary_eval_set);
const run = computed(() => props.skill.summary.latest_accepted_eval_run);
const files = computed(() => version.value?.bundle_files ?? []);
const lifecycleLabel = computed(() => skillLifecycleLabel(props.skill.skill.lifecycle_status));
const versionFlowItems = computed(() => buildVersionFlowItems({
  skill: { ...props.skill, latest_eval_runs: flowRuns.value },
  versions: flowVersions.value,
  reviews: reviews.value,
  publishRecords: publishRecords.value,
  evaluationsVisible: props.evaluationsVisible,
}).slice(0, 4));
const suggestions = computed(() => buildSkillSuggestions({
  skill: props.skill,
  reviews: reviews.value,
  publishRecords: publishRecords.value,
  evaluationsVisible: props.evaluationsVisible,
}));
const secondaryName = computed(() => skillSecondaryName(props.skill.skill));

onMounted(() => void loadGuidance());
watch(() => props.skill.skill.id, () => void loadGuidance());

async function loadGuidance(): Promise<void> {
  guidanceLoading.value = true; guidanceError.value = "";
  try {
    const detail = await paginationApi.guidance(props.skill.skill.id);
    flowVersions.value = detail.versions;
    flowRuns.value = detail.eval_runs;
    reviews.value = detail.reviews;
    publishRecords.value = detail.publish_records;
  } catch (error) {
    guidanceError.value = error instanceof Error ? error.message : "版本流程加载失败";
    reviews.value = [];
    publishRecords.value = [];
  } finally {
    guidanceLoading.value = false;
  }
}

function skillLifecycleLabel(status: string): string {
  if (status === "active") return "活跃";
  if (status === "archived") return "归档";
  return status;
}
</script>

<template>
  <div class="overview-grid">
    <section class="skill-summary-panel">
      <div class="skill-summary-main">
        <div class="skill-title-copy">
          <h1>{{ skill.skill.slug }}</h1>
          <span v-if="secondaryName" class="skill-display-name">{{ secondaryName }}</span>
          <p>{{ compactText(version?.description, "尚未填写 Skill 描述。") }}</p>
        </div>
        <dl class="skill-identity-card" aria-label="Skill 身份信息">
          <div>
            <dt>根目录</dt>
            <dd>{{ skill.skill.slug }}/</dd>
          </div>
          <div>
            <dt>维护者</dt>
            <dd>{{ skill.skill.owner_ref }}</dd>
          </div>
          <div>
            <dt>状态</dt>
            <dd>{{ lifecycleLabel }}</dd>
          </div>
        </dl>
        <div v-if="skill.skill.tags?.length" class="tag-row skill-tag-row">
          <span v-for="tag in skill.skill.tags" :key="`${tag.group_id}:${tag.value}`" class="tag-chip">{{ tagLabel(tag) }}</span>
        </div>
      </div>
      <div :class="['skill-summary-metrics', { 'evaluations-hidden': !evaluationsVisible }]">
        <div class="summary-metric">
          <span>当前版本</span>
          <strong>{{ versionName(version) }}</strong>
          <small v-if="version?.created_at">更新于 {{ humanDate(version.created_at) }}</small>
        </div>
        <div v-if="evaluationsVisible" class="summary-metric">
          <span>验证分数</span>
          <strong :class="scoreKind(run)">{{ scoreLabel(run) }}</strong>
          <small>{{ run?.summary?.total ? `${run.summary.passed ?? 0}/${run.summary.total} 通过` : "尚无测评" }}</small>
        </div>
        <div v-if="evaluationsVisible" class="summary-metric">
          <span>测评集</span>
          <strong>{{ evalSet?.name ?? "未创建" }}</strong>
          <small>{{ evalSet ? "默认测评集" : "无测评集" }}</small>
        </div>
      </div>
    </section>
    <section class="primary-panel bundle-panel">
      <p v-if="versionLoading" role="status">正在加载当前版本内容…</p>
      <p v-if="versionError" role="alert">{{ versionError }} <button class="secondary-button" type="button" @click="versionRetry++">重试内容</button></p>
      <p v-if="guidanceError" role="alert">{{ guidanceError }} <button class="secondary-button" type="button" @click="loadGuidance">重试版本流程</button></p>
      <div class="panel-title-row">
        <h2>Skill内容</h2>
        <div class="button-row">
          <button v-if="skill.workflow" class="secondary-button" type="button" @click="emit('navigate', { section: 'workflows', skillId: skill.skill.id, tab: 'workflow' })">
            编辑工作流
            <Workflow :size="16" />
          </button>
          <button class="secondary-button" type="button" @click="emit('navigate', { tab: 'versions' })">
            版本管理
            <GitCompareArrows :size="16" />
          </button>
          <button v-if="evaluationsVisible" class="secondary-button" type="button" @click="emit('navigate', { tab: 'history' })">
            打开测评历史
            <ExternalLink :size="16" />
          </button>
        </div>
      </div>
      <BundleBrowser :files="files" :root-label="skill.skill.slug" />
    </section>

    <section class="primary-panel skill-guidance-panel">
      <div class="panel-title-row">
        <div>
          <h2>下一步建议</h2>
          <p>{{ evaluationsVisible ? "根据版本、测评、评审和发布状态生成。" : "根据版本、评审和发布状态生成。" }}</p>
        </div>
        <InlineLoading v-if="guidanceLoading" label="正在刷新建议" />
      </div>
      <div v-if="suggestions.length" class="skill-suggestion-list">
        <article v-for="item in suggestions" :key="item.id" class="skill-suggestion-card">
          <div>
            <strong>{{ item.title }}</strong>
            <p>{{ item.description }}</p>
          </div>
          <button class="secondary-button compact-button" type="button" @click="emit('navigate', { tab: item.tab })">{{ item.actionLabel }}</button>
        </article>
      </div>
      <div v-else class="skill-suggestion-done">
        {{ evaluationsVisible ? "当前没有明确阻塞项，可以继续维护版本、补充测评或查看测评历史。" : "当前没有明确阻塞项，可以继续维护版本、发起评审或查看发布状态。" }}
      </div>
    </section>

    <section class="primary-panel version-flow-panel">
      <div class="panel-title-row">
        <div>
          <h2>版本流程</h2>
          <p>{{ evaluationsVisible ? "按版本查看测评、评审和发布进展。" : "按版本查看评审和发布进展。" }}</p>
        </div>
      </div>
      <div class="version-flow-list">
        <article v-for="item in versionFlowItems" :key="item.versionId" class="version-flow-card">
          <header>
            <strong>{{ item.version }}</strong>
            <span v-if="item.isCurrent" class="tag-chip">当前版本</span>
          </header>
          <div :class="['version-flow-stages', { 'evaluations-hidden': !evaluationsVisible }]">
            <button
              v-for="stage in item.stages"
              :key="stage.id"
              :class="['version-flow-stage', stage.status]"
              type="button"
              @click="emit('navigate', { tab: stage.tab, selectedVersionId: item.versionId })"
            >
              <span>{{ stage.label }}</span>
              <strong>{{ stage.description }}</strong>
            </button>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>
