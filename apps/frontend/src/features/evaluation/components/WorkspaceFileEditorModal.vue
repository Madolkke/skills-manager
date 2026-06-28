<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { FilePlus2, Trash2 } from "lucide-vue-next";
import Modal from "../../../components/Modal.vue";
import {
  defaultWorkspaceFile,
  formatWorkspaceSize,
  validateWorkspaceFiles,
  workspaceDraftSize,
  type WorkspaceFileDraft,
} from "../lib/workspaceDraft";

const props = defineProps<{
  files: WorkspaceFileDraft[];
  existingWorkspaceLabel: string;
}>();
const emit = defineEmits<{ close: []; save: [files: WorkspaceFileDraft[]] }>();

const draftFiles = ref<WorkspaceFileDraft[]>(cloneFiles(props.files));
const selectedId = ref(draftFiles.value[0]?.id ?? "");
const validation = computed(() => validateWorkspaceFiles(draftFiles.value));
const activeFile = computed(() => draftFiles.value.find((file) => file.id === selectedId.value) ?? draftFiles.value[0] ?? null);
const summary = computed(() => `${draftFiles.value.length} 个文件 · ${formatWorkspaceSize(workspaceDraftSize(draftFiles.value))}`);

watch(
  () => props.files,
  (files) => {
    draftFiles.value = cloneFiles(files);
    selectedId.value = draftFiles.value[0]?.id ?? "";
  },
);

/** 添加一个新的文本文件并切换到该文件。 */
function addFile(): void {
  const next = defaultWorkspaceFile(draftFiles.value.length);
  draftFiles.value.push(next);
  selectedId.value = next.id;
}

/** 删除当前文件；文件列表可以为空，表示工作区为空 zip。 */
function removeFile(fileId: string): void {
  const index = draftFiles.value.findIndex((file) => file.id === fileId);
  if (index < 0) return;
  draftFiles.value.splice(index, 1);
  selectedId.value = draftFiles.value[Math.max(0, index - 1)]?.id ?? draftFiles.value[0]?.id ?? "";
}

/** 更新当前文件路径。 */
function updatePath(value: string): void {
  if (activeFile.value) activeFile.value.path = value;
}

/** 更新当前文件文本内容。 */
function updateContent(value: string): void {
  if (activeFile.value) activeFile.value.content = value;
}

/** 校验通过后提交文件草稿。 */
function save(): void {
  if (!validation.value.valid) return;
  emit("save", cloneFiles(draftFiles.value));
}

/** 计算单个文件内容大小标签。 */
function fileSizeLabel(file: WorkspaceFileDraft): string {
  return formatWorkspaceSize(new TextEncoder().encode(file.content).length);
}

function cloneFiles(files: WorkspaceFileDraft[]): WorkspaceFileDraft[] {
  return files.map((file) => ({ ...file }));
}
</script>

<template>
  <Modal title="布置工作区" description="这些文本文件会打包为测试运行的工作目录。" size="wide" @close="emit('close')">
    <section class="workspace-editor-modal">
      <aside class="workspace-editor-sidebar">
        <div class="workspace-editor-summary">
          <strong>{{ summary }}</strong>
          <span>当前压缩包：{{ existingWorkspaceLabel }}</span>
        </div>
        <button class="secondary-button" type="button" @click="addFile">
          <FilePlus2 :size="16" />
          添加文件
        </button>
        <div class="workspace-file-list">
          <button
            v-for="file in draftFiles"
            :key="file.id"
            :class="['workspace-file-row', file.id === activeFile?.id && 'active', validation.errors[file.id] && 'invalid']"
            type="button"
            @click="selectedId = file.id"
          >
            <strong>{{ file.path || "未命名文件" }}</strong>
            <span>{{ validation.errors[file.id] || fileSizeLabel(file) }}</span>
          </button>
          <p v-if="draftFiles.length === 0" class="workspace-empty-state">当前没有文件，完成后会生成空工作区。</p>
        </div>
      </aside>
      <div class="workspace-editor-main">
        <template v-if="activeFile">
          <header class="scenario-editor-head">
            <div>
              <span>文本文件</span>
              <h3>{{ activeFile.path || "未命名文件" }}</h3>
            </div>
            <button class="icon-button danger" type="button" aria-label="删除文件" @click="removeFile(activeFile.id)">
              <Trash2 :size="17" />
            </button>
          </header>
          <label class="field-label">
            文件路径
            <input :value="activeFile.path" placeholder="例如：src/input.txt" @input="updatePath(($event.target as HTMLInputElement).value)">
            <span v-if="validation.errors[activeFile.id]" class="field-hint danger">{{ validation.errors[activeFile.id] }}</span>
          </label>
          <label class="field-label workspace-content-field">
            文件内容
            <textarea :value="activeFile.content" placeholder="填写 UTF-8 文本内容" @input="updateContent(($event.target as HTMLTextAreaElement).value)" />
          </label>
        </template>
        <div v-else class="workspace-editor-placeholder">
          <strong>还没有文件</strong>
          <span>点击左侧“添加文件”开始布置工作区。</span>
        </div>
      </div>
    </section>
    <footer class="modal-actions workspace-editor-actions">
      <button class="secondary-button" type="button" @click="emit('close')">取消</button>
      <button class="primary-button" type="button" :disabled="!validation.valid" @click="save">完成</button>
    </footer>
  </Modal>
</template>
