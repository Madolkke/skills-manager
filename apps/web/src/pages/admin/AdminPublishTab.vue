<script setup lang="ts">
import { computed } from "vue";
import type { PublishRecord } from "../../types";

const props = defineProps<{ records: PublishRecord[] }>();
const emit = defineEmits<{
  confirmRecord: [record: PublishRecord];
  cancelRecord: [record: PublishRecord];
}>();

const pendingRecords = computed(() => props.records.filter((record) => record.status === "pending_confirmation"));
const completedRecords = computed(() => props.records.filter((record) => record.status !== "pending_confirmation"));
</script>

<template>
  <div class="admin-tab-stack">
    <section class="primary-panel admin-card">
      <div class="panel-title-row">
        <h2>待确认发布单</h2>
        <span class="tag-chip muted">{{ pendingRecords.length }}</span>
      </div>
      <div class="admin-publish-record-list">
        <article v-for="record in pendingRecords" :key="record.id" class="admin-publish-record">
          <div>
            <strong>{{ record.skill?.slug ?? record.skill_id }}</strong>
            <span>{{ record.skill_version?.version ?? record.skill_version_id }} · {{ record.publish_target?.name ?? record.target_name ?? record.publish_target_id }}</span>
          </div>
          <div class="button-row">
            <button class="secondary-button" type="button" @click="emit('cancelRecord', record)">取消</button>
            <button class="primary-button" type="button" @click="emit('confirmRecord', record)">确认发布</button>
          </div>
        </article>
        <p v-if="!pendingRecords.length" class="field-help">没有待确认发布单。</p>
      </div>
    </section>

    <section class="primary-panel admin-card">
      <div class="panel-title-row">
        <h2>发布记录</h2>
        <span class="tag-chip muted">{{ completedRecords.length }}</span>
      </div>
      <div class="admin-publish-record-list">
        <article v-for="record in completedRecords" :key="record.id" class="admin-publish-record">
          <div>
            <strong>{{ record.skill?.slug ?? record.skill_id }}</strong>
            <span>{{ record.status }} · {{ record.publish_target?.name ?? record.target_name ?? record.publish_target_id }}</span>
          </div>
        </article>
        <p v-if="!completedRecords.length" class="field-help">暂无已完成发布记录。</p>
      </div>
    </section>
  </div>
</template>
