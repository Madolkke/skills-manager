<script setup lang="ts">
import { Braces, Plus, Server, Trash2 } from "lucide-vue-next";
import type { DeviceRole, WorkflowParameter } from "../../../types";

const props = defineProps<{ mode: "inputs" | "roles"; inputs: WorkflowParameter[]; roles: DeviceRole[]; readonly: boolean }>();
const emit = defineEmits<{ add: []; update: [id: string, patch: Record<string, unknown>]; remove: [id: string] }>();
</script>

<template>
  <section class="workflow-document">
    <header class="workflow-document-head">
      <span><Braces v-if="props.mode === 'inputs'" :size="18" /><Server v-else :size="18" /></span>
      <div><small>{{ props.mode === "inputs" ? "GLOBAL INPUTS" : "DEVICE ROLES" }}</small><h2>{{ props.mode === "inputs" ? "全局输入" : "设备角色" }}</h2><p>{{ props.mode === "inputs" ? "声明流程中可被步骤和采集绑定的输入。" : "用逻辑角色描述采集目标，不保存运行时设备。" }}</p></div>
      <button class="secondary-button" type="button" :disabled="props.readonly" @click="emit('add')"><Plus :size="15" />添加</button>
    </header>
    <div class="workflow-settings-list">
      <div v-for="item in props.mode === 'inputs' ? props.inputs : props.roles" :key="item.id" class="workflow-setting-row">
        <input class="workflow-key-input" :value="item.key" aria-label="Key" :disabled="props.readonly" @input="emit('update', item.id, { key: ($event.target as HTMLInputElement).value })" />
        <input :value="item.name" aria-label="名称" :disabled="props.readonly" @input="emit('update', item.id, { name: ($event.target as HTMLInputElement).value })" />
        <input :value="item.description" aria-label="说明" :disabled="props.readonly" @input="emit('update', item.id, { description: ($event.target as HTMLInputElement).value })" />
        <select v-if="props.mode === 'inputs'" :value="(item as WorkflowParameter).dataType" aria-label="类型" :disabled="props.readonly" @change="emit('update', item.id, { dataType: ($event.target as HTMLSelectElement).value })">
          <option v-for="type in ['string', 'integer', 'number', 'boolean', 'array', 'object']" :key="type" :value="type">{{ type }}</option>
        </select>
        <label class="workflow-check"><input type="checkbox" :checked="item.required" :disabled="props.readonly" @change="emit('update', item.id, { required: ($event.target as HTMLInputElement).checked })" />必填</label>
        <button class="icon-button mini" type="button" aria-label="删除" :disabled="props.readonly" @click="emit('remove', item.id)"><Trash2 :size="15" /></button>
      </div>
      <div v-if="(props.mode === 'inputs' ? props.inputs : props.roles).length === 0" class="workflow-empty">当前没有{{ props.mode === "inputs" ? "全局输入" : "设备角色" }}。</div>
    </div>
  </section>
</template>
