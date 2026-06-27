<script setup lang="ts">
import Modal from "../components/Modal.vue";
import type { SkillDetail } from "../types";
import VersionUploadForm from "./VersionUploadForm.vue";

defineProps<{ skill: SkillDetail }>();
const emit = defineEmits<{ close: []; uploaded: [] }>();
</script>

<template>
  <Modal title="上传版本" description="上传标准 Skill bundle 并追加一个不可变 Skill 版本。" @close="emit('close')">
    <VersionUploadForm :skill="skill" @cancel="emit('close')" @uploaded="emit('uploaded')" />
  </Modal>
</template>
