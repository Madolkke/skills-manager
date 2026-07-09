<script setup lang="ts">
import { ref, watch } from "vue";
import Modal from "../../components/Modal.vue";
import type { AdminGroup } from "../../lib/api";

const props = defineProps<{ group?: AdminGroup | null }>();
const emit = defineEmits<{
  close: [];
  submit: [payload: { name: string; description?: string }];
}>();

const form = ref({ name: "", description: "" });
const editing = ref(false);

watch(() => props.group, (group) => {
  editing.value = Boolean(group);
  form.value = { name: group?.name ?? "", description: group?.description ?? "" };
}, { immediate: true });

function submit(): void {
  if (!form.value.name.trim()) return;
  emit("submit", {
    name: form.value.name.trim(),
    description: form.value.description.trim(),
  });
  emit("close");
}
</script>

<template>
  <Modal
    :title="editing ? '编辑用户组' : '新建用户组'"
    description="用户组用于集中管理身份 ID，可在发起评审时直接选择，也可对 Skill 或 Tag 授权。"
    @close="emit('close')"
  >
    <div class="form-stack admin-modal-form">
      <label class="field-label">
        <span>组名称</span>
        <input v-model="form.name" placeholder="例如 backend-reviewers" />
      </label>
      <label class="field-label">
        <span>描述</span>
        <textarea v-model="form.description" placeholder="说明这个用户组包含哪些人，以及适合授予哪些权限" />
      </label>
      <div class="modal-actions">
        <button class="secondary-button" type="button" @click="emit('close')">取消</button>
        <button class="primary-button" type="button" :disabled="!form.name.trim()" @click="submit">
          {{ editing ? "保存修改" : "创建" }}
        </button>
      </div>
    </div>
  </Modal>
</template>
