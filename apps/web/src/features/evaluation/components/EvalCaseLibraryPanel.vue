<script setup lang="ts">
import { Link2, Search, X } from "lucide-vue-next";
import { computed, ref } from "vue";
import { humanDate } from "../../../lib/format";
import type { EvalCaseLibraryItem } from "../../../types";

const props = defineProps<{
  items: EvalCaseLibraryItem[];
  busy?: boolean;
}>();
const emit = defineEmits<{
  add: [caseId: string];
  close: [];
}>();

const query = ref("");

const filteredItems = computed(() => {
  const normalized = query.value.trim().toLowerCase();
  if (!normalized) return props.items;
  return props.items.filter((item) => {
    const stepText = item.case_version.steps.map((step) => [step.title, step.input, JSON.stringify(step.assertions)].join(" ")).join(" ");
    return [item.case.title, stepText].join(" ").toLowerCase().includes(normalized);
  });
});
</script>

<template>
  <section class="case-library-panel">
    <header>
      <div>
        <strong>添加已有测试例</strong>
        <span>{{ items.length }} 个可添加</span>
      </div>
      <button class="icon-button mini" type="button" aria-label="关闭添加已有测试例" @click="emit('close')">
        <X :size="16" />
      </button>
    </header>
    <label class="search-field compact">
      <Search :size="17" />
      <input v-model="query" placeholder="搜索已有测试例">
    </label>
    <div class="case-library-list">
      <article v-for="item in filteredItems" :key="item.case.id" class="case-library-row">
        <div>
          <strong>{{ item.case.title }}</strong>
          <span>
            测试例 v{{ item.case_version.version_number }} · 更新 {{ humanDate(item.case.updated_at) }}
          </span>
        </div>
        <button class="secondary-button" type="button" :disabled="busy" @click="emit('add', item.case.id)">
          <Link2 :size="16" />
          加入
        </button>
      </article>
      <p v-if="filteredItems.length === 0" class="case-library-empty">没有可添加的测试例。</p>
    </div>
  </section>
</template>
