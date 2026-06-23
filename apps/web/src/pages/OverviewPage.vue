<script setup lang="ts">
import { ExternalLink, GitCompareArrows } from "lucide-vue-next";
import { computed } from "vue";
import BundleBrowser from "../components/BundleBrowser.vue";
import { compactText, humanDate, scoreKind, scoreLabel, slugTitle, versionName } from "../lib/format";
import type { RouteState } from "../lib/navigation";
import { tagLabel } from "../lib/skillTags";
import type { SkillDetail } from "../types";

const props = defineProps<{ skill: SkillDetail }>();
const emit = defineEmits<{ navigate: [next: Partial<RouteState>] }>();

const version = computed(() => props.skill.summary.current_version);
const evalSet = computed(() => props.skill.summary.primary_eval_set);
const run = computed(() => props.skill.summary.latest_accepted_eval_run);
const files = computed(() => version.value?.bundle_files ?? []);
const lifecycleLabel = computed(() => skillLifecycleLabel(props.skill.skill.lifecycle_status));

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
  </div>
</template>
