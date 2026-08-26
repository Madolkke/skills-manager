<script setup lang="ts">
import { AlertCircle, ChevronDown, ChevronRight, Server, Trash2 } from "lucide-vue-next";
import UiButton from "../../../components/ui/UiButton.vue";
import UiIconButton from "../../../components/ui/UiIconButton.vue";
import type { DeviceRole, WorkflowValidationIssue } from "../../../types";
import { isWorkflowDeviceSchemaProjectable, workflowDeviceRoleExpressionPath, workflowDeviceRoleSchemaFieldCount } from "../workflowDeviceRoleSchema";
import { workflowSchemaSummary } from "../workflowJsonSchema";

const props = defineProps<{
  role: DeviceRole;
  expanded: boolean;
  readonly: boolean;
  issues: WorkflowValidationIssue[];
}>();
const emit = defineEmits<{
  toggle: [];
  change: [patch: Record<string, unknown>];
  remove: [];
  "edit-schema": [];
}>();

function schemaStatus(): string {
  if (!props.role.schema) return "未配置参数 Schema";
  if (!isWorkflowDeviceSchemaProjectable(props.role.schema)) return "Schema 存在校验问题";
  return `参数 Schema · ${workflowDeviceRoleSchemaFieldCount(props.role)} 个根字段`;
}

function fieldPath(key: string): string {
  return `${workflowDeviceRoleExpressionPath(props.role)}.${key}`;
}
</script>

<template>
  <article :data-device-role-id="props.role.id" :class="['workflow-device-role-card', props.expanded && 'is-expanded', props.issues.length && 'has-issues']">
    <header class="workflow-device-role-card-head">
      <button type="button" class="workflow-device-role-toggle" :aria-expanded="props.expanded" :aria-label="`${props.expanded ? '收起' : '展开'}设备角色 ${props.role.name || props.role.key || '未命名'}`" @click="emit('toggle')">
        <ChevronDown v-if="props.expanded" :size="17" /><ChevronRight v-else :size="17" />
        <Server :size="17" />
        <span class="workflow-device-role-title"><strong>{{ props.role.name || "未命名设备角色" }}</strong><code>{{ props.role.key || "未设置 Key" }}</code></span>
        <span :class="['workflow-device-role-badge', props.role.required && 'is-required']">{{ props.role.required ? "必填" : "可选" }}</span>
        <span class="workflow-device-role-schema-status">{{ schemaStatus() }}</span>
        <span v-if="props.issues.length" class="workflow-device-role-error"><AlertCircle :size="15" />{{ props.issues.length }} 项问题</span>
      </button>
      <div class="workflow-device-role-actions">
        <UiButton size="sm" variant="secondary" :disabled="props.readonly" @click="emit('edit-schema')">{{ props.role.schema ? "编辑参数 Schema" : "配置参数 Schema" }}</UiButton>
        <UiIconButton label="删除设备角色" size="sm" variant="danger" :disabled="props.readonly" @click="emit('remove')"><Trash2 /></UiIconButton>
      </div>
    </header>

    <div v-if="props.expanded" class="workflow-device-role-card-body">
      <div class="workflow-device-role-fields">
        <label class="workflow-setting-field"><span>角色 Key</span><input class="workflow-key-input" :value="props.role.key" aria-label="角色 Key" placeholder="primary" :disabled="props.readonly" @input="emit('change', { key: ($event.target as HTMLInputElement).value })" /></label>
        <label class="workflow-setting-field"><span>角色名称</span><input :value="props.role.name" aria-label="角色名称" placeholder="主设备" :disabled="props.readonly" @input="emit('change', { name: ($event.target as HTMLInputElement).value })" /></label>
        <label class="workflow-setting-field workflow-device-role-description"><span>角色说明</span><input :value="props.role.description" aria-label="角色说明" placeholder="角色用途（可选）" :disabled="props.readonly" @input="emit('change', { description: ($event.target as HTMLInputElement).value })" /></label>
        <label class="workflow-check workflow-setting-required"><input type="checkbox" :checked="props.role.required" :disabled="props.readonly" @change="emit('change', { required: ($event.target as HTMLInputElement).checked })" />必填</label>
      </div>
      <section class="workflow-device-role-path">
        <span>表达式根路径</span><code>{{ workflowDeviceRoleExpressionPath(props.role) }}</code><small>使用角色 Key；显示名称变更不会影响表达式。</small>
      </section>
      <section class="workflow-device-role-schema-summary">
        <div><strong>设备参数 Schema</strong><p v-if="!props.role.schema">尚未配置。角色仍可用于采集目标，但不会提供表达式变量。</p><p v-else>{{ workflowSchemaSummary(props.role.schema) }}。{{ isWorkflowDeviceSchemaProjectable(props.role.schema) ? "已投影到表达式环境。" : "修复校验问题后才会投影到表达式环境。" }}</p></div>
        <div v-if="isWorkflowDeviceSchemaProjectable(props.role.schema) && Object.keys(props.role.schema.properties).length" class="workflow-device-role-paths">
          <code v-for="key in Object.keys(props.role.schema.properties)" :key="key">{{ fieldPath(key) }}</code>
        </div>
      </section>
      <ul v-if="props.issues.length" class="workflow-device-role-issues"><li v-for="issue in props.issues" :key="issue.id">{{ issue.message }}</li></ul>
    </div>
  </article>
</template>
