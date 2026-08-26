<script setup lang="ts">
import { Braces, Plus, Server } from "lucide-vue-next";
import { computed, nextTick, onMounted, ref, watch } from "vue";
import UiButton from "../../../components/ui/UiButton.vue";
import type { DeviceRole, WorkflowJsonSchema, WorkflowParameter, WorkflowValidationIssue } from "../../../types";
import WorkflowDeviceRoleCard from "./WorkflowDeviceRoleCard.vue";
import WorkflowSchemaFieldRows from "./WorkflowSchemaFieldRows.vue";
import WorkflowSchemaEditorModal from "./WorkflowSchemaEditorModal.vue";

const props = defineProps<{
  inputs: WorkflowParameter[];
  roles: DeviceRole[];
  target: "inputs" | "roles";
  readonly: boolean;
  issues?: WorkflowValidationIssue[];
}>();
const emit = defineEmits<{
  "add-input": [];
  "update-input": [id: string, patch: Record<string, unknown>];
  "remove-input": [id: string];
  "add-role": [];
  "update-role": [id: string, patch: Record<string, unknown>];
  "remove-role": [id: string];
}>();
const inputSection = ref<HTMLElement | null>(null);
const roleSection = ref<HTMLElement | null>(null);
const editingRoleId = ref<string | null>(null);
const editingRole = computed(() => props.roles.find((role) => role.id === editingRoleId.value));
const expandedRoleIds = ref<Set<string>>(new Set());
const initializedRoleIds = ref<Set<string>>(new Set());

onMounted(() => focusSection(props.target));
watch(() => props.target, (target) => void nextTick(() => focusSection(target)));
watch(
  () => props.roles.map((role) => role.id),
  (ids) => {
    const current = new Set(ids);
    const next = new Set([...expandedRoleIds.value].filter((id) => current.has(id)));
    if (initializedRoleIds.value.size) ids.filter((id) => !initializedRoleIds.value.has(id)).forEach((id) => next.add(id));
    initializedRoleIds.value = current;
    expandedRoleIds.value = next;
  },
  { immediate: true },
);
watch(
  () => props.issues,
  () => {
    const next = new Set(expandedRoleIds.value);
    props.roles.filter((role) => roleIssues(role).length).forEach((role) => next.add(role.id));
    expandedRoleIds.value = next;
  },
  { deep: true, immediate: true },
);

function focusSection(target: "inputs" | "roles"): void {
  const section = target === "inputs" ? inputSection.value : roleSection.value;
  section?.focus({ preventScroll: true });
  section?.scrollIntoView?.({ block: "nearest" });
}

function addInput(): void {
  const previousIds = new Set(props.inputs.map((item) => item.id));
  emit("add-input");
  void nextTick(() => {
    const added = props.inputs.find((item) => !previousIds.has(item.id));
    if (!added) return;
    const input = inputSection.value?.querySelector<HTMLInputElement>(`[data-workflow-item="${CSS.escape(added.id)}"] input`);
    input?.focus();
    input?.scrollIntoView({ block: "nearest" });
  });
}

function roleIssues(role: DeviceRole): WorkflowValidationIssue[] {
  return (props.issues ?? []).filter((item) => item.selection.type === "roles" && item.selection.itemId === role.id);
}

function roleSchema(role: DeviceRole): WorkflowJsonSchema {
  return role.schema ?? { type: "object", title: `${role.name || role.key} 参数`, description: "", properties: {}, required: [], additionalProperties: false };
}

function toggleRole(roleId: string): void {
  const next = new Set(expandedRoleIds.value);
  if (next.has(roleId)) next.delete(roleId);
  else next.add(roleId);
  expandedRoleIds.value = next;
}

function addRole(): void {
  const previousIds = new Set(props.roles.map((item) => item.id));
  emit("add-role");
  void nextTick(() => {
    const added = props.roles.find((item) => !previousIds.has(item.id));
    if (!added) return;
    expandedRoleIds.value = new Set([...expandedRoleIds.value, added.id]);
    const input = roleSection.value?.querySelector<HTMLInputElement>(`[data-device-role-id="${CSS.escape(added.id)}"] input[aria-label="角色 Key"]`);
    input?.focus();
    input?.scrollIntoView({ block: "nearest" });
  });
}
</script>

<template>
  <section class="workflow-document workflow-global-settings">
    <header class="workflow-document-head">
      <span><Braces :size="18" /></span>
      <div>
        <small>全局配置</small>
        <h2>全局输入</h2>
        <p>声明流程级输入参数和采集目标使用的逻辑设备角色。</p>
      </div>
    </header>

    <section ref="inputSection" :class="['workflow-settings-section', props.target === 'inputs' && 'is-target']" tabindex="-1" aria-labelledby="workflow-inputs-heading">
      <header class="workflow-settings-section-head">
        <div><Braces :size="16" /><span><h3 id="workflow-inputs-heading">输入参数 <small>{{ props.inputs.length }}</small></h3><p>可被步骤和采集参数绑定的流程级输入。</p></span></div>
        <UiButton variant="secondary" :disabled="props.readonly" @click="addInput"><template #icon><Plus /></template>添加输入</UiButton>
      </header>
      <div class="workflow-settings-list">
        <WorkflowSchemaFieldRows kind="input" :items="props.inputs" :readonly="props.readonly" @change="(id, patch) => emit('update-input', id, patch)" @remove="emit('remove-input', $event)" />
        <div v-if="props.inputs.length === 0" class="workflow-empty">当前没有输入参数。</div>
      </div>
    </section>

    <section ref="roleSection" :class="['workflow-settings-section', props.target === 'roles' && 'is-target']" tabindex="-1" aria-labelledby="workflow-roles-heading">
      <header class="workflow-settings-section-head">
        <div><Server :size="16" /><span><h3 id="workflow-roles-heading">设备角色 <small>{{ props.roles.length }}</small></h3><p>用逻辑角色描述采集目标，不保存运行时设备。</p></span></div>
        <UiButton variant="secondary" :disabled="props.readonly" @click="addRole"><template #icon><Plus /></template>添加设备角色</UiButton>
      </header>
      <div class="workflow-settings-list">
        <WorkflowDeviceRoleCard v-for="(item, itemIndex) in props.roles" :key="item.id" :data-workflow-item="item.id" :data-workflow-index="itemIndex" :role="item" :expanded="expandedRoleIds.has(item.id)" :readonly="props.readonly" :issues="roleIssues(item)" @toggle="toggleRole(item.id)" @change="emit('update-role', item.id, $event)" @remove="emit('remove-role', item.id)" @edit-schema="editingRoleId = item.id" />
        <div v-if="props.roles.length === 0" class="workflow-empty">当前没有设备角色。</div>
      </div>
    </section>
    <WorkflowSchemaEditorModal v-if="editingRole" :open="true" :schema="roleSchema(editingRole)" :field-key="editingRole.key || editingRole.name" :readonly="props.readonly" :root-object-only="true" :identifier-only="true" @close="editingRoleId = null" @confirm="(schema) => { emit('update-role', editingRole!.id, { schema }); editingRoleId = null; }" />
  </section>
</template>
