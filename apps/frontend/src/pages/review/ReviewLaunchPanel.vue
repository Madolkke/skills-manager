<script setup lang="ts">
import DropdownSelect from "../../components/DropdownSelect.vue";
import type { DropdownSelectOption } from "../../components/dropdown";
import type { PublishTarget, ReviewerCandidateGroup, SkillVersion } from "../../types";

defineProps<{
  canManage: boolean;
  busy: boolean;
  manageReason: string;
  versionOptions: DropdownSelectOption[];
  selectedVersionId: string;
  selectedVersion: SkillVersion | null;
  targets: PublishTarget[];
  selectedTargets: string[];
  reviewerGroups: ReviewerCandidateGroup[];
  selectedReviewerGroupIds: string[];
  directReviewerInput: string;
  explicitReviewerCount: number;
}>();

const emit = defineEmits<{
  "update:selectedVersionId": [value: string];
  "update:directReviewerInput": [value: string];
  toggleReviewerGroup: [groupId: string];
  toggleTarget: [targetId: string];
  create: [];
}>();
</script>

<template>
  <aside class="primary-panel review-launch-panel">
    <div class="review-panel-head">
      <div>
        <h2>发起评审</h2>
        <p>选择版本、评审对象和自动提交发布源。</p>
      </div>
    </div>

    <div v-if="canManage" class="review-launch-form">
      <label class="field-label">
        <span>Skill 版本</span>
        <DropdownSelect :model-value="selectedVersionId" :options="versionOptions" compact @update:model-value="emit('update:selectedVersionId', $event)" />
      </label>

      <div v-if="selectedVersion" class="review-selected-version">
        <span>将评审</span>
        <strong>{{ selectedVersion.version }}</strong>
        <p>{{ selectedVersion.display_name || selectedVersion.change_summary || "当前版本没有备注。" }}</p>
      </div>

      <div class="field-label">
        <span>评审对象</span>
        <div class="review-target-list">
          <button
            v-for="group in reviewerGroups"
            :key="group.id"
            type="button"
            :class="['review-target-row', { active: selectedReviewerGroupIds.includes(group.id) }]"
            @click="emit('toggleReviewerGroup', group.id)"
          >
            <span class="review-target-main">
              <strong>{{ group.name }}</strong>
              <small>{{ group.description || group.id }}</small>
            </span>
            <span class="review-target-state">{{ selectedReviewerGroupIds.includes(group.id) ? "已选" : `${group.member_count} 人` }}</span>
          </button>
          <span v-if="!reviewerGroups.length" class="field-help">后台还没有可选用户组；也可以直接输入用户身份 ID。</span>
        </div>
        <input
          class="review-direct-reviewers"
          :value="directReviewerInput"
          placeholder="补充单个用户，多个身份 ID 用空格、逗号或分号分隔"
          @input="emit('update:directReviewerInput', ($event.target as HTMLInputElement).value)"
        />
        <small class="field-help">
          {{ explicitReviewerCount ? `本次将快照 ${explicitReviewerCount} 位评审人。` : "未选择时，将使用当前 reviewer 角色授权快照。" }}
        </small>
      </div>

      <div class="field-label">
        <span>自动提交发布源</span>
        <div class="review-target-list">
          <button
            v-for="target in targets"
            :key="target.id"
            type="button"
            :class="['review-target-row', { active: selectedTargets.includes(target.id) }]"
            @click="emit('toggleTarget', target.id)"
          >
            <span class="review-target-main">
              <strong>{{ target.name }}</strong>
              <small>{{ target.description || target.target_key }}</small>
            </span>
            <span class="review-target-state">{{ selectedTargets.includes(target.id) ? "已选" : target.auto_publish_enabled ? "自动发布" : "后台确认" }}</span>
          </button>
          <span v-if="!targets.length" class="field-help">后台还没有启用的发布源。</span>
        </div>
      </div>

      <button class="primary-button full-width" type="button" :disabled="busy || !selectedVersionId" :title="manageReason || (!selectedVersionId ? '需要先选择一个 Skill 版本。' : '')" @click="emit('create')">发起评审</button>
    </div>
    <p v-else class="field-help permission-hint review-launch-permission">当前身份需要 maintainer、owner 或 admin 才能发起评审。</p>
  </aside>
</template>
