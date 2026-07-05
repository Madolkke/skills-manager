<script setup lang="ts">
import { FolderOpen, MessageSquarePlus } from "lucide-vue-next";
import DropdownSelect from "../../../components/DropdownSelect.vue";
import type { DropdownSelectOption } from "../../../components/dropdown";
import type { SkillBuilderRunSelection } from "../../../types";

defineProps<{
  selection: SkillBuilderRunSelection;
  providerOptions: DropdownSelectOption[];
  modelOptions: DropdownSelectOption[];
  providerLoadError?: string;
  canCreateSession: boolean;
  newSessionDisabledReason: string;
  canOpenWorkspace: boolean;
  workspaceOpen: boolean;
  workspaceButtonText: string;
  canOpenSubmit: boolean;
  submitDisabledReason: string;
}>();

const emit = defineEmits<{
  provider: [providerId: string];
  model: [modelId: string];
  newSession: [];
  toggleWorkspace: [];
  submit: [];
}>();
</script>

<template>
  <header class="builder-main-toolbar">
    <div class="builder-toolbar-title">
      <span class="eyebrow">AI 创建 Skill</span>
      <h1>对话生成并整理工作区文件</h1>
    </div>
    <div class="builder-toolbar-model">
      <span class="builder-toolbar-label">运行配置</span>
      <div :class="['builder-model-fields', !selection.provider_id && 'default-mode']">
        <DropdownSelect
          :model-value="selection.provider_id ?? ''"
          :options="providerOptions"
          aria-label="选择 Opencode provider"
          compact
          @update:model-value="emit('provider', $event)"
        />
        <DropdownSelect
          v-if="selection.provider_id"
          :model-value="selection.model_id ?? ''"
          :options="modelOptions"
          placeholder="选择 Model"
          aria-label="选择 Opencode model"
          compact
          @update:model-value="emit('model', $event)"
        />
        <span v-else class="builder-default-model-pill">使用 Opencode 默认模型</span>
      </div>
      <p v-if="providerLoadError" class="builder-toolbar-hint danger">{{ providerLoadError }}</p>
    </div>
    <div class="builder-toolbar-actions">
      <button class="secondary-button" type="button" :disabled="!canCreateSession" :title="newSessionDisabledReason" @click="emit('newSession')">
        <MessageSquarePlus :size="16" />
        新建会话
      </button>
      <button class="secondary-button" type="button" :disabled="!canOpenWorkspace" :class="workspaceOpen && 'active'" @click="emit('toggleWorkspace')">
        <FolderOpen :size="16" />
        {{ workspaceButtonText }}
      </button>
      <button class="primary-button" type="button" :disabled="!canOpenSubmit" :title="submitDisabledReason" @click="emit('submit')">
        提交 Skill
      </button>
    </div>
  </header>
</template>
