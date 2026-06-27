<script setup lang="ts">
import { ref, watch } from "vue";
import Modal from "../../components/Modal.vue";
import type { AdminGroup } from "../../lib/api";

const props = defineProps<{ group: AdminGroup }>();
const emit = defineEmits<{
  close: [];
  submit: [subjectId: string];
}>();

const subjectId = ref("");

watch(() => props.group.id, () => {
  subjectId.value = "";
});

function submit(): void {
  const next = subjectId.value.trim();
  if (!next) return;
  emit("submit", next);
  emit("close");
}
</script>

<template>
  <Modal :title="`添加成员到 ${group.name}`" description="成员身份 ID 来自前端身份设置；普通请求不能自行声明用户组。" @close="emit('close')">
    <div class="form-stack admin-modal-form">
      <label class="field-label">
        <span>用户身份 ID</span>
        <input v-model="subjectId" placeholder="例如 product-operator" @keydown.enter="submit" />
      </label>
      <div class="modal-actions">
        <button class="secondary-button" type="button" @click="emit('close')">取消</button>
        <button class="primary-button" type="button" :disabled="!subjectId.trim()" @click="submit">添加成员</button>
      </div>
    </div>
  </Modal>
</template>
