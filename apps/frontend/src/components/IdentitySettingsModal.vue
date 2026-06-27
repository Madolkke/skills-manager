<script setup lang="ts">
import { ref } from "vue";
import Modal from "./Modal.vue";
import { clearTemporaryActorId, setTemporaryActorId } from "../lib/identity";

const props = defineProps<{ actor: string }>();
const emit = defineEmits<{ close: []; changed: [actor: string] }>();

const actorId = ref(props.actor);

function save(): void {
  emit("changed", setTemporaryActorId(actorId.value));
}

function clear(): void {
  emit("changed", clearTemporaryActorId());
}
</script>

<template>
  <Modal title="身份设置" description="临时设置当前浏览器使用的身份 ID。后续接入认证套件时，会复用同一个身份读取方式。" @close="emit('close')">
    <div class="form-stack">
      <label class="field-label">
        <span>身份 ID</span>
        <input v-model="actorId" placeholder="例如 product-operator" />
      </label>
      <p class="field-help">这个值会保存在当前浏览器，并随 API 请求发送为 X-SkillHub-Actor。</p>
      <div class="modal-actions">
        <button class="secondary-button" type="button" @click="clear">恢复默认</button>
        <button class="secondary-button" type="button" @click="emit('close')">取消</button>
        <button class="primary-button" type="button" @click="save">保存身份</button>
      </div>
    </div>
  </Modal>
</template>
