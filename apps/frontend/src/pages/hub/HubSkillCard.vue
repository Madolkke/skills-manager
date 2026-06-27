<script setup lang="ts">
import clsx from "clsx";
import { CheckCircle2, Circle } from "lucide-vue-next";
import { humanDate, scoreKind, scoreLabel, slugTitle, versionName } from "../../lib/format";
import type { SkillSummary } from "../../types";

defineProps<{ item: SkillSummary }>();
const emit = defineEmits<{ click: [] }>();
</script>

<template>
  <button class="skill-card" type="button" @click="emit('click')">
    <div class="card-body">
      <div class="card-context">
        <span>维护者 {{ item.skill.owner_ref }}</span>
        <span>更新 {{ humanDate(item.skill.updated_at) }}</span>
      </div>
      <div class="skill-card-head">
        <h3>{{ slugTitle(item.skill.slug) }}</h3>
        <span :class="clsx('score-chip', scoreKind(item.summary.latest_accepted_eval_run))">{{ scoreLabel(item.summary.latest_accepted_eval_run) }}</span>
      </div>
      <p>{{ item.summary.current_version?.change_summary ?? "尚未写入说明。" }}</p>
    </div>
    <div class="card-metrics">
      <span class="metric-cell">
        <small>验证得分</small>
        <strong :class="scoreKind(item.summary.latest_accepted_eval_run)">{{ scoreLabel(item.summary.latest_accepted_eval_run) }}</strong>
      </span>
      <span class="metric-cell">
        <small>测评集</small>
        <strong>{{ item.summary.primary_eval_set?.name ?? "未创建" }}</strong>
      </span>
      <span class="metric-cell">
        <small>当前版本</small>
        <strong>{{ versionName(item.summary.current_version) }}</strong>
      </span>
      <Circle v-if="scoreKind(item.summary.latest_accepted_eval_run) === 'empty'" class="status-ring empty" :size="23" />
      <CheckCircle2 v-else class="status-ring verified" :size="23" />
    </div>
  </button>
</template>
