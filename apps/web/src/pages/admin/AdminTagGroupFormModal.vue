<script setup lang="ts">
import { ref, watch } from "vue";
import Modal from "../../components/Modal.vue";
import type { TagGroup } from "../../types";

const props = defineProps<{ group?: TagGroup | null }>();
const emit = defineEmits<{
  close: [];
  submit: [payload: { id?: string; display_name: string; description?: string; sort_order?: number }];
}>();

const form = ref({ id: "", display_name: "", description: "", sort_order: 0 });
const editing = ref(false);

watch(() => props.group, (group) => {
  editing.value = Boolean(group);
  form.value = {
    id: group?.id ?? "",
    display_name: group?.display_name ?? "",
    description: group?.description ?? "",
    sort_order: group?.sort_order ?? 0,
  };
}, { immediate: true });

function submit(): void {
  if (!form.value.display_name.trim() || (!editing.value && !form.value.id.trim())) return;
  emit("submit", {
    id: editing.value ? undefined : form.value.id.trim(),
    display_name: form.value.display_name.trim(),
    description: form.value.description.trim(),
    sort_order: Number(form.value.sort_order) || 0,
  });
  emit("close");
}
</script>

<template>
  <Modal
    :title="editing ? '编辑 Tag Group' : '新建 Tag Group'"
    description="Tag Group 用于定义一组正交的 Tag 枚举，Skill 只能选择这里已经维护的 Tag 值。"
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
      <div class="modal-actions">
        <button class="secondary-button" type="button" @click="emit('close')">取消</button>
        <button class="primary-button" type="button" :disabled="!form.display_name.trim() || (!editing && !form.id.trim())" @click="submit">
          {{ editing ? "保存修改" : "创建" }}
        </button>
      </div>
    </div>
  </Modal>
</template>
