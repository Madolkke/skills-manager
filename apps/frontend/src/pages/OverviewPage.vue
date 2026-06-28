<script setup lang="ts">
import { ExternalLink, GitCompareArrows } from "lucide-vue-next";
import { computed, onMounted, ref, watch } from "vue";
import BundleBrowser from "../components/BundleBrowser.vue";
import InlineLoading from "../components/InlineLoading.vue";
import { api } from "../lib/api";
import { compactText, humanDate, scoreKind, scoreLabel, slugTitle, versionName } from "../lib/format";
import type { RouteState } from "../lib/navigation";
import { buildSkillSuggestions, buildVersionFlowItems } from "../lib/skillGuidance";
import { tagLabel } from "../lib/skillTags";
import type { ReviewRequest, SkillDetail, SkillPublishOverview } from "../types";

const props = defineProps<{ skill: SkillDetail }>();
const emit = defineEmits<{ navigate: [next: Partial<RouteState>] }>();
const reviews = ref<ReviewRequest[]>([]);
const publishOverview = ref<SkillPublishOverview | null>(null);
const guidanceLoading = ref(false);

const version = computed(() => props.skill.summary.current_version);
const evalSet = computed(() => props.skill.summary.primary_eval_set);
const run = computed(() => props.skill.summary.latest_accepted_eval_run);
const files = computed(() => version.value?.bundle_files ?? []);
const lifecycleLabel = computed(() => skillLifecycleLabel(props.skill.skill.lifecycle_status));
const versionFlowItems = computed(() => buildVersionFlowItems({
  skill: props.skill,
  reviews: reviews.value,
  publishRecords: publishOverview.value?.publish_records ?? [],
}).slice(0, 4));
const suggestions = computed(() => buildSkillSuggestions({
  skill: props.skill,
  reviews: reviews.value,
  publishRecords: publishOverview.value?.publish_records ?? [],
}));

onMounted(() => void loadGuidance());
watch(() => props.skill.skill.id, () => void loadGuidance());

async function loadGuidance(): Promise<void> {
  guidanceLoading.value = true;
  try {
    const [nextReviews, nextPublish] = await Promise.all([
      api.listSkillReviews(props.skill.skill.id),
      api.getSkillPublishOverview(props.skill.skill.id),
    ]);
    reviews.value = nextReviews;
    publishOverview.value = nextPublish;
  } catch {
    reviews.value = [];
    publishOverview.value = null;
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
          <h1>{{ slugTitle(skill.skill.slug) }}</h1>
          <p>{{ compactText(version?.change_summary, "这个 Skill 还没有说明。") }}</p>
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
      <div class="skill-summary-metrics">
        <div class="summary-metric">
          <span>当前版本</span>
          <strong>{{ versionName(version) }}</strong>
          <small v-if="version?.created_at">更新于 {{ humanDate(version.created_at) }}</small>
        </div>
        <div class="summary-metric">
          <span>验证分数</span>
          <strong :class="scoreKind(run)">{{ scoreLabel(run) }}</strong>
          <small>{{ run?.summary?.total ? `${run.summary.passed ?? 0}/${run.summary.total} 通过` : "尚无测评" }}</small>
        </div>
        <div class="summary-metric">
          <span>测评集</span>
          <strong>{{ evalSet?.name ?? "未创建" }}</strong>
          <small>{{ evalSet ? "默认测评集" : "无测评集" }}</small>
        </div>
      </div>
    </section>
    <section class="primary-panel bundle-panel">
      <div class="panel-title-row">
        <h2>Skill bundle</h2>
        <div class="button-row">
          <button class="secondary-button" type="button" @click="emit('navigate', { tab: 'versions' })">
            版本管理
            <GitCompareArrows :size="16" />
          </button>
          <button class="secondary-button" type="button" @click="emit('navigate', { tab: 'history' })">
            打开历史
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
          <p>根据版本、测评、评审和发布状态生成。</p>
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
      <div v-else class="skill-suggestion-done">当前没有明确阻塞项，可以继续维护版本、补充测评或查看历史结果。</div>
    </section>

    <section class="primary-panel version-flow-panel">
      <div class="panel-title-row">
        <div>
          <h2>版本流程</h2>
          <p>按版本查看测评、评审和发布进展。</p>
        </div>
      </div>
      <div class="version-flow-list">
        <article v-for="item in versionFlowItems" :key="item.versionId" class="version-flow-card">
          <header>
            <strong>{{ item.version }}</strong>
            <span v-if="item.isCurrent" class="tag-chip">当前版本</span>
          </header>
          <div class="version-flow-stages">
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
