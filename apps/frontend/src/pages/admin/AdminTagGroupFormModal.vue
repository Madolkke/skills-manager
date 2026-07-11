<script setup lang="ts">
import { ref, watch } from "vue";
import Modal from "../../components/Modal.vue";
import type { TagGroup } from "../../types";

const props = defineProps<{ group?: TagGroup | null }>();
const emit = defineEmits<{
  close: [];
  submit: [payload: { id?: string; display_name: string; description?: string; sort_order?: number; required?: boolean; free_form?: boolean; initial_value?: string }];
}>();

const form = ref({ id: "", display_name: "", description: "", sort_order: 0, required: false, free_form: false, initial_value: "" });
const editing = ref(false);

watch(() => props.group, (group) => {
  editing.value = Boolean(group);
  form.value = {
    id: group?.id ?? "",
    display_name: group?.display_name ?? "",
    description: group?.description ?? "",
    sort_order: group?.sort_order ?? 0,
    required: group?.required ?? false,
    free_form: group?.free_form ?? false,
    initial_value: "",
  };
}, { immediate: true });

function submit(): void {
  if (!form.value.display_name.trim() || (!editing.value && !form.value.id.trim())) return;
  if (!editing.value && form.value.required && !form.value.free_form && !form.value.initial_value.trim()) return;
  emit("submit", {
    id: editing.value ? undefined : form.value.id.trim(),
    display_name: form.value.display_name.trim(),
    description: form.value.description.trim(),
    sort_order: Number(form.value.sort_order) || 0,
    required: form.value.required,
    free_form: form.value.free_form,
    initial_value: editing.value ? undefined : form.value.initial_value.trim(),
  });
  emit("close");
}
</script>

<template>
  <Modal
    :title="editing ? '编辑 Tag Group' : '新建 Tag Group'"
    description="枚举组只允许选择后台候选值；自由组也允许用户输入新值并沉淀为全局候选。"
    @close="emit('close')"
  >
    <div class="form-stack admin-modal-form">
      <label class="field-label">
        <span>Group ID</span>
        <input v-model="form.id" :disabled="editing" placeholder="例如 domain" />
      </label>
      <label class="field-label">
        <span>显示名称</span>
        <input v-model="form.display_name" placeholder="例如 业务领域" />
      </label>
      <label class="field-label">
        <span>备注</span>
        <textarea v-model="form.description" placeholder="说明这个 Tag Group 的语义和使用场景" />
      </label>
      <label class="field-label compact">
        <span>排序</span>
        <input v-model.number="form.sort_order" type="number" />
        <small class="field-help">数字越小越靠前，默认 0。</small>
      </label>
      <section class="tag-group-requirement-field" aria-labelledby="tag-group-mode-title">
        <div>
          <strong id="tag-group-mode-title">输入模式</strong>
          <p>{{ form.free_form ? "用户可输入任意 Tag 值，后台候选作为基础建议。" : "用户只能选择后台已经维护的 Tag 值。" }}</p>
        </div>
        <div class="tag-group-requirement-toggle" role="radiogroup" aria-label="Tag Group 输入模式">
          <button type="button" :class="{ active: !form.free_form }" role="radio" :aria-checked="!form.free_form" @click="form.free_form = false">
            枚举组
          </button>
          <button type="button" :class="{ active: form.free_form }" role="radio" :aria-checked="form.free_form" @click="form.free_form = true; form.initial_value = ''">
            自由组
          </button>
        </div>
      </section>
      <section class="tag-group-requirement-field" aria-labelledby="tag-group-requirement-title">
        <div>
          <strong id="tag-group-requirement-title">保存要求</strong>
          <p>{{ form.free_form ? "自由必选组无需预置候选，但 Skill 保存时必须输入至少一个值。" : (editing ? "必选组在 Skill 保存 Tags 时至少选择一个 Tag；空组不能设为必选。" : "新建必选组时需要同时创建第一个 Tag 值。") }}</p>
        </div>
        <div class="tag-group-requirement-toggle" role="radiogroup" aria-label="Tag Group 保存要求">
          <button type="button" :class="{ active: !form.required }" role="radio" :aria-checked="!form.required" @click="form.required = false">
            可选
          </button>
          <button type="button" :class="{ active: form.required }" role="radio" :aria-checked="form.required" @click="form.required = true">
            必选
          </button>
        </div>
      </section>
      <label v-if="!editing && form.required && !form.free_form" class="field-label tag-group-initial-value">
        <span>初始 Tag 值</span>
        <input v-model="form.initial_value" placeholder="例如 router" />
        <small class="field-help">创建后可继续在右侧维护更多 Tag 值。</small>
      </label>
      <div class="modal-actions">
        <button class="secondary-button" type="button" @click="emit('close')">取消</button>
        <button class="primary-button" type="button" :disabled="!form.display_name.trim() || (!editing && !form.id.trim()) || (!editing && form.required && !form.free_form && !form.initial_value.trim())" @click="submit">
          {{ editing ? "保存修改" : "创建" }}
        </button>
      </div>
    </div>
  </Modal>
</template>
