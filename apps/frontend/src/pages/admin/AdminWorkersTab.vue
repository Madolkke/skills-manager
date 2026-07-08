<script setup lang="ts">
import { computed } from "vue";
import { humanDate } from "../../lib/format";
import { durationText, queuedWorkerJobs, workerCurrentJobText, workerJobTypeText, workerStatusText, workerStatusTone } from "../../lib/workerStatus";
import type { WorkerStatus, WorkerStatusOverview } from "../../types";

const props = defineProps<{ overview: WorkerStatusOverview | null; loading: boolean }>();
const emit = defineEmits<{ refresh: [] }>();

const summary = computed(() => props.overview?.summary);
const workers = computed(() => props.overview?.workers ?? []);
const queuedTotal = computed(() => queuedWorkerJobs(props.overview));

function runtimeText(worker: WorkerStatus): string {
  return durationText(worker.started_at, props.overview?.generated_at);
}

function jobRuntimeText(worker: WorkerStatus): string {
  if (!worker.current_job?.started_at) return "-";
  return durationText(worker.current_job.started_at, props.overview?.generated_at);
}
</script>

<template>
  <div class="admin-tab-stack admin-workers-tab">
    <section class="admin-metric-grid">
      <div class="admin-metric-card">
        <span>Worker</span>
        <strong>{{ summary?.total ?? 0 }}</strong>
      </div>
      <div class="admin-metric-card">
        <span>在线</span>
        <strong>{{ summary?.online ?? 0 }}</strong>
      </div>
      <div class="admin-metric-card">
        <span>运行中</span>
        <strong>{{ summary?.running ?? 0 }}</strong>
      </div>
      <div class="admin-metric-card">
        <span>排队任务</span>
        <strong>{{ queuedTotal }}</strong>
      </div>
    </section>

    <section class="primary-panel admin-card admin-workers-panel">
      <div class="panel-title-row">
        <div>
          <h2>Worker 状态</h2>
          <p>
            最近 {{ overview?.active_window_hours ?? 24 }} 小时活跃 · 离线阈值 {{ overview?.online_threshold_seconds ?? 30 }} 秒 ·
            {{ overview?.generated_at ? humanDate(overview.generated_at) : "-" }}
          </p>
        </div>
        <button class="secondary-button" type="button" :disabled="loading" @click="emit('refresh')">{{ loading ? "刷新中..." : "刷新" }}</button>
      </div>

      <div class="admin-worker-queue">
        <span>测评排队 <strong>{{ summary?.queued_eval_jobs ?? 0 }}</strong></span>
        <span>AI 创建排队 <strong>{{ summary?.queued_builder_jobs ?? 0 }}</strong></span>
        <span>Job 运行中 <strong>{{ summary?.running_jobs ?? 0 }}</strong></span>
        <span>离线 <strong>{{ summary?.offline ?? 0 }}</strong></span>
      </div>

      <div class="admin-worker-table">
        <div class="admin-worker-table-head">
          <span>Worker</span>
          <span>状态</span>
          <span>当前任务</span>
          <span>最近心跳</span>
          <span>运行时长</span>
        </div>
        <div v-for="worker in workers" :key="worker.worker_id" class="admin-worker-table-row">
          <div class="admin-worker-main">
            <strong>{{ worker.worker_id }}</strong>
            <small>{{ worker.metadata?.opencode_base_url || "-" }}</small>
            <small>{{ worker.metadata?.workdir_host || "-" }}</small>
          </div>
          <span :class="['admin-publish-status', workerStatusTone(worker)]">{{ workerStatusText(worker) }}</span>
          <div class="admin-worker-job">
            <strong>{{ workerJobTypeText(worker.current_job?.type) }}</strong>
            <span>{{ workerCurrentJobText(worker) }}</span>
            <small v-if="worker.current_job">Job {{ worker.current_job.id }} · 尝试 {{ worker.current_job.attempts }} · {{ jobRuntimeText(worker) }}</small>
            <small v-if="worker.current_job?.error" class="admin-worker-error">{{ worker.current_job.error }}</small>
          </div>
          <span>{{ humanDate(worker.last_seen_at) }}</span>
          <span>{{ runtimeText(worker) }}</span>
        </div>
        <p v-if="!workers.length" class="field-help admin-workers-empty">最近没有 Worker 心跳。</p>
      </div>
    </section>
  </div>
</template>
