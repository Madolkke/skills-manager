<script setup lang="ts">
import { AlertTriangle, Trash2 } from "lucide-vue-next";
import { computed, nextTick, ref } from "vue";
import Modal from "../../components/Modal.vue";
import { api, ApiError } from "../../lib/api";

const props = defineProps<{ skillId: string; slug: string; canDelete: boolean }>();
const emit = defineEmits<{ deleted: [] }>();

const modalOpen = ref(false);
const confirmation = ref("");
const error = ref("");
const deleting = ref(false);
const input = ref<HTMLInputElement | null>(null);
const confirmed = computed(() => confirmation.value === props.slug);

async function openModal(): Promise<void> {
  if (!props.canDelete) return;
  confirmation.value = "";
  error.value = "";
  modalOpen.value = true;
  await nextTick();
  input.value?.focus();
}

function closeModal(): void {
  if (deleting.value) return;
  modalOpen.value = false;
}

async function deleteSkill(): Promise<void> {
  if (!confirmed.value || deleting.value) return;
  deleting.value = true;
  error.value = "";
  try {
    await api.deleteSkill(props.skillId, confirmation.value);
    modalOpen.value = false;
    emit("deleted");
  } catch (requestError) {
    error.value = requestError instanceof ApiError || requestError instanceof Error
      ? requestError.message
      : "永久删除失败，请稍后重试。";
  } finally {
    deleting.value = false;
  }
}
</script>

<template>
  <section class="settings-section danger-settings-section">
    <div class="danger-zone">
      <div class="danger-zone-copy">
        <span class="danger-zone-icon" aria-hidden="true"><AlertTriangle :size="20" /></span>
        <div>
          <h3>永久删除 Skill</h3>
          <p>删除所有版本、测评、评审、Workflow 和访问设置。此操作不可恢复。</p>
        </div>
      </div>
      <button
        class="danger-button"
        type="button"
        :disabled="!canDelete"
        :title="canDelete ? '永久删除 Skill' : '只有 owner 或 admin 可以删除 Skill。'"
        data-testid="open-delete-skill"
        @click="openModal"
      >
        <Trash2 :size="16" />
        永久删除 Skill
      </button>
    </div>
    <div v-if="!canDelete" class="settings-notice muted">只有 owner 或 admin 可以永久删除当前 Skill。</div>

    <Modal
      v-if="modalOpen"
      title="永久删除 Skill"
      description="此操作会立即删除 Skill 及其全部从属数据，且无法撤销。"
      @close="closeModal"
    >
      <form class="delete-skill-form" @submit.prevent="deleteSkill">
        <div class="delete-skill-warning">
          <AlertTriangle :size="20" aria-hidden="true" />
          <p>请输入 <strong>{{ slug }}</strong> 以确认永久删除。</p>
        </div>
        <label class="field-label">
          <span>Skill slug</span>
          <input
            ref="input"
            v-model="confirmation"
            autocomplete="off"
            spellcheck="false"
            :disabled="deleting"
            data-testid="delete-skill-confirmation"
          />
        </label>
        <div v-if="error" class="form-error" role="alert">{{ error }}</div>
        <div class="modal-actions">
          <button class="secondary-button" type="button" :disabled="deleting" @click="closeModal">取消</button>
          <button
            class="danger-button"
            type="submit"
            :disabled="!confirmed || deleting"
            data-testid="confirm-delete-skill"
          >
            <Trash2 :size="16" />
            {{ deleting ? "删除中..." : "永久删除" }}
          </button>
        </div>
      </form>
    </Modal>
  </section>
</template>
