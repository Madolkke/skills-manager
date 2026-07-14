<script setup lang="ts">
import { Braces, Plus, Server, Trash2 } from "lucide-vue-next";
import { nextTick, onMounted, ref, watch } from "vue";
import UiButton from "../../../components/ui/UiButton.vue";
import UiIconButton from "../../../components/ui/UiIconButton.vue";
import type { DeviceRole, WorkflowParameter } from "../../../types";

const props = defineProps<{
  inputs: WorkflowParameter[];
  roles: DeviceRole[];
  target: "inputs" | "roles";
  readonly: boolean;
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

onMounted(() => focusSection(props.target));
watch(() => props.target, (target) => void nextTick(() => focusSection(target)));

function focusSection(target: "inputs" | "roles"): void {
  const section = target === "inputs" ? inputSection.value : roleSection.value;
  section?.focus({ preventScroll: true });
  section?.scrollIntoView?.({ block: "nearest" });
}
</script>

<template>
  <section class="workflow-document workflow-global-settings">
    <header class="workflow-document-head">
      <span><Braces :size="18" /></span>
      <div>
        <small>GLOBAL INPUTS</small>
        <h2>全局输入</h2>
        <p>声明流程级输入参数和采集目标使用的逻辑设备角色。</p>
      </div>
    </header>

    <section ref="inputSection" :class="['workflow-settings-section', props.target === 'inputs' && 'is-target']" tabindex="-1" aria-labelledby="workflow-inputs-heading">
      <header class="workflow-settings-section-head">
        <div><Braces :size="16" /><span><h3 id="workflow-inputs-heading">输入参数 <small>{{ props.inputs.length }}</small></h3><p>可被步骤和采集参数绑定的流程级输入。</p></span></div>
        <UiButton variant="secondary" :disabled="props.readonly" @click="emit('add-input')"><template #icon><Plus /></template>添加输入</UiButton>
      </header>
      <div class="workflow-settings-list">
        <div v-for="item in props.inputs" :key="item.id" class="workflow-setting-row is-input">
          <label class="workflow-setting-field"><span>参数 Key</span><input class="workflow-key-input" :value="item.key" aria-label="输入 Key" placeholder="tenant" :disabled="props.readonly" @input="emit('update-input', item.id, { key: ($event.target as HTMLInputElement).value })" /></label>
          <label class="workflow-setting-field"><span>参数名称</span><input :value="item.name" aria-label="输入名称" placeholder="租户" :disabled="props.readonly" @input="emit('update-input', item.id, { name: ($event.target as HTMLInputElement).value })" /></label>
          <label class="workflow-setting-field"><span>参数说明</span><input :value="item.description" aria-label="输入说明" placeholder="参数用途（可选）" :disabled="props.readonly" @input="emit('update-input', item.id, { description: ($event.target as HTMLInputElement).value })" /></label>
          <label class="workflow-setting-field"><span>数据类型</span><select :value="item.dataType" aria-label="输入类型" :disabled="props.readonly" @change="emit('update-input', item.id, { dataType: ($event.target as HTMLSelectElement).value })">
            <option v-for="type in ['string', 'integer', 'number', 'boolean', 'array', 'object']" :key="type" :value="type">{{ type }}</option>
          </select></label>
          <UiIconButton label="删除输入" size="sm" variant="danger" :disabled="props.readonly" @click="emit('remove-input', item.id)"><Trash2 /></UiIconButton>
        </div>
        <div v-if="props.inputs.length === 0" class="workflow-empty">当前没有输入参数。</div>
      </div>
    </section>

    <section ref="roleSection" :class="['workflow-settings-section', props.target === 'roles' && 'is-target']" tabindex="-1" aria-labelledby="workflow-roles-heading">
      <header class="workflow-settings-section-head">
        <div><Server :size="16" /><span><h3 id="workflow-roles-heading">设备角色 <small>{{ props.roles.length }}</small></h3><p>用逻辑角色描述采集目标，不保存运行时设备。</p></span></div>
        <UiButton variant="secondary" :disabled="props.readonly" @click="emit('add-role')"><template #icon><Plus /></template>添加设备角色</UiButton>
      </header>
      <div class="workflow-settings-list">
        <div v-for="item in props.roles" :key="item.id" class="workflow-setting-row is-role">
          <label class="workflow-setting-field"><span>角色 Key</span><input class="workflow-key-input" :value="item.key" aria-label="角色 Key" placeholder="primary" :disabled="props.readonly" @input="emit('update-role', item.id, { key: ($event.target as HTMLInputElement).value })" /></label>
          <label class="workflow-setting-field"><span>角色名称</span><input :value="item.name" aria-label="角色名称" placeholder="主设备" :disabled="props.readonly" @input="emit('update-role', item.id, { name: ($event.target as HTMLInputElement).value })" /></label>
          <label class="workflow-setting-field"><span>角色说明</span><input :value="item.description" aria-label="角色说明" placeholder="角色用途（可选）" :disabled="props.readonly" @input="emit('update-role', item.id, { description: ($event.target as HTMLInputElement).value })" /></label>
          <label class="workflow-check workflow-setting-required"><input type="checkbox" :checked="item.required" :disabled="props.readonly" @change="emit('update-role', item.id, { required: ($event.target as HTMLInputElement).checked })" />必填</label>
          <UiIconButton label="删除设备角色" size="sm" variant="danger" :disabled="props.readonly" @click="emit('remove-role', item.id)"><Trash2 /></UiIconButton>
        </div>
        <div v-if="props.roles.length === 0" class="workflow-empty">当前没有设备角色。</div>
      </div>
    </section>
  </section>
</template>
