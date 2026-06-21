<script setup lang="ts">
import { Check, Edit3, Plus, X } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import DropdownSelect from "../../../components/DropdownSelect.vue";
import type { DropdownSelectOption } from "../../../components/dropdown";
import { humanDate } from "../../../lib/format";
import type { EvalSetSummary } from "../../../types";

const props = defineProps<{
  evalSets: EvalSetSummary[];
  selectedId: string;
  active: EvalSetSummary | null;
  caseCount: number;
  busy?: boolean;
}>();
const emit = defineEmits<{
  select: [evalSetId: string];
  create: [payload: { name: string; description: string }];
  update: [payload: { name: string; description: string }];
}>();

const creating = ref(false);
const editing = ref(false);
const name = ref("");
const description = ref("");

const options = computed<DropdownSelectOption[]>(() =>
  props.evalSets.map((evalSet) => ({
    value: evalSet.id,
    label: evalSet.name,
    description: `${humanDate(evalSet.updated_at)} 更新`,
  })),
);

watch(() => [props.active?.id, props.active?.name, props.active?.description] as const, () => {
  cancelForms();
});

/** 打开新建测评集表单，并初始化输入内容。 */
function startCreate(): void {
  creating.value = true;
  editing.value = false;
  name.value = "";
  description.value = "";
}

/** 打开当前测评集编辑表单。 */
function startEdit(): void {
  if (!props.active) return;
  editing.value = true;
  creating.value = false;
  name.value = props.active.name;
  description.value = props.active.description ?? "";
}

/** 关闭内联表单并清空临时输入。 */
function cancelForms(): void {
  creating.value = false;
  editing.value = false;
  name.value = "";
  description.value = "";
}

/** 提交新建或编辑表单。 */
function submit(): void {
  const cleanName = name.value.trim();
  if (!cleanName || props.busy) return;
  const payload = { name: cleanName, description: description.value.trim() };
  if (creating.value) emit("create", payload);
  if (editing.value) emit("update", payload);
}
</script>

<template>
  <section class="evalset-switcher">
    <div class="evalset-title-row"><span class="green-dot" /><span>当前测评集</span></div>
    <DropdownSelect
      :model-value="selectedId"
      :options="options"
      aria-label="选择测评集"
      @update:model-value="emit('select', $event)"
    />
    <form class="evalset-card compact" @submit.prevent="submit">
      <div class="evalset-card-head">
        <div v-if="editing" class="evalset-card-editor">
          <label>
            <span>测评集名称</span>
            <input v-model="name" maxlength="120" placeholder="例如：核心回归">
          </label>
          <label>
            <span>描述</span>
            <textarea v-model="description" maxlength="1000" rows="3" placeholder="说明这组测试覆盖的场景" />
          </label>
        </div>
        <div v-else>
          <h1>{{ active?.name ?? "未选择测评集" }}</h1>
          <p>{{ active?.description || "暂无描述。" }}</p>
        </div>
        <div v-if="editing" class="evalset-card-tools">
          <button class="icon-button mini active" type="submit" aria-label="保存测评集" :disabled="busy || !name.trim()">
            <Check :size="15" />
          </button>
          <button class="icon-button mini" type="button" aria-label="取消编辑测评集" :disabled="busy" @click="cancelForms">
            <X :size="15" />
          </button>
        </div>
        <button v-else class="icon-button mini" type="button" aria-label="编辑测评集" :disabled="!active" @click="startEdit">
          <Edit3 :size="15" />
        </button>
      </div>
      <div class="mini-grid">
        <span>测试例<b>{{ caseCount }}</b></span>
        <span>创建时间<b>{{ humanDate(active?.created_at) }}</b></span>
        <span>更新时间<b>{{ humanDate(active?.updated_at) }}</b></span>
      </div>
    </form>
    <form v-if="creating" class="evalset-inline-form" @submit.prevent="submit">
      <label>
        <span>测评集名称</span>
        <input v-model="name" maxlength="120" placeholder="例如：核心回归">
      </label>
      <label>
        <span>描述</span>
        <textarea v-model="description" maxlength="1000" rows="3" placeholder="说明这组测试覆盖的场景" />
      </label>
      <div class="button-row">
        <button class="primary-button" type="submit" :disabled="busy || !name.trim()">
          <Check :size="16" />
          创建
        </button>
        <button class="secondary-button" type="button" :disabled="busy" @click="cancelForms">
          <X :size="16" />
          取消
        </button>
      </div>
    </form>
    <button v-else class="secondary-button full-width" type="button" @click="startCreate">
      <Plus :size="16" />
      新建测评集
    </button>
  </section>
</template>
