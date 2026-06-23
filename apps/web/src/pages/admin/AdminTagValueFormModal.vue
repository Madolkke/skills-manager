<script setup lang="ts">
import { ref, watch } from "vue";
import Modal from "../../components/Modal.vue";
import type { TagGroup, TagValueOption } from "../../types";

const props = defineProps<{ group: TagGroup; value?: TagValueOption | null }>();
const emit = defineEmits<{
  close: [];
  submit: [payload: { value: string; display_name?: string | null; description?: string; sort_order?: number }];
}>();

const form = ref({ value: "", display_name: "", description: "", sort_order: 0 });
const editing = ref(false);

watch(() => props.value, (value) => {
  editing.value = Boolean(value);
  form.value = {
    value: value?.value ?? "",
    display_name: value?.display_name ?? "",
    description: value?.description ?? "",
    sort_order: value?.sort_order ?? 0,
  };
}, { immediate: true });

function submit(): void {
  if (!form.value.value.trim()) return;
  emit("submit", {
    value: form.value.value.trim(),
    display_name: form.value.display_name.trim() || null,
    description: form.value.description.trim(),
    sort_order: Number(form.value.sort_order) || 0,
  });
  emit("close");
}
</script>

<template>
  <Modal
    :title="editing ? '编辑 Tag 值' : '添加 Tag 值'"
    :description="`当前 Tag Group：${group.display_name}（${group.id}）`"
    @close="emit('close')"
  >
    <div class="form-stack admin-modal-form">
      <label class="field-label">
        <span>Tag 值</span>
        <input v-model="form.value" placeholder="支持中文、空格、符号和 Emoji" />
      </label>
      <label class="field-label">
        <span>显示名称</span>
        <input v-model="form.display_name" placeholder="可选；为空时直接显示 Tag 值" />
      </label>
      <label class="field-label">
        <span>备注</span>
        <textarea v-model="form.description" placeholder="说明这个 Tag 值适合标记哪些 Skill" />
      </label>
      <label class="field-label compact">
        <span>排序</span>
        <input v-model.number="form.sort_order" type="number" />
        <small class="field-help">数字越小越靠前，默认 0。</small>
      </label>
      <div class="modal-actions">
        <button class="secondary-button" type="button" @click="emit('close')">取消</button>
        <button class="primary-button" type="button" :disabled="!form.value.trim()" @click="submit">
          {{ editing ? "保存修改" : "添加" }}
        </button>
      </div>
    </div>
  </Modal>
</template>
